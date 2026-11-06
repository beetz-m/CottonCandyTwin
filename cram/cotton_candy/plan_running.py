"""
Building and running the booth's plans on the kinematically simulated robot.

CRAM main from November 2026 (cram-env since 2026-11-06) runs a plan as one cramph statechart: the plan's actions are
nodes that create their steps when they join a statechart, a statechart context serves one executor, and there is no
shared plan ``Context`` any more. :class:`BoothContext` is the twin's replacement for the former coraplex ``Context``:
the world and the robot the designators are built for, with :meth:`BoothContext.expand` (build a plan without running
it, to read its steps) and :meth:`BoothContext.perform` (run it with a fresh executor). Collision avoidance stays off,
as under the former ``kinematically_simulated_robot`` (see ``demo.py``).
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, Callable, List, Optional

from coraplex.plans.context_extensions import RobotAccess, StatementGrounding
from coraplex.plans.executors import KinematicallySimulatedPlanExecutor
from cramph.composites import Sequence
from cramph.context import ContextExtension, StatechartContext
from cramph.node import StatechartNode
from cramph.statechart import Statechart
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.world import World


@dataclass
class BoothContext:
    """
    The world and the robot the booth's designators are built for and performed by.
    """

    world: World
    """
    The booth world.
    """

    robot: AbstractRobot
    """
    The robot operating the booth.
    """

    sampling_seed: int = 0
    """
    Seed for the locations the plans' actions sample, so a run repeats.
    """

    collision_avoidance: bool = False
    """
    Whether the robot avoids its surroundings and itself while it moves.
    """

    def extensions(self) -> List[ContextExtension]:
        """
        :return: The context extensions the booth's plans read.
        """
        return [RobotAccess(self.robot), StatementGrounding(sampling_seed=self.sampling_seed)]

    def executor(self) -> KinematicallySimulatedPlanExecutor:
        """
        :return: A new executor simulating plans kinematically in the booth world.
        """
        return KinematicallySimulatedPlanExecutor(
            StatechartContext.with_extensions(self.world, self.extensions()),
            collision_avoidance=self.collision_avoidance,
        )

    def expand(self, *nodes: StatechartNode) -> Sequence:
        """
        Build a plan of ``nodes`` without running it, so its steps can be read (the actions create their steps when
        they join the statechart).

        :param nodes: The plan's steps, in order. A node can be part of one statechart only.
        :return: The plan.
        """
        plan = Sequence(nodes=list(nodes))
        Statechart(context=self.executor().context).add_node(plan)
        return plan

    def perform(self, nodes: List[StatechartNode], attach: Optional[Callable[[StatechartNode], Any]] = None) -> Sequence:
        """
        Run ``nodes`` in order until all of them succeeded; a failed step raises.

        :param nodes: The plan's steps, in order.
        :param attach: Called with the plan before it runs (e.g. to show it in a viewer).
        :return: The plan that ran.
        """
        executor = self.executor()
        try:
            plan = Sequence(nodes=list(nodes))
            statechart = Statechart(context=executor.context)
            statechart.add_node(plan)
            if attach is not None:
                attach(plan)
            executor.compile(statechart)
            executor.execute()
        finally:
            executor.close()
        return plan
