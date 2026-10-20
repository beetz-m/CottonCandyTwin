"""
The make-and-serve plan, executed kinematically: from a cold machine to a customer holding a portion, and a second
customer served while the machine is still producing.
"""

from __future__ import annotations

import pytest

from coraplex.datastructures.dataclasses import Context
from coraplex.execution_environment import kinematically_simulated_robot
from coraplex.plans.factories import sequential
from krrood.entity_query_language.factories import evaluate_condition
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.semantic_annotations.semantic_annotations import Human

from cotton_candy.actions import MakeAndServeCottonCandyAction
from cotton_candy.booth_world import BoothWorldBuilder, RobotStation, TwinModule
from cotton_candy.process import FlossMachinePhase, FlossMachineProcess, FlossMachineTimings
from cotton_candy.semantic_annotations import CandyStick, CottonCandyMachine, HandoverZone, SugarCarton


@pytest.fixture(scope="module")
def booth():
    world = BoothWorldBuilder().build()
    robot = world.get_semantic_annotations_by_type(PR2)[0]
    machine = world.get_semantic_annotations_by_type(CottonCandyMachine)[0]
    process = FlossMachineProcess(machine, FlossMachineTimings.from_twin_register(TwinModule.PARAMS.load()))
    return world, robot, Context(world, robot, sampling_seed=0), machine, process


def make_and_serve(booth, stick_index: int) -> MakeAndServeCottonCandyAction:
    world, robot, context, machine, process = booth
    one = lambda t: world.get_semantic_annotations_by_type(t)[0]
    return MakeAndServeCottonCandyAction(
        machine, process, world.get_semantic_annotations_by_type(CandyStick)[stick_index], one(SugarCarton),
        one(HandoverZone), one(Human), robot.right_arm, RobotStation.SERVING.pose(world.root),
        RobotStation.MACHINE.pose(world.root), RobotStation.MACHINE_CLOSE.pose(world.root),
    )


def steps_of(action) -> list:
    return [type(node.designator).__name__ for node in action._action_plan.children]


def test_cold_machine_is_filled_and_started_first(booth):
    action = make_and_serve(booth, 0)
    sequential([action], booth[2])
    assert steps_of(action) == ["FillSpinnerHeadAction", "StartFlossMachineAction", "MakeCottonCandyAction",
                                "ServeCottonCandyAction"]


def test_first_customer_gets_a_portion_from_a_cold_machine(booth):
    world, robot, context, machine, process = booth
    action = make_and_serve(booth, 0)
    plan = sequential([action], context)
    with kinematically_simulated_robot:
        plan.perform()
    customer = world.get_semantic_annotations_by_type(Human)[0]
    assert action.stick.root.parent_kinematic_structure_entity is customer.root
    assert process.portions_served == 1 and process.phase is FlossMachinePhase.PRODUCING
    assert evaluate_condition(action.post_condition(action.bound_variables, action.context,
                                                    action.designator_parameter))


def test_second_customer_is_served_without_restarting(booth):
    world, robot, context, machine, process = booth
    action = make_and_serve(booth, 1)
    sequential([action], context)
    assert steps_of(action) == ["MakeCottonCandyAction", "ServeCottonCandyAction"]
    plan = sequential([make_and_serve(booth, 1)], context)
    with kinematically_simulated_robot:
        plan.perform()
    assert process.portions_served == 2
