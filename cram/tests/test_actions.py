"""
Tests of the cotton candy booth world, the floss machine process and the top-level action designators.
"""

from __future__ import annotations

import pytest

from coraplex.datastructures.dataclasses import Context
from coraplex.plans.factories import sequential
from krrood.entity_query_language.factories import evaluate_condition
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.world_description.world_entity import Body

from cotton_candy.actions import (
    project_refills,
    CleanFlossMachineAction,
    FillSpinnerHeadAction,
    MakeCottonCandyAction,
    PrepareFlossMachineAction,
    SellCottonCandyAction,
    ShutDownFlossMachineAction,
    StartFlossMachineAction,
    StopFlossMachineAction,
)
from cotton_candy.manipulation_categories import ManipulationActionCategory as C, PressingButtonAction, category_profile
from cotton_candy.booth_world import BoothWorldBuilder, RobotStation, TwinModule
from cotton_candy.process import (
    FlossMachinePhase,
    FlossMachineProcess,
    FlossMachineTimings,
    SugarPouredIntoSpinningHead,
)
from cotton_candy.semantic_annotations import (
    CandyStick,
    CottonCandyMachine,
    HandoverZone,
    Sponge,
    SugarCarton,
)


@pytest.fixture(scope="module")
def booth():
    """
    The booth world with a PR2 at the machine station, its context and the machine's process.
    """
    world = BoothWorldBuilder(machine_set_up=False).build()
    robot = world.get_semantic_annotations_by_type(PR2)[0]
    machine = world.get_semantic_annotations_by_type(CottonCandyMachine)[0]
    process = FlossMachineProcess(machine, FlossMachineTimings.from_twin_register(TwinModule.PARAMS.load()))
    return world, robot, Context(world, robot, sampling_seed=0), machine, process


@pytest.fixture(autouse=True)
def machine_off(booth):
    """
    Every test starts with the machine switched off, locked and at minimum heat.
    """
    machine = booth[3]
    for element in (machine.motor_switch, machine.heat_switch, machine.heat_control, *machine.lock_handles):
        set_fraction(element, 0.0)
    yield


def condition_holds(action, condition) -> bool:
    return bool(evaluate_condition(condition(action.bound_variables, action.context, action.designator_parameter)))


def set_fraction(element, fraction: float) -> None:
    limits = element.movable_joint.dof.limits
    element.movable_joint.position = limits.lower.position + fraction * (
        limits.upper.position - limits.lower.position
    )


# %% world


def test_booth_world_carries_the_machine_and_its_elements(booth):
    world, robot, context, machine, process = booth
    assert machine.motor_switch is not None and machine.heat_switch is not None
    assert len(machine.lock_handles) == 2
    assert not machine.motor_switch.is_on
    assert len(world.get_semantic_annotations_by_type(CandyStick)) == 3
    assert world.get_semantic_annotations_by_type(HandoverZone)


def test_sticks_have_a_floss_tip(booth):
    world, *_ = booth
    stick = world.get_semantic_annotations_by_type(CandyStick)[0]
    assert stick.get_tool_frame() is not stick.root


# %% process model


def test_process_follows_the_manual(booth):
    world, robot, context, machine, _ = booth
    process = FlossMachineProcess(machine)
    assert process.phase is FlossMachinePhase.OFF
    process.pour_sugar(0.05)
    set_fraction(machine.motor_switch, 1.0)
    assert process.phase is FlossMachinePhase.SPINNING
    with pytest.raises(SugarPouredIntoSpinningHead):
        process.pour_sugar(0.01)
    set_fraction(machine.heat_switch, 1.0)
    process.advance(process.timings.warm_up_s - 1.0)
    assert process.phase is FlossMachinePhase.WARMING_UP
    process.advance(2.0)
    assert process.phase is FlossMachinePhase.PRODUCING
    waited = process.advance_until_portion()
    assert waited == pytest.approx(60 * process.timings.portion_sugar_kg / (
        process.timings.output_rate_portions_per_min * process.timings.portion_sugar_kg), abs=2.0)
    set_fraction(machine.heat_switch, 0.0)
    set_fraction(machine.motor_switch, 0.0)
    assert process.phase is FlossMachinePhase.OFF


# %% designators: plans and conditions


def test_pressing_a_button_closes_the_gripper_pushes_and_lets_go(booth):
    world, robot, context, machine, process = booth
    action = PressingButtonAction(machine.motor_switch, robot.right_arm, 1.0)
    sequential([action], context)
    names = [type(node.designator).__name__ for node in action._action_plan.children]
    assert names == ["ParkArmsAction", "MoveGripperMotion", "GraspingAction", "TurnToMotion", "MoveGripperMotion",
                     "MoveToolCenterPointMotion"]


def test_top_level_designators_map_onto_manipulation_categories(booth):
    """
    The mapping table of cotton_candy.actions, read from the plans themselves.
    """
    world, robot, context, machine, process = booth
    arm = robot.right_arm
    one = lambda t: world.get_semantic_annotations_by_type(t)[0]
    expected = [
        (PrepareFlossMachineAction(machine, arm), [C.TURNING, C.TURNING]),
        (FillSpinnerHeadAction(machine, process, one(SugarCarton), arm, RobotStation.MACHINE.pose(world.root),
                               RobotStation.MACHINE_CLOSE.pose(world.root)),
         [C.TRANSPORTING, C.POURING, C.TRANSPORTING]),
        (StartFlossMachineAction(machine, process, arm),
         [C.PRESSING_BUTTON, C.MONITORING, C.PRESSING_BUTTON, C.TURNING, C.MONITORING, C.TURNING]),
        (MakeCottonCandyAction(machine, process, one(CandyStick), arm),
         [C.TRANSPORTING, C.MONITORING, C.GATHERING, C.WRAPPING]),
        (StopFlossMachineAction(machine, process, arm),
         [C.PRESSING_BUTTON, C.MONITORING, C.PRESSING_BUTTON, C.MONITORING]),
        (CleanFlossMachineAction(machine, process, one(Sponge), arm), [C.TRANSPORTING, C.WIPING, C.TRANSPORTING]),
    ]
    for action, categories in expected:
        sequential([action], context)
        assert category_profile(action) == categories, type(action).__name__


def test_fill_needs_a_stopped_head(booth):
    world, robot, context, machine, _ = booth
    process = FlossMachineProcess(machine)
    carton = world.get_semantic_annotations_by_type(SugarCarton)[0]
    action = FillSpinnerHeadAction(machine, process, carton, robot.right_arm, RobotStation.MACHINE.pose(world.root),
                                   RobotStation.MACHINE_CLOSE.pose(world.root))
    sequential([action], context)
    assert condition_holds(action, action.pre_condition)
    set_fraction(machine.motor_switch, 1.0)
    assert not condition_holds(action, action.pre_condition)
    set_fraction(machine.motor_switch, 0.0)


def test_start_needs_unlocked_handles_and_sugar(booth):
    world, robot, context, machine, _ = booth
    process = FlossMachineProcess(machine)
    action = StartFlossMachineAction(machine, process, robot.right_arm)
    sequential([action], context)
    assert not condition_holds(action, action.pre_condition)
    process.pour_sugar(0.05)
    for handle in machine.lock_handles:
        set_fraction(handle, 1.0)
    assert condition_holds(action, action.pre_condition)
    for handle in machine.lock_handles:
        set_fraction(handle, 0.0)


def test_prepare_post_condition_reads_the_handles(booth):
    world, robot, context, machine, process = booth
    action = PrepareFlossMachineAction(machine, robot.right_arm)
    sequential([action], context)
    assert not condition_holds(action, action.post_condition)
    for handle in machine.lock_handles:
        set_fraction(handle, 1.0)
    assert condition_holds(action, action.post_condition)
    for handle in machine.lock_handles:
        set_fraction(handle, 0.0)


@pytest.mark.parametrize("refill_needed", [True, False])
def test_selling_refills_only_when_the_head_runs_short(booth, refill_needed):
    world, robot, context, machine, _ = booth
    process = FlossMachineProcess(machine)
    stick = world.get_semantic_annotations_by_type(CandyStick)[0]
    action = SellCottonCandyAction(
        machine, process, stick,
        world.get_semantic_annotations_by_type(SugarCarton)[0],
        world.get_semantic_annotations_by_type(HandoverZone)[0],
        robot.right_arm,
        RobotStation.SERVING.pose(world.root),
        RobotStation.MACHINE.pose(world.root),
        RobotStation.MACHINE_CLOSE.pose(world.root),
        refill_first=refill_needed,
    )
    sequential([action], context)
    names = [type(node.designator).__name__ for node in action._action_plan.children]
    assert ("RefillSpinnerHeadAction" in names) is refill_needed
    assert names[-2:] == ["MakeCottonCandyAction", "ServeCottonCandyAction"]


def test_every_top_level_designator_builds_a_plan(booth):
    world, robot, context, machine, process = booth
    arm = robot.right_arm
    stick = world.get_semantic_annotations_by_type(CandyStick)[1]
    actions = [
        PrepareFlossMachineAction(machine, arm),
        StartFlossMachineAction(machine, process, arm),
        MakeCottonCandyAction(machine, process, stick, arm),
        StopFlossMachineAction(machine, process, arm),
        ShutDownFlossMachineAction(machine, process, arm),
        CleanFlossMachineAction(machine, process, world.get_semantic_annotations_by_type(Sponge)[0], arm),
    ]
    for action in actions:
        sequential([action], context)
        assert action._action_plan.children


def test_refill_projection_follows_the_sugar_budget(booth):
    process = FlossMachineProcess(booth[3])
    # the register: 60 g head x 0.9 = 54 g per fill, 20 g per portion
    assert project_refills(process, 5) == [False, False, True, False, True]   # 54 g per fill = 2 portions
    assert project_refills(process, 2, head_filled=False) == [True, False]
