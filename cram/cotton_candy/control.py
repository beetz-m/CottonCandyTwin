"""
A control page for the generalized plan, served by the demo process next to the cramera viewer.

cramera shows and queries the running plan but cannot start one, so the demo serves this page itself
(http://127.0.0.1:8770). From the page you place orders, change the state of the booth (exogenous events, or the
robot doing part of the work first), project which sub-goals the plan would run, and let the plan achieve its goal.
cramera shows the execution live.

Threading: the HTTP server only queues commands and reads the last status snapshot. Every command, and every status
snapshot, runs on the demo's own thread inside its execution environment, where the plan normally runs; the world
is never touched from the HTTP thread.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
import traceback
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from typing_extensions import Any, Callable, Dict, List, Optional

from coraplex.plans.factories import sequential
from krrood.entity_query_language.exceptions import MultipleSolutionFound, NoSolutionFound
from semantic_digital_twin.semantic_annotations.semantic_annotations import Human

from cotton_candy.actions import StopFlossMachineAction
from cotton_candy.manipulation_categories import ApproachDirection, TransportingAction
from cotton_candy.process import CandyStage
from cotton_candy.recipes import Flavour
from cotton_candy.semantic_annotations import CandyStick, CottonCandyMachine
from cotton_candy.universal_plan import GoalUnachievable, MakeAndHandOverCandyPlan

logger = logging.getLogger(__name__)

DEFAULT_PORT = int(os.environ.get("COTTON_CANDY_CONTROL_PORT", "8770"))
"""
Port of the control page (``COTTON_CANDY_CONTROL_PORT``; cramera's viewer uses 8711 and its live bridges 8765 and up).
"""

PAGE = Path(__file__).with_name("control_page.html")
"""
The page's HTML.
"""


@dataclass
class Command:
    """
    A request from the page, executed on the demo thread.
    """

    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanControl:
    """
    Executes the page's commands with the generalized plan and keeps a status snapshot for the page.
    """

    plan: MakeAndHandOverCandyPlan
    """
    The generalized plan.
    """

    attach_plan: Optional[Callable[[Any], None]] = None
    """
    Shows a sub-plan in the viewer (the visualization's ``attach_plan``).
    """

    port: int = DEFAULT_PORT
    """
    Port of the control page.
    """

    commands: "queue.Queue[Command]" = field(default_factory=queue.Queue)
    status: Dict[str, Any] = field(default_factory=dict)
    log: List[Dict[str, Any]] = field(default_factory=list)
    running: Optional[str] = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # %% the commands

    @property
    def world(self):
        return self.plan.context.world

    @property
    def arm(self):
        return self.plan.context.robot.right_arm

    def _run(self, designators) -> None:
        sub_plan = sequential(designators, self.plan.context)
        if self.attach_plan is not None:
            self.attach_plan(sub_plan)
        sub_plan.perform()

    def order(self, flavour: str = Flavour.RASPBERRY.name, customer: Optional[str] = "Customer") -> str:
        candy = self.plan.process.new_order(Flavour[flavour].value, ordered_by=customer or None)
        return f"order {candy.order}: {candy.flavour} for {customer or 'any customer'}"

    def cancel_open_orders(self) -> str:
        process = self.plan.process
        open_orders = [c for c in process.candies if c.stage is not CandyStage.DELIVERED]
        process.candies[:] = [c for c in process.candies if c.stage is CandyStage.DELIVERED]
        return f"cancelled {len(open_orders)} open order(s)"

    def empty_sugar_head(self) -> str:
        """
        Exogenous: the head runs dry (the plan has to refill before it can form a candy).
        """
        process = self.plan.process
        grams = 1000 * (process.sugar_in_head_kg + process.floss_in_pan_kg)
        process.sugar_in_head_kg = 0.0
        process.floss_in_pan_kg = 0.0
        return f"spinner head and pan emptied ({grams:.0f} g of sugar and floss removed)"

    def take_stick(self) -> str:
        """
        The robot takes a free stick before the plan runs (the plan then starts later in its table).
        """
        quiver_sticks = [s for s in self.world.get_semantic_annotations_by_type(CandyStick)
                         if s.root.parent_kinematic_structure_entity is not self.arm.end_effector.tool_frame
                         and s.root.parent_kinematic_structure_entity.name.name != "Customer"]
        tool_frame = self.arm.end_effector.tool_frame
        held = [b.name.name for b in self.world.bodies if b.parent_kinematic_structure_entity is tool_frame]
        if held:
            return f"the gripper already holds {held[0]}"
        if not quiver_sticks:
            return "no free stick left in the quiver"
        stick = quiver_sticks[0]
        self._run([TransportingAction(stick, self.arm, ApproachDirection.TOWARDS_LEFT_WALL)])
        return f"robot took {stick.root.name.name}"

    def stop_machine(self) -> str:
        machine = self.world.get_semantic_annotations_by_type(CottonCandyMachine)[0]
        if self.plan.process.phase.name == "OFF":
            return "the machine is already off"
        self._run([StopFlossMachineAction(machine, self.plan.process, self.arm)])
        return f"robot stopped the machine (phase {self.plan.process.phase.value})"

    def lose_candy(self) -> str:
        """
        Belief and world disagree: the belief says the open candy is wrapped on a stick the robot does not hold.
        """
        process = self.plan.process
        open_orders = [c for c in process.candies if c.stage is not CandyStage.DELIVERED]
        if not open_orders:
            return "no open order to lose"
        tool_frame = self.arm.end_effector.tool_frame
        elsewhere = [s.root.name.name for s in self.world.get_semantic_annotations_by_type(CandyStick)
                     if s.root.parent_kinematic_structure_entity is not tool_frame]
        candy = open_orders[-1]
        candy.stage, candy.stick = CandyStage.WRAPPED, elsewhere[-1]
        return f"belief now says order {candy.order} is wrapped on {candy.stick}, which the robot does not hold"

    def project(self) -> str:
        belief = self.plan.estimator.estimate(self.plan.the_candy())
        rows = self.plan.projection(belief)
        return "projection: " + (" -> ".join(rows) if rows else "goal already holds, nothing to do")

    def achieve(self) -> str:
        plan = self.plan
        plan.trace.clear()
        plan.failures.clear()
        final = plan.perform()
        failures = "; ".join(f"{f.tag}: {f.description}" for f in plan.failures)
        return (f"achieved: {' -> '.join(plan.trace) or 'nothing to do'}"
                + (f" (recovered from: {failures})" if failures else "")
                + f"; candy {final.candy.order} {final.stage.value}")

    COMMANDS = ("order", "cancel_open_orders", "empty_sugar_head", "take_stick", "stop_machine", "lose_candy",
                "project", "achieve")

    def execute(self, command: Command) -> None:
        """
        Run one command on the demo thread and log its outcome.
        """
        self.running = command.name
        started = time.time()
        try:
            message, ok = getattr(self, command.name)(**command.arguments), True
        except (GoalUnachievable, MultipleSolutionFound, NoSolutionFound, LookupError) as error:
            message, ok = f"{type(error).__name__}: {error}", False
        except Exception as error:   # report, keep serving
            logger.error("command %s failed:\n%s", command.name, traceback.format_exc())
            message, ok = f"{type(error).__name__}: {error}"[:300], False
        finally:
            self.running = None
        entry = {"time": time.strftime("%H:%M:%S"), "command": command.name, "ok": ok, "message": message,
                 "seconds": round(time.time() - started, 1)}
        with self._lock:
            self.log.append(entry)
            del self.log[:-40]
        print(f"[control] {command.name}: {message}", flush=True)

    # %% the status

    def snapshot(self) -> Dict[str, Any]:
        """
        The state the page shows: the machine, the candy belief store, and the plan's view of the candy.
        """
        plan, process = self.plan, self.plan.process
        status: Dict[str, Any] = {
            "machine": {"phase": process.phase.value, "sugar_in_head_g": round(1000 * process.sugar_in_head_kg, 1),
                        "floss_in_pan_g": round(1000 * process.floss_in_pan_kg, 1),
                        "portions_served": process.portions_served, "time_s": round(process.time_s)},
            "candies": [{"order": c.order, "flavour": c.flavour, "stage": c.stage.value, "stick": c.stick,
                         "ordered_by": c.ordered_by, "customer": c.customer} for c in process.candies],
            "flavours": [f.name for f in Flavour],
            "customers": [h.root.name.name for h in self.world.get_semantic_annotations_by_type(Human)],
            "rows": [{"index": s.index, "tag": s.tag, "kernel": s.kernel_text} for s in plan.steps()],
            "trace": list(plan.trace),
            "failures": [{"tag": f.tag, "reason": f.description} for f in plan.failures],
        }
        try:
            # As the plan does: the open order, else the last candy (whose delivery is then the goal that holds).
            if not plan._open_order() and process.candies:
                belief = plan.estimator.estimate(plan._last_candy())
            else:
                belief = plan.estimator.estimate(plan.the_candy())
            status["belief"] = {
                "candy": belief.candy.order, "flavour": belief.candy.flavour, "stage": belief.stage.value,
                "stick": belief.stick.root.name.name if belief.stick else None,
                "sugar": belief.sugar.root.name.name if belief.sugar else None,
                "customer": belief.customer.root.name.name if belief.customer else None,
                "ingredients": [m.name for m in belief.ingredients],
                "holding": belief.holding.value, "held": belief.held.root.name.name if belief.held else None,
                "fluents": {"gripper free": belief.gripper_free, "sugar available": belief.sugar_available,
                            "producing": belief.producing, "enough sugar": belief.enough_sugar,
                            "stick in hand": belief.stick_in_hand, "delivered": belief.delivered},
            }
            rows = [s for s in plan.steps()]
            status["kernels"] = [s.kernel(belief) for s in rows]
            status["goals"] = [s.goal(belief) for s in rows]
            try:
                selected = plan.select(belief)
                status["selected"] = None if selected is None else selected.tag
                status["projection"] = plan.projection(belief)
            except GoalUnachievable as error:
                status["selected"], status["projection"], status["unachievable"] = None, [], str(error)
        except MultipleSolutionFound:
            status["belief_error"] = "THE candy is ambiguous: more than one open order (cancel one)"
        except (NoSolutionFound, LookupError):
            status["belief_error"] = "no open order: place one"
        return status

    def publish_status(self) -> None:
        try:
            status = self.snapshot()
        except Exception as error:
            status = {"snapshot_error": f"{type(error).__name__}: {error}"[:300]}
        with self._lock:
            self.status = status

    def page_status(self) -> Dict[str, Any]:
        with self._lock:
            return {**self.status, "running": self.running, "current_row": self.plan.trace[-1] if self.running ==
                    "achieve" and self.plan.trace else None, "queued": self.commands.qsize(), "log": list(self.log)}

    # %% serving

    def serve_forever(self) -> None:
        """
        Start the page's HTTP server and execute queued commands on this (the demo's) thread, until interrupted.
        """
        server = ThreadingHTTPServer(("127.0.0.1", self.port), _handler_for(self))
        threading.Thread(target=server.serve_forever, name="cotton-candy-control", daemon=True).start()
        print(f"[control] plan control page: http://127.0.0.1:{self.port}/", flush=True)
        self.publish_status()
        try:
            while True:
                try:
                    command = self.commands.get(timeout=1.0)
                except queue.Empty:
                    self.publish_status()
                    continue
                self.execute(command)
                self.publish_status()
        finally:
            server.shutdown()


def _handler_for(control: PlanControl):
    allowed_origins = {f"http://127.0.0.1:{control.port}", f"http://localhost:{control.port}"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

        def _send(self, body: bytes, content_type: str, code: int = 200) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload: Any, code: int = 200) -> None:
            self._send(json.dumps(payload).encode(), "application/json", code)

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                return self._send(PAGE.read_bytes(), "text/html; charset=utf-8")
            if self.path.startswith("/status"):
                return self._json(control.page_status())
            self._json({"ok": False, "error": "unknown endpoint"}, 404)

        def do_POST(self) -> None:
            # Only this page may send commands (no cross-site requests to the robot).
            origin = self.headers.get("Origin")
            if origin is not None and origin not in allowed_origins:
                return self._json({"ok": False, "error": "origin not allowed"}, 403)
            name = self.path.strip("/").split("?")[0]
            if name not in PlanControl.COMMANDS:
                return self._json({"ok": False, "error": f"unknown command {name!r}"}, 404)
            try:
                arguments = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            except json.JSONDecodeError:
                return self._json({"ok": False, "error": "body must be JSON"}, 400)
            if not isinstance(arguments, dict):
                return self._json({"ok": False, "error": "body must be a JSON object"}, 400)
            if name == "order":
                arguments = {k: v for k, v in arguments.items() if k in ("flavour", "customer")}
                if arguments.get("flavour", Flavour.RASPBERRY.name) not in Flavour.__members__:
                    return self._json({"ok": False, "error": "unknown flavour"}, 400)
            else:
                arguments = {}
            control.commands.put(Command(name, arguments))
            self._json({"ok": True, "queued": name})

    return Handler
