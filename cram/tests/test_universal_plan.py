"""
The generalized make-and-hand-over plan: designators resolved against the candy belief and the booth, check-before-act
sub-goals selected PLANEX-style, executed kinematically from different states.
"""

from __future__ import annotations

import pytest

from coraplex.datastructures.dataclasses import Context
from coraplex.execution_environment import kinematically_simulated_robot
from coraplex.plans.factories import sequential
from krrood.entity_query_language.exceptions import MultipleSolutionFound
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.semantic_annotations.semantic_annotations import Human

from cotton_candy.actions import FillSpinnerHeadAction, FormPortionAction, StartFlossMachineAction
from cotton_candy.booth_world import BoothWorldBuilder, RobotStation, TwinModule
from cotton_candy.manipulation_categories import ApproachDirection, TransportingAction
from cotton_candy.ontology.production import OntologyBuilder
from cotton_candy.process import CandyStage, FlossMachineProcess, FlossMachineTimings
from cotton_candy.recipes import Flavour
from cotton_candy.semantic_annotations import CandyStick, CottonCandyMachine, SugarCarton
from cotton_candy.universal_plan import GoalUnachievable, make_and_hand_over


def fresh(flavour: Flavour = Flavour.RASPBERRY, customer: str | None = "Customer"):
    world = BoothWorldBuilder().build()
    robot = world.get_semantic_annotations_by_type(PR2)[0]
    machine = world.get_semantic_annotations_by_type(CottonCandyMachine)[0]
    process = FlossMachineProcess(machine, FlossMachineTimings.from_twin_register(TwinModule.PARAMS.load()))
    context = Context(world, robot, sampling_seed=0)
    materials = OntologyBuilder(world, context, process).build().materials
    process.candies.clear()
    process.new_order(flavour.value, ordered_by=customer)
    return world, robot, context, machine, process, make_and_hand_over(context, process, materials)


def execute(context, designators):
    with kinematically_simulated_robot:
        sequential(designators, context).perform()


def belief(plan):
    return plan.estimator.estimate(plan.the_candy())


def test_the_designators_resolve_against_belief_and_booth():
    world, robot, context, machine, process, plan = fresh()
    b = belief(plan)
    assert b.candy.order == 1 and b.stick.root.name.name == "CandyStick0"
    assert b.sugar.root.name.name == "SugarCarton" and b.customer.root.name.name == "Customer"
    assert "Allura Red (pink colour)" in [m.name for m in b.ingredients]


def test_cold_machine_achieves_every_sub_goal():
    world, robot, context, machine, process, plan = fresh()
    assert plan.projection(belief(plan)) == ["MACHINE-READY", "STICK-IN-HAND", "CANDY-FORMED", "CANDY-WRAPPED",
                                             "HANDED-OVER"]
    with kinematically_simulated_robot:
        final = plan.perform()
    assert final.delivered and plan.failures == []
    assert plan.trace == ["MACHINE-READY", "STICK-IN-HAND", "CANDY-FORMED", "HANDED-OVER"]


def test_interrupted_after_taking_the_stick_resumes_with_forming():
    world, robot, context, machine, process, plan = fresh()
    arm, carton = robot.right_arm, world.get_semantic_annotations_by_type(SugarCarton)[0]
    stick = world.get_semantic_annotations_by_type(CandyStick)[0]
    execute(context, [FillSpinnerHeadAction(machine, process, carton, arm, RobotStation.MACHINE.pose(world.root),
                                            RobotStation.MACHINE_CLOSE.pose(world.root)),
                      StartFlossMachineAction(machine, process, arm),
                      TransportingAction(stick, arm, ApproachDirection.TOWARDS_LEFT_WALL)])
    assert plan.select(belief(plan)).tag == "CANDY-FORMED"
    with kinematically_simulated_robot:
        assert plan.perform().delivered
    assert plan.trace[0] == "CANDY-FORMED"


def test_a_wrapped_candy_in_hand_is_only_handed_over():
    world, robot, context, machine, process, plan = fresh()
    arm, carton = robot.right_arm, world.get_semantic_annotations_by_type(SugarCarton)[0]
    stick = world.get_semantic_annotations_by_type(CandyStick)[0]
    execute(context, [FillSpinnerHeadAction(machine, process, carton, arm, RobotStation.MACHINE.pose(world.root),
                                            RobotStation.MACHINE_CLOSE.pose(world.root)),
                      StartFlossMachineAction(machine, process, arm),
                      TransportingAction(stick, arm, ApproachDirection.TOWARDS_LEFT_WALL),
                      FormPortionAction(machine, process, stick, arm)])
    assert process.candy.stage is CandyStage.WRAPPED
    assert plan.projection(belief(plan)) == ["HANDED-OVER"]
    with kinematically_simulated_robot:
        plan.perform()
    assert plan.trace == ["HANDED-OVER"]
    assert stick.root.parent_kinematic_structure_entity is world.get_semantic_annotations_by_type(Human)[0].root


def test_a_believed_portion_without_its_stick_in_hand_is_lost():
    world, robot, context, machine, process, plan = fresh()
    process.candy.stage, process.candy.stick = CandyStage.WRAPPED, "CandyStick2"
    b = belief(plan)
    assert b.stage is CandyStage.NONE and plan.select(b).tag == "MACHINE-READY"


def test_no_sugar_for_the_ordered_flavour_is_unachievable():
    world, robot, context, machine, process, plan = fresh(Flavour.BLUEBERRY)
    assert belief(plan).sugar is None
    with pytest.raises(GoalUnachievable):
        plan.select(belief(plan))


def test_two_open_orders_leave_the_candy_ambiguous():
    world, robot, context, machine, process, plan = fresh()
    process.new_order(Flavour.RASPBERRY.value)
    with pytest.raises(MultipleSolutionFound):
        plan.the_candy()


def test_a_second_order_gets_a_new_stick_and_skips_the_ready_machine():
    world, robot, context, machine, process, plan = fresh()
    with kinematically_simulated_robot:
        plan.perform()
    process.new_order(Flavour.RASPBERRY.value, ordered_by="Customer")
    b = belief(plan)
    assert b.stick.root.name.name == "CandyStick1" and plan.select(b).tag == "STICK-IN-HAND"
    plan.trace.clear()
    with kinematically_simulated_robot:
        assert plan.perform().delivered
    assert plan.trace == ["STICK-IN-HAND", "CANDY-FORMED", "HANDED-OVER"]


def test_goal_already_holding_means_nothing_to_do():
    world, robot, context, machine, process, plan = fresh()
    with kinematically_simulated_robot:
        plan.perform()
    plan.trace.clear()
    with kinematically_simulated_robot:
        plan.perform()
    assert plan.trace == []
