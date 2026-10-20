"""
A PR2 runs a shift at a fairground cotton candy booth, watched in cramera.

The booth, the floss machine and the tools come from the CottonCandyTwin's layout model and parameter register
(``cotton_candy.booth_world``); the shift is a sequence of top-level action designators, each a composition of
manipulation action categories (``cotton_candy.actions``): fill the stopped spinner head from the Flossugar carton,
start the machine, sell two portions (make and hand over), shut down with the burn-out, and clean.

The cotton candy production ontology, generated from the scene graph and linked to its semantic annotations, is
registered in cramera's query panel together with its competency questions (``cotton_candy.competency_questions``);
the live questions read the world and the machine's process while the shift runs.

Run (viewer: ``cramera`` at http://localhost:8711, then choose Live):

    cram/run.sh cramera-live cram/demo.py                             # the whole shift
    COTTON_CANDY_PLAN=serve cram/run.sh cramera-live cram/demo.py     # make one portion, hand it to the customer
    COTTON_CANDY_PLAN=generalized cram/run.sh cramera-live cram/demo.py   # the generalized plan, two orders

Collision avoidance is off for this kinematic run: the PR2's collision buffers (0.05-0.20 m) exceed the clearances
of the human-scale machine (controls under the pan overhang, reaching over the 0.66 m pan); coraplex's per-motion
collision allowances do not lift the execution environment's avoidance tasks. The base is held at its stations by
the designators' motions, and the twin's checks C14/C15 verify that the parked robot fits at every station.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import StrEnum

from typing_extensions import Optional

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import ExecutionType, VisualizationBackend
from coraplex.demonstrations import RobotDemonstration
from coraplex.plans.factories import sequential
from coraplex.plans.plan_node import PlanNode
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
from cotton_candy.recipes import Flavour
from cotton_candy.competency_questions import CottonCandyKnowledgeSource
from cotton_candy.ontology.production import CottonCandyProductionOntology, OntologyBuilder
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
    The booth's shift as a robot demonstration with the cramera viewer.
    """

    used_robot: type = PR2
    """
    The robot that operates the booth.
    """

    default_visualization_backend: VisualizationBackend = VisualizationBackend.CRAMERA
    """
    The browser viewer.
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

    process: Optional[FlossMachineProcess] = field(default=None, init=False)
    """
    The machine's process model.
    """

    ontology: Optional[CottonCandyProductionOntology] = field(default=None, init=False)
    """
    The production ontology generated from the scene graph.
    """

    def build_simulated_world(self) -> World:
        return BoothWorldBuilder(robot_type=self.used_robot).build()

    def is_scene_populated(self, world: World) -> bool:
        return bool(world.get_semantic_annotations_by_type(CottonCandyMachine))

    def populate_scene(self, world: World) -> None:
        """
        The booth world is complete when it is built.
        """

    def build_context(self, world: World) -> Context:
        robot = world.get_semantic_annotations_by_type(self.used_robot)[0]
        context = Context(world, robot, sampling_seed=0)
        machine = world.get_semantic_annotations_by_type(CottonCandyMachine)[0]
        self.process = FlossMachineProcess(machine, FlossMachineTimings.from_twin_register(TwinModule.PARAMS.load()))
        self.ontology = OntologyBuilder(world, context, self.process).build()
        self._register_knowledge(world)
        return context

    def _register_knowledge(self, world: World) -> None:
        """
        Offer the ontology and its competency questions in cramera's query panel.
        """
        provider = getattr(self.visualization, "provider", None)
        bridge = getattr(provider, "bridge", None)
        if bridge is None:
            return
        CottonCandyKnowledgeSource(self.ontology, self.process, world).register_on(bridge)

    plan_kind: str = field(default_factory=lambda: os.environ.get("COTTON_CANDY_PLAN", "shift"))
    """
    ``shift`` (the whole shift), ``serve`` (make cotton candy and hand it to the customer, from a cold machine) or
    ``generalized`` (the generalized plan: the candy ordered is made and handed over from whatever state it is in;
    two orders, the second reusing the running machine).
    """

    def run(self) -> World:
        if self.plan_kind != "generalized":
            return super().run()
        from coraplex.execution_environment import ExecutionEnvironment

        from cotton_candy.universal_plan import make_and_hand_over

        try:
            world = self.acquire_world()
            context = self.build_context(world)
            plan = make_and_hand_over(context, self.process, self.ontology.materials)
            if self.visualization is not None:
                plan.on_plan = self.visualization.attach_plan
            with ExecutionEnvironment(execution_type=self.execution_type,
                                      collision_avoidance=self.collision_avoidance):
                for order in range(self.portions):
                    self.process.new_order(Flavour.RASPBERRY.value, ordered_by="Customer")
                    plan.perform()
                    print(f"order {order + 1}: {' -> '.join(plan.trace)}", flush=True)
                    plan.trace.clear()
        finally:
            self.tear_down()
        return world

    def build_plan(self, context: Context) -> PlanNode:
        world = context.world
        if self.plan_kind == "serve":
            return self._serve_plan(context)
        one = lambda annotation: world.get_semantic_annotations_by_type(annotation)[0]
        machine, arm = one(CottonCandyMachine), context.robot.right_arm
        sticks = world.get_semantic_annotations_by_type(CandyStick)
        stations = {station: station.pose(world.root) for station in RobotStation}
        shift = [
            FillSpinnerHeadAction(machine, self.process, one(SugarCarton), arm, stations[RobotStation.MACHINE],
                                  stations[RobotStation.MACHINE_CLOSE]),
            StartFlossMachineAction(machine, self.process, arm),
        ]
        portions = min(self.portions, len(sticks))
        shift += [
            SellCottonCandyAction(machine, self.process, sticks[i], one(SugarCarton), one(HandoverZone), arm,
                                  stations[RobotStation.SERVING], stations[RobotStation.MACHINE],
                                  stations[RobotStation.MACHINE_CLOSE], refill_first=refill)
            for i, refill in enumerate(project_refills(self.process, portions))
        ]
        shift += [
            ShutDownFlossMachineAction(machine, self.process, arm),
            CleanFlossMachineAction(machine, self.process, one(Sponge), arm),
        ]
        return sequential(shift, context=context).plan

    def _serve_plan(self, context: Context) -> PlanNode:
        """
        :return: The plan that makes one portion and hands it to the customer.
        """
        world = context.world
        one = lambda annotation: world.get_semantic_annotations_by_type(annotation)[0]
        return sequential(
            [
                MakeAndServeCottonCandyAction(
                    one(CottonCandyMachine), self.process, one(CandyStick), one(SugarCarton), one(HandoverZone),
                    one(Human), context.robot.right_arm, RobotStation.SERVING.pose(world.root),
                    RobotStation.MACHINE.pose(world.root), RobotStation.MACHINE_CLOSE.pose(world.root),
                )
            ],
            context=context,
        ).plan


class HoldOption(StrEnum):
    """
    The environment variable that keeps the demo serving the viewer after the shift, so the competency questions
    can still be asked of the live world (``COTTON_CANDY_HOLD=1``; stop with Ctrl-C).
    """

    VARIABLE = "COTTON_CANDY_HOLD"


def main(execution_type: ExecutionType = ExecutionType.KINEMATICALLY_SIMULATED) -> CottonCandyBoothDemonstration:
    demonstration = CottonCandyBoothDemonstration(execution_type=execution_type)
    hold = os.environ.get(HoldOption.VARIABLE, "0") == "1"
    if hold:
        demonstration.tear_down = lambda: None      # keep the viewer's world after the plan
    demonstration.run()
    process = demonstration.process
    print(f"shift done: {process.portions_served} portions, machine {process.phase.value}, t = {process.time_s:.0f} s",
          flush=True)
    while hold:
        time.sleep(1.0)
    return demonstration


if __name__ == "__main__":
    main()
