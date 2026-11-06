"""
A PR2 runs a shift at a fairground cotton candy booth.

The booth, the floss machine and the tools come from the CottonCandyTwin's layout model and parameter register
(``cotton_candy.booth_world``); the shift is a sequence of top-level action designators, each a composition of
manipulation action categories (``cotton_candy.actions``): fill the stopped spinner head from the Flossugar carton,
start the machine, sell two portions (make and hand over), shut down with the burn-out, and clean.

The cotton candy production ontology is generated from the scene graph and linked to its semantic annotations; its
competency questions (``cotton_candy.competency_questions``) are answered by the tests
(``cram/tests/test_competency_questions.py``).

Run headless (CRAM main of 2026-11, cram-env):

    cram/run.sh python cram/demo.py                                   # the whole shift
    COTTON_CANDY_PLAN=serve cram/run.sh python cram/demo.py           # make one portion, hand it to the customer
    COTTON_CANDY_PLAN=generalized cram/run.sh python cram/demo.py     # the generalized plan, two orders
    COTTON_CANDY_PLAN=control cram/run.sh python cram/demo.py         # drive the generalized plan from a page
                                                                      # at http://127.0.0.1:8770 (cotton_candy.control)

Live viewing in CRAMERA is not available since 2026-11-06: CRAM main removed the cramera package and cramera-live,
and the stand-alone cramera stack (~/cramera) runs the CRAM of 2026-10-27, whose plan API this code no longer uses.

Collision avoidance is off for this kinematic run: the PR2's collision buffers (0.05-0.20 m) exceed the clearances
of the human-scale machine (controls under the pan overhang, reaching over the 0.66 m pan). The base is held at its
stations by the designators' motions, and the twin's checks C14/C15 verify that the parked robot fits at every
station.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from typing_extensions import Any, List, Optional

from coraplex.demonstrations import RobotDemonstration
from cramph.composites import Sequence
from cramph.context import ContextExtension, StatechartContext
from cramph.statechart import Statechart
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.semantic_annotations.semantic_annotations import Human
from semantic_digital_twin.world import World

from cotton_candy.actions import (
    CleanFlossMachineAction,
    FillSpinnerHeadAction,
    MakeAndServeCottonCandyAction,
    SellCottonCandyAction,
    ShutDownFlossMachineAction,
    StartFlossMachineAction,
    project_refills,
)
from cotton_candy.booth_world import BoothWorldBuilder, RobotStation, TwinModule
from cotton_candy.ontology.production import CottonCandyProductionOntology, OntologyBuilder
from cotton_candy.plan_running import BoothContext
from cotton_candy.recipes import Flavour
from cotton_candy.process import FlossMachineProcess, FlossMachineTimings
from cotton_candy.semantic_annotations import (
    CandyStick,
    CottonCandyMachine,
    HandoverZone,
    Sponge,
    SugarCarton,
)


# %% the demonstration


@dataclass
class CottonCandyBoothDemonstration(RobotDemonstration):
    """
    The booth's shift as a robot demonstration, run headless.

    CRAM main builds a demonstration's world from a scene and a robot specification; the booth keeps its own builder
    (:class:`~cotton_candy.booth_world.BoothWorldBuilder`), so :meth:`build_simulated_world` replaces that path and the
    specifications are not used.
    """

    used_robot: type = PR2
    """
    The robot that operates the booth.
    """

    collision_avoidance: bool = False
    """
    Off for the kinematic run (see the module docstring).
    """

    event_segmentation: bool = False
    """
    No event segmentation in this demo.
    """

    portions: int = 2
    """
    How many portions are sold.
    """

    context: Optional[BoothContext] = field(default=None, init=False)
    """
    The world and the robot the designators are built for.
    """

    process: Optional[FlossMachineProcess] = field(default=None, init=False)
    """
    The machine's process model.
    """

    ontology: Optional[CottonCandyProductionOntology] = field(default=None, init=False)
    """
    The production ontology generated from the scene graph.
    """

    plan_kind: str = field(default_factory=lambda: os.environ.get("COTTON_CANDY_PLAN", "shift"))
    """
    ``shift`` (the whole shift), ``serve`` (make cotton candy and hand it to the customer, from a cold machine) or
    ``generalized`` (the generalized plan: the candy ordered is made and handed over from whatever state it is in;
    two orders, the second reusing the running machine) or ``control`` (the generalized plan, driven from the control
    page of :mod:`cotton_candy.control`: orders, changes to the booth, projection and execution on request).
    """

    # %% the world

    def scene_specification(self):
        raise NotImplementedError("the booth is built by BoothWorldBuilder, see build_simulated_world")

    def robot_specification(self):
        raise NotImplementedError("the robot is parked by BoothWorldBuilder, see build_simulated_world")

    def build_simulated_world(self) -> World:
        """
        Build the booth with the robot at the machine station, the machine's process and the production ontology.
        """
        world = BoothWorldBuilder(robot_type=self.used_robot).build()
        robot = world.get_semantic_annotations_by_type(self.used_robot)[0]
        self.context = BoothContext(world, robot, sampling_seed=0, collision_avoidance=self.collision_avoidance)
        machine = world.get_semantic_annotations_by_type(CottonCandyMachine)[0]
        self.process = FlossMachineProcess(machine, FlossMachineTimings.from_twin_register(TwinModule.PARAMS.load()))
        self.ontology = OntologyBuilder(world, self.context, self.process).build()
        return world

    def acquire_world(self) -> World:
        """
        The simulated booth, headless: no ROS session and no viewer are started (the booth's runs are kinematic).
        """
        return self.build_simulated_world()

    def is_scene_populated(self, world: World) -> bool:
        return bool(world.get_semantic_annotations_by_type(CottonCandyMachine))

    def populate_scene(self, world: World) -> None:
        """
        The booth world is complete when it is built.
        """

    def build_context_extensions(self, world: World) -> List[ContextExtension]:
        return self.context.extensions()

    # %% the plan

    def build_statechart(self, context: StatechartContext) -> Statechart:
        statechart = Statechart(context=context)
        statechart.add_node(Sequence(nodes=self.build_plan()))
        return statechart

    def run(self) -> World:
        if self.plan_kind not in ("generalized", "control"):
            return super().run()
        from cotton_candy.universal_plan import make_and_hand_over

        try:
            world = self.acquire_world()
            plan = make_and_hand_over(self.context, self.process, self.ontology.materials)
            if self.plan_kind == "control":
                from cotton_candy.control import PlanControl

                PlanControl(plan, attach_plan=plan.on_plan).serve_forever()
            for order in range(self.portions):
                self.process.new_order(Flavour.RASPBERRY.value, ordered_by="Customer")
                plan.perform()
                print(f"order {order + 1}: {' -> '.join(plan.trace)}", flush=True)
                plan.trace.clear()
        finally:
            self.tear_down()
        return world

    def build_plan(self) -> List[Any]:
        """
        :return: The top-level designators of the run, in order.
        """
        world, arm = self.context.world, self.context.robot.right_arm
        if self.plan_kind == "serve":
            return self._serve_plan()
        one = lambda annotation: world.get_semantic_annotations_by_type(annotation)[0]
        machine = one(CottonCandyMachine)
        sticks = world.get_semantic_annotations_by_type(CandyStick)
        stations = {station: station.pose(world.root) for station in RobotStation}
        shift = [
            FillSpinnerHeadAction(machine=machine, process=self.process, carton=one(SugarCarton), arm=arm,
                                  machine_station=stations[RobotStation.MACHINE],
                                  close_station=stations[RobotStation.MACHINE_CLOSE]),
            StartFlossMachineAction(machine=machine, process=self.process, arm=arm),
        ]
        portions = min(self.portions, len(sticks))
        shift += [
            SellCottonCandyAction(machine=machine, process=self.process, stick=sticks[i], carton=one(SugarCarton),
                                  handover=one(HandoverZone), arm=arm,
                                  serving_station=stations[RobotStation.SERVING],
                                  machine_station=stations[RobotStation.MACHINE],
                                  close_station=stations[RobotStation.MACHINE_CLOSE], refill_first=refill)
            for i, refill in enumerate(project_refills(self.process, portions))
        ]
        shift += [
            ShutDownFlossMachineAction(machine=machine, process=self.process, arm=arm),
            CleanFlossMachineAction(machine=machine, process=self.process, sponge=one(Sponge), arm=arm),
        ]
        return shift

    def _serve_plan(self) -> List[Any]:
        """
        :return: The plan that makes one portion and hands it to the customer.
        """
        world = self.context.world
        one = lambda annotation: world.get_semantic_annotations_by_type(annotation)[0]
        return [
            MakeAndServeCottonCandyAction(
                machine=one(CottonCandyMachine), process=self.process, stick=one(CandyStick), carton=one(SugarCarton),
                handover=one(HandoverZone), customer=one(Human), arm=self.context.robot.right_arm,
                serving_station=RobotStation.SERVING.pose(world.root),
                machine_station=RobotStation.MACHINE.pose(world.root),
                close_station=RobotStation.MACHINE_CLOSE.pose(world.root),
            )
        ]


def main() -> CottonCandyBoothDemonstration:
    demonstration = CottonCandyBoothDemonstration()
    demonstration.run()
    process = demonstration.process
    print(f"shift done: {process.portions_served} portions, machine {process.phase.value}, t = {process.time_s:.0f} s",
          flush=True)
    return demonstration


if __name__ == "__main__":
    main()
