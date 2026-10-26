"""SUPERSEDED by ccram (~/Documents/ConceptualCRAM/ccram/kernel.py) + concept/adapter.py; kept for reference.

The conceptual CRAM kernel on the cotton candy booth (M1 step 3): booth.lisp, executed.

Reads the schema library (booth.lisp) and runs its plan schemas on the CRAM booth world (coraplex, kinematic PR2,
FlossMachineProcess). Every (perform (an action ...)) goes through the D10 cycle:
    1. goal     the schema's :telos template instantiated with the bound roles (perform -> goal)
    2. skip     its achieve parts already hold -> nothing to do (check before acting)
    3. climb    each role is resolved by a servant of the servant table, with the binding status it yields (D3)
    4. gate     the template's (prevent phi :while chi) parts with chi true now -> refused before acting (D6, the
                closing events of the microtheory); the schema's :pre where observable
    5. realise  the schema's phases -> the existing coraplex actions (cotton_candy.manipulation_categories)
    6. verdict  the template checked on the states before / at the process events / after (D10 trajectory check);
                a violated part raises a typed failure (Q2) for the enclosing with-failure-handling
and is recorded as an episode node (tag path, designator, bindings + servant + status, goal, gate, verdict).

Predicates are read from the world and the process model (StateReader); predicates the kinematic simulation cannot
observe (dropped, spilled) are reported as model-only, never asserted.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))           # cram/concept
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, os.path.dirname(HERE))                                     # cram -> cotton_candy
sys.path.insert(0, os.path.expanduser("~/Documents/HouseholdTwin/tools"))
import ccram_goals as G  # noqa: E402
from sdt_sexpr import TagTable, parse  # noqa: E402

MODEL_ONLY = {"dropped", "spilled", "contact", "clean"}       # not observable in the kinematic booth
OBSERVABLE = {"mode", "gripper-free", "held-by", "at", "contains", "portion-spun", "on", "switch-state",
              "travel-fraction", "on-tool", "stage", "holds", "burnt-out", "delivered"}       # StateReader


class KernelFailure(Exception):
    """A typed failure description (Q2): .kind is the failure keyword of the ontology."""

    def __init__(self, kind, description, **info):
        super().__init__(f"{kind}: {description}")
        self.kind, self.description, self.info = kind, description, info


# ---------------------------------------------------------------------------------------------------- library
class Library:
    def __init__(self, path=os.path.join(HERE, "booth.lisp")):
        self.forms = parse(open(path).read())
        self.acts, self.plans, self.problems = G.schemas_of(self.forms)
        self.params = {f[1]: f[2] for f in self.forms if isinstance(f, list) and f and f[0] == "def-plan-schema"}
        self.tags = TagTable([f for f in self.forms if isinstance(f, list) and f and f[0] == ":tag"])
        G.PROCESS_PREDS.update(G.process_preds(self.forms))
        G.PLANS.update(self.plans)
        self._onto = None
        self.onto()                     # ontology reasoning in refinement and state checks (on -> at, D9)

    def onto(self):
        if self._onto is None:
            import ccram_lang as CL
            o = CL.Ontology()
            self._onto = (o, CL.Lexicon(o), CL)
            G.use_ontology()
        return self._onto

    def failure_is_a(self, kind, handler):
        if kind == handler:
            return True
        o, lex, CL = self.onto()
        a, b = lex.resolve("type", kind), lex.resolve("type", handler)
        return bool(a and b and o.is_a(a[0], b[0]))

    def grounding(self, tag):
        """(grounding (annotation CLASS FIELD)) of a tagged node -> (class, field)."""
        h = self.tags.find(tag)
        node = self.tags.node.get(h) if h is not None else None
        for c in (node or [])[1:]:
            if isinstance(c, list) and c and c[0] == "grounding" and isinstance(c[1], list) and c[1][0] == "annotation":
                return c[1][1], c[1][2]
        return None


# ---------------------------------------------------------------------------------------------------- the booth world
class Booth:
    """The CRAM side: world, robot, process, and the symbols the plan language uses for its entities."""

    def __init__(self, world, context, process):
        from cotton_candy.semantic_annotations import CandyStick, CottonCandyMachine, HandoverZone, Sponge, SugarCarton
        from semantic_digital_twin.semantic_annotations.semantic_annotations import Human
        self.world, self.context, self.process = world, context, process
        self.robot = context.robot
        one = lambda c: world.get_semantic_annotations_by_type(c)[0]            # noqa: E731
        self.machine = one(CottonCandyMachine)
        self.types = {"cotton-candy-machine": CottonCandyMachine, "sugar-carton": SugarCarton, "candy-stick": CandyStick,
                      "sponge": Sponge, "customer": Human, "handover-location": HandoverZone}
        self.symbol_of = {id(self.machine): "machine", id(self.robot.right_arm): "right-arm",
                          id(self.robot.left_arm): "left-arm"}
        self.home = {}                  # its destination (D7, class home): where an object was taken from
        self.parent = {}                # ... and the body it hung from (re-attached when it is put back)
        self.grip = {}                  # grip point recorded at the take (pouring lifts from it)
        self.events = []                # (process time, atom) -- e.g. (poured-into sugar spinner-head)

    def sym(self, v):
        return self.symbol_of.get(id(v)) or getattr(getattr(v, "name", None), "name", None) or str(v)

    def name(self, v, s):
        self.symbol_of[id(v)] = s
        return s


class StateReader:
    """Ground atoms of the current state (the trajectory checker's view)."""

    def __init__(self, booth):
        self.b = booth

    def atoms(self, tracked=()):
        b = self.b
        from coraplex.querying.predicates import GripperIsFree
        a = [["mode", "floss-machine", b.process.phase.value.replace("_", "-")]]
        if b.process.sugar_in_head_kg > 1e-6:                  # a quantity: (contains head (mass kg))
            a.append(["contains", "spinner-head", ["mass", round(b.process.sugar_in_head_kg, 4)]])
        if b.process.portion_ready:
            a.append(["portion-spun"])
        if b.process.burnt_out_s >= b.process.timings.burn_out_s - 1e-6:
            a.append(["burnt-out", "machine"])
        for sw in ("motor-switch", "heat-switch"):
            a.append(["switch-state", sw, "on" if getattr(b.machine, sw.replace("-", "_")).is_on else "off"])
        a.append(["travel-fraction", "heat-control", round(float(b.machine.heat_control.travel_fraction), 2)])
        for i, c in enumerate(b.process.candies):
            st, cs = c.stage.value, f"candy-{i + 1}"            # the order's symbol (climb: order-record)
            if st in ("gathered", "wrapped", "delivered"):
                stick = next((b.sym(o) for o in tracked if o.root.name.name == c.stick), c.stick or "candy-stick")
                a.append(["on-tool", "floss", stick])        # the process names the stick by its body, the plan by tag
            a.append(["stage", cs, st])
            if st == "delivered":
                a.append(["delivered", cs, "customer"])
        for obj in tracked:
            par = obj.root.parent_kinematic_structure_entity
            for hu in b.world.get_semantic_annotations_by_type(b.types["customer"]):
                if par is hu.root:
                    a.append(["holds", b.sym(hu), b.sym(obj)])
                    a.append(["taken-by", b.sym(hu), b.sym(obj)])     # the hand-over's release condition
        for arm in (b.robot.right_arm, b.robot.left_arm):
            ee = arm.end_effector
            if GripperIsFree(ee)():
                a.append(["gripper-free", b.sym(arm)])
            branch = b.world.get_kinematic_structure_entities_of_branch(ee.tool_frame)
            for obj in tracked:
                if obj.root in branch:
                    a.append(["held-by", b.sym(obj), b.sym(arm)])
        base = b.robot.root.global_pose.to_np()
        from cotton_candy.booth_world import RobotStation
        for st in RobotStation:
            p = st.pose(b.world.root).to_np()
            if math.hypot(*(base[:2, 3] - p[:2, 3])) < 0.02:          # stations lie centimetres apart
                a.append(["at", ["the", "robot"], TAG_OF_STATION[st.name]])
        for obj in tracked:
            h = b.home.get(id(obj))
            if h is not None:
                d = obj.root.global_pose.to_np()[:3, 3] - h.to_np()[:3, 3]
                if float((d ** 2).sum()) ** 0.5 < 0.05 and not any(x[0] == "held-by" and x[1] == b.sym(obj) for x in a):
                    a.append(["on", b.sym(obj), "home-of-" + b.sym(obj)])
        return a


# ---------------------------------------------------------------------------------------------------- the climb
STATIONS = {"at-machine": "MACHINE", "machine-close": "MACHINE_CLOSE", "serving": "SERVING"}
TAG_OF_STATION = {v: k for k, v in STATIONS.items()}


class Climb:
    """Resolve a role filler with the servant table's servants; returns (value, symbol, record)."""

    def __init__(self, lib, booth):
        self.lib, self.b = lib, booth

    def resolve(self, x, env, role=None):
        b = self.b
        if isinstance(x, str) and x.startswith("?"):
            return env[x]
        if not isinstance(x, list):
            return x, x if isinstance(x, (int, float)) else str(x), dict(servant="literal", status="recorded")
        if x[0] not in ("a", "an", "the", "some", "its", "tagged", "each"):     # a condition (until, ...)
            return subst_sym(x, env), subst_sym(x, env), dict(servant="condition", status="recorded")
        if x[0] in ("a", "an", "the") and x[1] == "cotton-candy":    # order-record: the candy belief of the order
            c = b.process.candy
            return c, f"candy-{b.process.candies.index(c) + 1}", dict(servant="order-record", status="recorded",
                                                                     ordered_by=c.customer)
        if x[0] == "tagged":                                    # part-of-reference -> sdt-part-tree
            scope = self.resolve(x[2], env)[0] if len(x) > 2 else None
            cls_field = self.lib.grounding(x[1])
            if cls_field and scope is not None:
                v = getattr(scope, cls_field[1])
                return v, b.name(v, x[1]), dict(servant="sdt-part-tree", status="recorded",
                                                 grounding=f"{cls_field[0]}.{cls_field[1]}")
            raise KernelFailure("no-referent", f"{G.show(x)} has no grounding")
        if x[0] == "the" and x[1] == "station":                 # robot-station -> layout-stations
            tag = next(c[1] for c in x[2:] if isinstance(c, list) and c[0] == "tag")
            from cotton_candy.booth_world import RobotStation
            st = RobotStation[STATIONS[tag]]
            return st.pose(b.world.root), tag, dict(servant="layout-stations", status="recorded")
        if x[0] == "its" and x[1] == "destination":             # destination-its -> class home (D7)
            obj = env.get("_object")
            h = b.home.get(id(obj[0])) if obj else None
            if h is None:
                raise KernelFailure("no-referent", "no belonging place known (ask)")
            return h, "home-of-" + obj[1], dict(servant="class-home", status="commonsense",
                                                 note="where it was taken from (no belonging norm for this context)")
        if x[0] == "some":                                      # amount -> recipe
            t = b.process.timings
            kg = max(0.0, t.head_capacity_kg * t.fill_fraction - b.process.sugar_in_head_kg)
            target = t.head_capacity_kg * t.fill_fraction       # what the head must contain afterwards
            ov = getattr(self, "override", None)
            if ov:
                kg = ov.pop(0)
                return kg, ["mass", round(b.process.sugar_in_head_kg + kg, 4)], dict(
                    servant="recipe", status="assumed", value_kg=round(kg, 4),
                    note="carton nearly empty: less than the recipe")
            return kg, ["mass", round(target, 4)], dict(servant="recipe", status="commonsense", value_kg=round(kg, 4))
        if x[0] in ("a", "an", "the") and x[1] in b.types:      # object-by-type -> eql-annotations
            vs = b.world.get_semantic_annotations_by_type(b.types[x[1]])
            if not vs:
                raise KernelFailure("no-referent", f"no {x[1]}")
            if x[1] == "candy-stick":                              # a free stick: not handed to a customer
                hum = [h.root for h in b.world.get_semantic_annotations_by_type(b.types["customer"])]
                free = [v for v in vs if v.root.parent_kinematic_structure_entity not in hum]
                k = vs.index(free[0]) if free else 0
                return vs[k], b.name(vs[k], f"stick-{k + 1}"), dict(servant="eql-annotations", status="recorded",
                                                                     candidates=len(free))
            if x[0] == "the" and len(vs) > 1:
                raise KernelFailure("multiple-solutions-found", f"{len(vs)} x {x[1]}")
            v = vs[0]
            tag = {"sugar-carton": "sugar-carton-raspberry", "cotton-candy-machine": "machine", "customer": "customer",
                   "handover-location": "handover-zone", "sponge": "sponge", "candy-stick": "stick-1"}.get(x[1], b.sym(v))
            return v, b.name(v, tag), dict(servant="eql-annotations", status="recorded", candidates=len(vs))
        raise KernelFailure("no-referent", f"no servant for {G.show(x)}")


# ---------------------------------------------------------------------------------------------------- realisations
class Realiser:
    """Schema phases -> coraplex actions (the parameters are the booth's, cotton_candy/actions.py)."""

    def __init__(self, booth, reader):
        self.b, self.r = booth, reader

    def nodes(self, schema, roles):
        return getattr(self, schema.replace("-", "_"))(roles)

    @staticmethod
    def _half(obj):
        spout = obj.get_tool_frame().global_pose.to_np()
        root = obj.root.global_pose.to_np()
        return float(((spout[:3, 3] - root[:3, 3]) ** 2).sum()) ** 0.5

    def transporting(self, R):
        """grasp servant (grasp-candidates): approach and grasp offset per object class, as cotton_candy/actions.py."""
        from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
        from cotton_candy.actions import pose_above
        from cotton_candy.manipulation_categories import ApproachDirection, TransportingAction
        from semantic_digital_twin.datastructures.definitions import TorsoState
        obj, arm = R["object"][0], R["arm"][0]
        kind = type(obj).__name__
        if os.environ.get("KERNEL_DEBUG"):
            from coraplex.querying.predicates import GripperIsFree
            w = self.b.world
            tor = [round(float(c.position), 3) for c in w.connections if "torso_lift" in c.name.name and hasattr(c, "position")]
            print("      [debug] take", kind, "base", self.b.robot.root.global_pose.to_np()[:3, 3].round(3), "torso", tor[:1],
                  "free R/L", GripperIsFree(self.b.robot.right_arm.end_effector)(),
                  GripperIsFree(self.b.robot.left_arm.end_effector)(), "obj", obj.root.global_pose.to_np()[:3, 3].round(3),
                  "obj parent", obj.root.parent_kinematic_structure_entity.name.name, flush=True)
        if id(obj) not in self.b.home:                 # class home (D7): the full pose it was taken from (orientation
            from scipy.spatial.transform import Rotation   # matters: a stick goes back upright into the quiver) and
            from semantic_digital_twin.spatial_types.spatial_types import Pose   # the body it hung from
            m = obj.root.global_pose.to_np()
            qx, qy, qz, qw = Rotation.from_matrix(m[:3, :3]).as_quat()
            self.b.home[id(obj)] = Pose.from_xyz_quaternion(pos_x=float(m[0, 3]), pos_y=float(m[1, 3]),
                                                            pos_z=float(m[2, 3]), quat_x=qx, quat_y=qy, quat_z=qz,
                                                            quat_w=qw, reference_frame=self.b.world.root)
            self.b.parent[id(obj)] = obj.root.parent_kinematic_structure_entity
        if kind == "SugarCarton":
            half = self._half(obj)
            self.b.grip[id(obj)] = pose_above(obj.root.global_pose, -half + 0.03, self.b.world.root)
            return [MoveTorsoAction(TorsoState.HIGH),
                    TransportingAction(obj, arm, ApproachDirection.TOWARDS_SALES_FRONT,
                                       grasp_offset=(0.0, 0.0, -half + 0.03))]
        if kind == "CandyStick":
            return [MoveTorsoAction(TorsoState.LOW), TransportingAction(obj, arm, ApproachDirection.TOWARDS_LEFT_WALL)]
        return [TransportingAction(obj, arm, ApproachDirection.TOWARDS_SALES_FRONT)]

    def pressing_button(self, R):
        from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
        from cotton_candy.manipulation_categories import PressingButtonAction
        from semantic_digital_twin.datastructures.definitions import TorsoState
        arm = R.get("arm", (self.b.robot.right_arm,))[0]
        on = str(R["state"][1]) == "on"
        b = self.b
        from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
        return [MoveTorsoAction(TorsoState.LOW), PressingButtonAction(R["object"][0], arm, 1.0 if on else 0.0),
                self._step(b.process.notice_switches), ParkArmsAction(b.robot.all_arms)]   # as Start/Stop end

    def turning(self, R):
        from cotton_candy.manipulation_categories import TurningAction
        arm = R.get("arm", (self.b.robot.right_arm,))[0]
        from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
        return [TurningAction(R["object"][0], arm, float(R["setting"][0])), ParkArmsAction(self.b.robot.all_arms)]

    def monitoring_process(self, R):
        """Waits on the process model until the condition holds (the machine's reported state on a real one)."""
        b, rd = self.b, self.r
        until = R["until"][1]
        limit = float(R["timeout"][0]) if "timeout" in R else 900.0

        def wait():
            b.process.notice_switches()
            waited = 0.0
            prev = b.process.phase.value
            while not G.holds(until, rd.atoms(self.tracked)) and waited < limit:
                b.process.advance(0.5)
                waited += 0.5
                ph = b.process.phase.value
                if ph == "running_empty" and prev != "running_empty":       # floss-machine microtheory: mode
                    self.interp.signal("head-running-empty",                  # running-empty :signals
                                       f"spinner head ran empty at t = {b.process.time_s:.0f} s")
                prev = ph
            if not G.holds(until, rd.atoms(self.tracked)):
                from cotton_candy.process import PhaseNotReached
                raise PhaseNotReached(b.process.phase, b.process.phase)
        return [self._step(wait)]

    def gathering(self, R):
        from cotton_candy.manipulation_categories import GatheringAction
        stick, pan = R["tool"][0], R["container"][0]
        arm = R.get("arm", (self.b.robot.right_arm,))[0]
        return [GatheringAction(arm=arm, tool=stick, container=pan.root),
                self._step(lambda: self.b.process.take_portion(stick.root.name.name))]

    def wrapping(self, R):
        from cotton_candy.manipulation_categories import WrappingAction
        arm = R.get("arm", (self.b.robot.right_arm,))[0]
        return [WrappingAction(arm=arm, tool=R["tool"][0], above=R["above"][0].root),
                self._step(self.b.process.candy_wrapped)]

    def handing_over(self, R):
        from coraplex.plans.attachment_nodes import ReAttachNode
        from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
        from cotton_candy.manipulation_categories import HandingOverAction
        from semantic_digital_twin.spatial_types.spatial_types import Pose
        stick, customer, zone = R["object"][0], R["recipient"][0], R["destination"][0]
        arm = R.get("arm", (self.b.robot.right_arm,))[0]
        z = zone.root.global_pose.to_np()
        pose = Pose.from_xyz_rpy(x=float(z[0, 3]), y=float(z[1, 3]), z=float(z[2, 3]), pitch=-math.pi / 2,
                                 reference_frame=self.b.world.root)
        return [HandingOverAction(stick, arm, pose), ReAttachNode(body=stick.root, new_parent=customer.root),
                self._step(lambda: self.b.process.candy_delivered(customer.root.name.name)),
                ParkArmsAction(self.b.robot.all_arms)]

    def wiping(self, R):
        """The stainless strip beside the pan (the original CleanFlossMachineAction: never water in the head)."""
        from coraplex.datastructures.enums import WipingTechnique
        from cotton_candy.manipulation_categories import CategorisedWipingAction
        from semantic_digital_twin.spatial_types.spatial_types import Pose
        sponge = R["tool"][0]
        arm = R.get("arm", (self.b.robot.right_arm,))[0]
        table = self.b.world.get_body_by_name("MachineTable")
        bbox = table.collision.as_bounding_box_collection_in_frame(self.b.world.root).bounding_box()
        sp = sponge.root.global_pose.to_np()
        target = Pose.from_xyz_rpy(x=float(sp[0, 3]), y=float(bbox.max_y) - 0.08, z=float(bbox.max_z),
                                   reference_frame=self.b.world.root)
        return [CategorisedWipingAction(arm=arm, tool=sponge, target_pose=target, technique=WipingTechnique.WIPE,
                                        length=0.15, cycles=2.0)]

    def _step(self, fn):
        from cotton_candy.process_nodes import process_step
        return process_step(fn)

    def navigating(self, R):                            # noqa: D102
        from coraplex.robot_plans.actions.core.navigation import NavigateAction
        return [NavigateAction(R["destination"][0])]

    def pouring_into(self, R):
        from cotton_candy.manipulation_categories import PouringIntoAction
        from cotton_candy.process_nodes import process_step
        obj, head = R["object"][0], R["destination"][0]
        arm = self.b.robot.right_arm
        tilt, grip_h = 1.2, 0.03
        half = self._half(obj)
        kg = R["amount"][0]

        def pour():
            self.b.events.append((self.b.process.time_s, ["poured-into", R["amount"][1], R["destination"][1]],
                                  self.r.atoms(self.tracked)))
            self.b.process.pour_sugar(kg)
        return [PouringIntoAction(arm, head.root, standoff=(2 * half - grip_h) * math.sin(tilt), pour_height=0.24,
                                  tilt_angle=tilt, lift_from=self.b.grip[id(obj)],
                                  may_touch=[self.b.machine.floss_pan.root, self.b.world.get_body_by_name("FlossBubble")]),
                process_step(pour)]

    def putting_down(self, R):
        from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
        from cotton_candy.manipulation_categories import PuttingDownAction
        arm = self.b.robot.right_arm
        obj = R["object"][0]
        par = self.b.parent.get(id(obj)) if R["destination"][1].startswith("home-of-") else None
        return [ParkArmsAction([arm]), PuttingDownAction(obj, R["destination"][0], new_parent=par),
                ParkArmsAction(self.b.robot.all_arms)]


# ---------------------------------------------------------------------------------------------------- interpreter
class Interpreter:
    def __init__(self, lib, booth, attach=None):
        self.lib, self.b = lib, booth
        self.reader = StateReader(booth)
        self.climb = Climb(lib, booth)
        self.real = Realiser(booth, self.reader)
        self.attach = attach
        self.episode, self.path, self.protections = [], [], []
        self.tracked = [v for c in booth.types.values() if c is not booth.types["cotton-candy-machine"]
                        for v in booth.world.get_semantic_annotations_by_type(c)]
        self.real.tracked = self.tracked
        self.after = {}                 # scenario hooks: tag -> function run after that step (disturbances)
        self.listeners = []             # called with every finished episode node (cramera episode source)
        self.handlers = []              # dynamic handler stack of with-failure-handling (innermost last)
        self._handled = set()           # failures being / already handled (never re-read as new signals)
        self.amount_override = []       # scenario: amounts the recipe servant yields first (e.g. a near-empty carton)
        self.real.interp = self
        self.climb.override = self.amount_override

    # -- plans
    def call_plan(self, name, args=None):
        params = self.lib.params[name]
        env = {}
        for k, (pn, ptype) in enumerate(params):
            if args and pn in args:
                env["?" + pn] = args[pn]
            elif ptype == "arm":
                arm = self.b.robot.right_arm
                env["?" + pn] = (arm, "right-arm", dict(servant="robot-model", status="recorded"))
            else:
                env["?" + pn] = self.climb.resolve(["a", ptype], env)
        ps = self.lib.plans[name]
        pre = ps.get(":pre", [None, None])[1]                               # plan :pre (C facet), where observable
        if pre is not None:
            now = self.reader.atoms(self.tracked)
            for c in (pre[1:] if isinstance(pre, list) and pre and pre[0] == "and" else [pre]):
                c = subst_sym(c, env)
                if isinstance(c, list) and c and c[0] == "at" and not G.holds(c, now):   # a location: achieve it
                    cands = [f for k, f in G.refine(["achieve", c], self.lib.acts) if k == "action"]
                    if cands:
                        self.note(f"{name}: precondition {G.show(c)} -> achieve by {G.show(cands[0])}")
                        self.path.append(f"pre-{name}")
                        try:
                            self.perform(cands[0], env)
                        finally:
                            self.path.pop()
                        now = self.reader.atoms(self.tracked)
                        continue
                if isinstance(c, list) and c and c[0] in OBSERVABLE and not G.holds(c, now):
                    self.note(f"{name}: precondition {G.show(c)} does not hold -- not started")
                    raise KernelFailure("precondition-failed", f"{name}: {G.show(c)}")
        self.path.append(name)
        try:
            for c in ps.get(":body", [None])[1:]:
                self.run(c, env)
        finally:
            self.path.pop()
        succ = ps.get(":succ", [None, None])[1]
        if succ is not None:
            now = self.reader.atoms(self.tracked)
            parts = succ[1:] if isinstance(succ, list) and succ and succ[0] == "and" else [succ]
            res = [(G.show(subst_sym(c, env)), G.holds(subst_sym(c, env), now)) for c in parts
                   if isinstance(c, list) and c and c[0] in OBSERVABLE]
            if res:
                self.note(f"{name} :succ " + ", ".join(f"{c} {'holds' if ok else 'DOES NOT hold'}" for c, ok in res))
        return env

    def run(self, x, env):
        if not isinstance(x, list) or not x:
            return
        h = x[0]
        if h == "seq":
            for y in x[1:]:
                self.run(y, env)
        elif h == ":tag":
            self.path.append(x[1])
            try:
                self.run(x[2], env)
            finally:
                self.path.pop()
            if x[1] in self.after:
                self.after.pop(x[1])()
        elif h == "perform":
            self.perform(x[1], env)
        elif h == "perform-plan":
            args = {pn: env["?" + a[1:]] if isinstance(a, str) and a.startswith("?") else self.climb.resolve(a, env)
                    for (pn, _), a in zip(self.lib.params[x[1]], x[2:])}       # positional; designators climbed
            self.call_plan(x[1], args)
        elif h == "evap-protect":                     # run the body; the tail always runs after it (protection)
            try:
                self.run(x[1], env)
            finally:
                self.run(x[2], env)
        elif h == "with-failure-handling":
            for attempt in range(3):
                self.handlers.append(x[1])
                try:
                    for y in x[2:]:
                        self.run(y, env)
                    return
                except KernelFailure as f:
                    self.handlers.pop()
                    clause = next((c for c in x[1] if self.lib.failure_is_a(f.kind, c[0])), None)
                    if clause is None:
                        raise
                    self.note(f"handled {f.kind} ({clause[0]})")
                    self._handled.add(id(f))
                    outcome = clause[-1][0] if isinstance(clause[-1], list) and clause[-1] else None
                    for y in clause[2:]:
                        if isinstance(y, list) and y and y[0] in ("retry", "continue"):
                            continue
                        self.run(y, env)
                    if outcome == "continue":
                        return
                    continue
                finally:
                    if self.handlers and self.handlers[-1] is x[1]:
                        self.handlers.pop()
            raise KernelFailure("goal-unachievable", "retries exhausted")
        elif h == "protect":
            self.protections.append(x[1])
        elif h == "wait-for":
            c = x[1]
            if isinstance(c, list) and c and c[0] == "elapsed":
                self.b.process.advance(10.0)
        elif h == "achieve" and isinstance(x[1], list) and any(isinstance(a, list) and a and a[0] == "each"
                                                               for a in x[1][1:]):
            # (achieve (at (each tool) (its destination))): one sub-goal per tracked object with a known belonging
            # place; an object a customer holds belongs with the customer now (belonging norm, D7)
            now = self.reader.atoms(self.tracked)
            for obj in self.tracked:
                s_ = self.b.sym(obj)
                if id(obj) not in self.b.home:
                    continue
                if any(a[0] == "holds" and a[2] == s_ for a in now):
                    self.note(f"{s_}: with the customer -- belongs there now (belonging norm), not returned")
                    continue
                sub = [x[1][0], s_, "home-of-" + s_]
                if G.holds(sub, now):
                    self.note(f"skip: {G.show(sub)} holds")
                    continue
                self.perform(["an", "action", ["type", "putting-down"], ["object", ["the", "object", ["tag", s_]]],
                              ["destination", ["its", "destination"]]], env)
        elif h == "achieve":
            phi = subst_sym(x[1], env)
            if G.holds(phi, self.reader.atoms(self.tracked)):
                self.note(f"skip: {G.show(phi)} holds")
                return
            cands = [f for k, f in G.refine(["achieve", x[1]], self.lib.acts) if k == "action"]
            if not cands:
                raise KernelFailure("goal-unachievable", f"no refinement for {G.show(x[1])}")
            self.perform(cands[0], env)

    def _emit(self, node):
        self.episode.append(node)
        for f in self.listeners:
            f(node)

    # -- warrant (KR3) and pre-act verdict (D4)
    def predict(self, t, R):
        """Emulate a process-driven step on a copy of the floss machine model: does it reach its condition, or does
        a microtheory signal come first? (the copy shares nothing that advance() mutates)"""
        import copy
        if t != "monitoring-process" or "until" not in R:
            return None
        p = copy.copy(self.b.process)
        until, waited, prev = R["until"][1], 0.0, p.phase.value
        saved = self.b.process
        self.b.process = p                          # the reader looks at the copy while emulating
        try:
            while waited < 900.0:
                if G.holds(until, self.reader.atoms(self.tracked)):
                    return dict(prediction=f"{G.show(until)} after {waited:.0f} s", predicted_failure=None)
                p.advance(0.5)
                waited += 0.5
                if p.phase.value == "running_empty" and prev != "running_empty":
                    return dict(prediction=f"head-running-empty after {waited:.0f} s",
                                predicted_failure="head-running-empty")
                prev = p.phase.value
            return dict(prediction="condition not reached within 900 s", predicted_failure="phase-not-reached")
        finally:
            self.b.process = saved

    def handled_here(self, kind):
        for clauses in reversed(self.handlers):
            c = next((c for c in clauses if self.lib.failure_is_a(kind, c[0])), None)
            if c is not None:
                return "continue" if isinstance(c[-1], list) and c[-1] and c[-1][0] == "continue" else "repair"
        return None

    def assess(self, t, R, goal, d):
        statuses = {k: v[2].get("status") for k, v in R.items()}
        weak = sorted(k for k, st in statuses.items() if st in ("commonsense", "assumed"))
        assumed = sorted(k for k, st in statuses.items() if st == "assumed")
        model_only = [p for p in (goal[1] if goal else []) if p.former == "achieve" and isinstance(p.phi, list)
                      and p.phi and p.phi[0] in MODEL_ONLY]
        pred = self.predict(t, R)
        if weak or model_only:
            warrant = "plausible"
        elif pred is not None and pred["predicted_failure"] is None:
            warrant = "rational"                    # justified + the emulation predicts success
        else:
            warrant = "justified"
        why = ([f"{', '.join(weak)}: common sense / assumed"] if weak else []) + \
              ([f"model-only goal {G.show(model_only[0].phi)}"] if model_only else [])
        if pred is not None and pred["predicted_failure"]:
            h = self.handled_here(pred["predicted_failure"])
            verdict = (f"act-now: predicted {pred['predicted_failure']} is expected here (continue)" if h == "continue"
                       else f"repair-first: predicted {pred['predicted_failure']}, signalled before acting" if h
                       else f"deliberate-longer: predicted {pred['predicted_failure']} and no handler in scope")
        elif assumed:
            verdict = f"probe-first recommended ({', '.join(assumed)} assumed) -- no probe in the kinematic booth: act"
        else:
            verdict = "act-now"
        out = dict(warrant=warrant, warrant_why="; ".join(why), preact=verdict)
        if pred is not None:
            out["prediction"] = pred["prediction"]
        return out

    def signal(self, kind, description):
        """A failure description signalled by a part of the system (Q2). The innermost handler whose failure class
        subsumes it decides: (continue) -> the signal was the expected event, the signalling action RESUMES;
        any other handler -> unwind to it (raise). No handler -> raise to the plan's caller."""
        for clauses in reversed(self.handlers):
            c = next((c for c in clauses if self.lib.failure_is_a(kind, c[0])), None)
            if c is None:
                continue
            if isinstance(c[-1], list) and c[-1] and c[-1][0] == "continue":
                self.note(f"signal {kind}: expected here ({c[0]} -> continue)")
                return
            break
        raise KernelFailure(kind, description)

    def note(self, msg):
        self._emit(dict(path="/".join(self.path), note=msg, t=round(self.b.process.time_s, 1)))
        print("   ", "/".join(self.path), msg, flush=True)

    # -- the D10 cycle
    def perform(self, d, env):
        t = next(c[1] for c in d[2:] if isinstance(c, list) and c and c[0] == "type")
        node = dict(path="/".join(self.path), designator=G.show(d), schema=t, t0=round(self.b.process.time_s, 1),
                    wall0=time.time())
        R = {}
        loc = dict(env)
        for c in d[2:]:                                                     # 3. climb
            if isinstance(c, list) and c and c[0] != "type":
                if c[0] == "destination" and "object" in R:
                    loc["_object"] = R["object"]
                R[c[0]] = self.climb.resolve(c[1], loc, c[0])
        if "arm" not in R and t in ("transporting", "pressing-button", "turning", "gathering", "wrapping",
                                    "handing-over", "wiping"):
            R["arm"] = (self.b.robot.right_arm, "right-arm", dict(servant="robot-model", status="recorded"))
        node["bindings"] = {k: dict(symbol=v[1], **{kk: vv for kk, vv in v[2].items()}) for k, v in R.items()}
        sym_d = d[:2] + [c if not (isinstance(c, list) and c and c[0] in R) else [c[0], R[c[0]][1]] for c in d[2:]]
        if "arm" in R and not any(isinstance(c, list) and c and c[0] == "arm" for c in d[2:]):
            sym_d = sym_d + [["arm", R["arm"][1]]]
        goal = G.goal_of(sym_d, self.lib.acts)                              # 1. goal (perform -> goal)
        node["goal"] = [G.show(p.form()) for p in goal[1]] if goal else []
        before = self.reader.atoms(self.tracked)
        ach = [p for p in goal[1] if p.former == "achieve" and not G.is_var(p.phi)] if goal else []
        if ach and all(G.holds(p.phi, before) for p in ach):                # 2. skip
            node.update(verdict="skipped: goal holds", t1=node["t0"])
            self._emit(node)
            print("   ", node["path"], t, "skipped (goal holds)", flush=True)
            return
        for p in (goal[1] if goal else []):                                 # 4. gate
            if p.former == "prevent" and p.qual == ":while" and G.holds(p.arg, before):
                node.update(verdict=f"refused by the gate: {G.show(p.form())}")
                self._emit(node)
                raise KernelFailure("sugar-poured-into-spinning-head" if p.phi[0] == "poured-into" else
                                    "closing-event-violation", node["verdict"])
        pre = self.lib.acts.get(t, {}).get(":pre", [None, None])[1]   # schema :pre (C facet): a location the
        for c in (pre[1:] if isinstance(pre, list) and pre and pre[0] == "and" else ([pre] if pre else [])):
            c = subst_sym(c, loc)                                          # robot must be at is ACHIEVED by
            if isinstance(c, list) and c and c[0] == "at" and not G.holds(c, before):   # refinement (D10)
                cands = [f for k, f in G.refine(["achieve", c], self.lib.acts) if k == "action"]
                if not cands:
                    raise KernelFailure("precondition-failed", f"{t}: {G.show(c)} (no refinement)")
                self.note(f"{t}: precondition {G.show(c)} -> achieve by {G.show(cands[0])}")
                self.path.append(f"pre-{t}")
                try:
                    self.perform(cands[0], env)
                finally:
                    self.path.pop()
                before = self.reader.atoms(self.tracked)
        node["gate"] = "admitted"
        node.update(self.assess(t, R, goal, d))                              # warrant + pre-act verdict (KR3, D4)
        if node["preact"].startswith("repair-first"):                       # don't run into a predicted failure
            kind = node["preact"].split("predicted ")[1].split(",")[0]
            node.update(verdict=f"pre-empted: {kind} predicted", t1=node["t0"])
            self._emit(node)
            print("   ", node["path"], t, node["verdict"], f"[{node['warrant']}; {node['preact']}]", flush=True)
            self.signal(kind, f"predicted by emulation: {node.get('prediction')}")
        from coraplex.plans.factories import sequential
        self.b.events.clear()
        try:                                                                # 5. realise
            seq = sequential(self.real.nodes(t, R), context=self.b.context)
            if self.attach is not None:
                self.attach(seq.plan)
            seq.perform()
        except Exception as e:                                              # noqa: BLE001
            inner = e
            while inner is not None and not (isinstance(inner, KernelFailure) and id(inner) not in self._handled):
                inner = inner.__cause__ or inner.__context__       # (a failure being handled is only context)
            if isinstance(inner, KernelFailure):                            # a signal from inside (Q2)
                node.update(verdict=f"interrupted: {inner.kind}", t1=round(self.b.process.time_s, 1))
                self._emit(node)
                raise inner
            kind = {"SugarPouredIntoSpinningHead": "sugar-poured-into-spinning-head",
                    "PhaseNotReached": "phase-not-reached"}.get(type(e).__name__, "manipulation-failure")
            node.update(verdict=f"failed: {type(e).__name__}: {e}"[:300], t1=round(self.b.process.time_s, 1))
            self._emit(node)
            raise KernelFailure(kind, str(e)[:200]) from e
        after = self.reader.atoms(self.tracked)                             # 6. verdict on the trajectory
        traj = [(node["t0"], before)] + [(te, st + [ev]) for te, ev, st in self.b.events] + \
               [(self.b.process.time_s, after)]
        checkable = (goal[0], [p for p in goal[1] if not (isinstance(p.phi, list) and p.phi and p.phi[0] in MODEL_ONLY)])
        ok, bad = G.check(checkable, traj) if goal else (True, [])
        node.update(t1=round(self.b.process.time_s, 1), wall_s=round(time.time() - node.pop("wall0"), 1),
                    model_only=[G.show(p.form()) for p in goal[1] if p not in checkable[1]] if goal else [],
                    verdict="goal achieved" if ok else "goal violated",
                    violations=[(G.show(p.form()), tt, w) for p, tt, w in bad], state_after=[G.show(a) for a in after])
        self._emit(node)
        print("   ", node["path"], t, node["verdict"], [v[0] for v in node["violations"]],
              f"[{node.get('warrant')}; {node.get('preact')}]", flush=True)
        if not ok:
            raise KernelFailure("goal-not-achieved", "; ".join(v[0] for v in node["violations"]))


def subst_sym(x, env):
    if isinstance(x, list):
        return [subst_sym(y, env) for y in x]
    return env[x][1] if isinstance(x, str) and x in env else x


def save_episode(interp, name, out_dir=os.path.join(HERE, "episodes")):
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, f"{name}.json")
    json.dump(interp.episode, open(p, "w"), indent=1, default=str)
    return p
