"""
Action designators for a robot that operates a cotton candy booth.

The top-level designators follow the operating procedure of the reference machine's manual (twin register,
``GM_MAN_EXP`` pp. 5, 8-13): prepare the machine, fill the stopped spinner head, start it (motor, wait 10 s, heat,
maximum heat until floss appears, then back to the operating setting), make and serve portions, refill, shut down
with the burn-out, and clean. Each top-level designator composes coraplex core actions and motions; the floss
machine's behaviour (phases, sugar, floss) comes from :class:`~cotton_candy.process.FlossMachineProcess`.

Top level:

* :class:`PrepareFlossMachineAction`
* :class:`FillSpinnerHeadAction`
* :class:`StartFlossMachineAction`
* :class:`MakeCottonCandyAction`
* :class:`ServeCottonCandyAction`
* :class:`SellCottonCandyAction`
* :class:`RefillSpinnerHeadAction`
* :class:`StopFlossMachineAction`
* :class:`ShutDownFlossMachineAction`
* :class:`CleanFlossMachineAction`
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from typing_extensions import Any, Dict, Optional, Union

from giskardpy.motion_statechart.data_types import DefaultWeights
from giskardpy.motion_statechart.goals.open_close import Open
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.factories import ConditionType, and_, variable_from

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import ToolPathSegmentKind, WipingTechnique
from coraplex.plans.factories import code, sequential
from coraplex.plans.plan_node import PlanNode
from coraplex.querying.predicates import GripperIsFree, GripperIsNotFree
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.robot_plans.actions.composite.tool_based import PouringAction, ToolMotionAction, WipingAction
from coraplex.robot_plans.actions.composite.tool_paths import ToolPath, ToolPathSegment
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.pick_up import GraspingAction, PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction, ParkArmsAction
from coraplex.robot_plans.motions.base import BaseMotion
from coraplex.robot_plans.motions.container import ClosingMotion, OpeningMotion
from coraplex.robot_plans.motions.gripper import MoveGripperMotion, MoveToolCenterPointMotion
from semantic_digital_twin.datastructures.definitions import GripperState, TorsoState
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.world_entity import Body

from cotton_candy.process import FlossMachinePhase, FlossMachineProcess
from cotton_candy.semantic_annotations import (
    CandyStick,
    ControlKnob,
    CottonCandyMachine,
    HandoverZone,
    OperatingElement,
    RockerSwitch,
    Sponge,
    SugarScoop,
    SugarTray,
)


# %% motions


@dataclass
class TurnToMotion(BaseMotion):
    """
    Turn a grasped operating element to a position of its joint, e.g. a knob to a heat setting.
    """

    object_part: Body
    """
    The body of the grasped element.
    """

    arm: Arm
    """
    The arm holding the element.
    """

    goal_position: float
    """
    The joint position to turn to.
    """

    def perform(self):
        return

    @property
    def _motion_chart(self):
        return Open(
            tip_link=self.arm.end_effector.tool_frame,
            environment_link=self.object_part,
            goal_joint_state=self.goal_position,
            mechanism_weight=DefaultWeights.WEIGHT_BELOW_COLLISION_AVOIDANCE,
        )


# %% operating the machine's elements


@dataclass
class OperateElementAction(ActionDescription):
    """
    Grasp an operating element (rocker, knob, lever), move it to a fraction of its travel and let go again.
    """

    element: OperatingElement
    """
    The element to operate.
    """

    arm: Arm
    """
    The arm that operates it.
    """

    travel_fraction: float
    """
    Where to move the element: 0 is the lower end of its joint range (OFF, LOCKED, minimum), 1 the upper end
    (ON, UNLOCKED, maximum).
    """

    release_clearance: float = 0.05
    """
    The gap in metres between element and gripper after letting go.
    """

    def _goal_position(self) -> float:
        limits = self.element.movable_joint.dof.limits
        return limits.lower.position + self.travel_fraction * (limits.upper.position - limits.lower.position)

    def _mechanism_motion(self) -> BaseMotion:
        if self.travel_fraction >= 0.999:
            return OpeningMotion(self.element.root, self.arm)
        if self.travel_fraction <= 0.001:
            return ClosingMotion(self.element.root, self.arm)
        return TurnToMotion(self.element.root, self.arm, self._goal_position())

    @property
    def _action_plan(self) -> PlanNode:
        grasp = GraspCandidate.from_body_origin(self.element)
        back_off = Pose.from_xyz_rpy(z=-self.release_clearance, reference_frame=self.arm.end_effector.tool_frame)
        return sequential(
            [
                GraspingAction(grasp, self.arm),
                self._mechanism_motion(),
                MoveGripperMotion(GripperState.OPEN, self.arm.end_effector, allow_gripper_collision=True),
                MoveToolCenterPointMotion(back_off, self.arm, allow_gripper_collision=True),
            ]
        )

    @staticmethod
    def pre_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The operating gripper has to be free.
        """
        return GripperIsFree(variables["arm"].end_effector)

    @staticmethod
    def post_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The element stands within 5 % of its travel at the requested position.
        """
        element = variable_from(kwargs["element"])
        return and_(
            element.travel_fraction > kwargs["travel_fraction"] - 0.05,
            element.travel_fraction < kwargs["travel_fraction"] + 0.05,
        )


@dataclass
class LetFlossMachineRunAction(ActionDescription):
    """
    Let the machine's process run: for a time, until a phase is reached, or until a portion of floss has collected.

    The plan advances the process model; with a real or Isaac Sim machine the same node waits for the machine's
    reported state instead.
    """

    process: FlossMachineProcess
    """
    The process of the machine.
    """

    seconds: float = 0.0
    """
    How long to let it run, if no phase or portion is waited for.
    """

    until_phase: Optional[FlossMachinePhase] = None
    """
    The phase to wait for, if any.
    """

    until_portion: bool = False
    """
    Whether to wait until one portion of floss has collected in the pan.
    """

    timeout_s: float = 300.0
    """
    The longest wait for a phase or a portion.
    """

    def _run(self) -> float:
        self.process.notice_switches()
        if self.until_phase is not None:
            return self.process.advance_until(self.until_phase, self.timeout_s)
        if self.until_portion:
            return self.process.advance_until_portion(self.timeout_s)
        self.process.advance(self.seconds)
        return self.seconds

    @property
    def _action_plan(self) -> PlanNode:
        return code(self._run)


# %% top level: preparing and filling


@dataclass
class PrepareFlossMachineAction(ActionDescription):
    """
    Make the machine ready to run: turn both Lock-N-Go handles to UNLOCKED so the bell housing floats on its
    springs ("DO NOT operate with handles in the transport position", GM_MAN_EXP p. 5).
    """

    machine: CottonCandyMachine
    """
    The machine to prepare.
    """

    arm: Arm
    """
    The arm that turns the handles.
    """

    @property
    def _action_plan(self) -> PlanNode:
        return sequential(
            [MoveTorsoAction(TorsoState.MID)]
            + [OperateElementAction(handle, self.arm, 1.0) for handle in self.machine.lock_handles]
            + [ParkArmsAction(self.robot.all_arms)]
        )

    @staticmethod
    def pre_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The motor is off: the handles are only moved on a stopped machine.
        """
        return variable_from(kwargs["machine"].motor_switch).is_on == False  # noqa: E712

    @staticmethod
    def post_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        Every handle stands UNLOCKED.
        """
        return and_(*[variable_from(handle).is_unlocked for handle in kwargs["machine"].lock_handles])


@dataclass
class FillSpinnerHeadAction(ActionDescription):
    """
    Fill the stopped spinner head to 90 % with floss sugar from the working tray, using the scoop
    ("With the spinner head stopped, pour flossugar into the spinner head. Always fill it 90% full",
    GM_MAN_EXP p. 10).
    """

    machine: CottonCandyMachine
    """
    The machine whose head is filled.
    """

    process: FlossMachineProcess
    """
    The machine's process (receives the sugar).
    """

    scoop: SugarScoop
    """
    The scoop the sugar is poured with.
    """

    tray: SugarTray
    """
    The working sugar tray the scoop is filled from and put back to.
    """

    arm: Arm
    """
    The arm holding the scoop.
    """

    def _scoop_rest_pose(self) -> Pose:
        tray_pose = self.tray.root.global_pose.to_np()
        return Pose.from_xyz_rpy(
            x=float(tray_pose[0, 3]),
            y=float(tray_pose[1, 3]),
            z=float(tray_pose[2, 3]) + 0.07,
            reference_frame=self.world.root,
        )

    def _pour(self) -> None:
        missing = self.process.timings.head_capacity_kg * self.process.timings.fill_fraction - self.process.sugar_in_head_kg
        self.process.pour_sugar(max(0.0, missing))

    @property
    def _action_plan(self) -> PlanNode:
        return sequential(
            [
                MoveTorsoAction(TorsoState.MID),
                PickUpAction(GraspCandidate.from_body_origin(self.scoop), self.arm),
                PouringAction(target_container=self.machine.spinner_head.root, source_container=self.scoop,
                              arm=self.arm),
                code(self._pour),
                PlaceAction(self.scoop, self._scoop_rest_pose()),
                ParkArmsAction(self.robot.all_arms),
            ]
        )

    @staticmethod
    def pre_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The head stands still ("NEVER add sugar when motor is running") and the arm is free.
        """
        return and_(
            variable_from(kwargs["process"]).phase == FlossMachinePhase.OFF,
            GripperIsFree(variables["arm"].end_effector),
        )

    @staticmethod
    def post_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The head is filled to at least 85 % of its capacity.
        """
        return variable_from(kwargs["process"]).head_fill_level >= 0.85


# %% top level: starting and stopping


@dataclass
class StartFlossMachineAction(ActionDescription):
    """
    Start the machine and bring it to producing floss (GM_MAN_EXP p. 10, steps 4-6): "Motor & Master" ON, wait
    10 s, "Heat" ON, heat control to maximum for the fastest warm-up, wait until floss appears (20-30 s), then turn
    the heat back to the operating setting "to eliminate smoking".
    """

    machine: CottonCandyMachine
    """
    The machine to start.
    """

    process: FlossMachineProcess
    """
    The machine's process.
    """

    arm: Arm
    """
    The arm that operates the controls.
    """

    operating_heat: float = 0.7
    """
    The heat control setting (fraction of its travel) once floss is produced (ILLUSTRATIVE; found by the operator).
    """

    @property
    def _action_plan(self) -> PlanNode:
        timings = self.process.timings
        return sequential(
            [
                MoveTorsoAction(TorsoState.MID),
                OperateElementAction(self.machine.motor_switch, self.arm, 1.0),
                LetFlossMachineRunAction(self.process, seconds=timings.master_to_heat_delay_s),
                OperateElementAction(self.machine.heat_switch, self.arm, 1.0),
                OperateElementAction(self.machine.heat_control, self.arm, 1.0),
                LetFlossMachineRunAction(self.process, until_phase=FlossMachinePhase.PRODUCING,
                                         timeout_s=3 * timings.warm_up_s),
                OperateElementAction(self.machine.heat_control, self.arm, self.operating_heat),
                ParkArmsAction(self.robot.all_arms),
            ]
        )

    @staticmethod
    def pre_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The machine is off, unlocked, and its head holds sugar.
        """
        process = variable_from(kwargs["process"])
        return and_(
            process.phase == FlossMachinePhase.OFF,
            process.sugar_in_head_kg > 0.0,
            *[variable_from(handle).is_unlocked for handle in kwargs["machine"].lock_handles],
        )

    @staticmethod
    def post_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The machine produces floss.
        """
        return variable_from(kwargs["process"]).phase == FlossMachinePhase.PRODUCING


@dataclass
class StopFlossMachineAction(ActionDescription):
    """
    Stop the machine, e.g. to refill (GM_MAN_EXP p. 10, step 8): "Heat" OFF, let the motor run a few seconds to
    start cooling the head, then "Motor & Master" OFF and wait until the head stands still.
    """

    machine: CottonCandyMachine
    """
    The machine to stop.
    """

    process: FlossMachineProcess
    """
    The machine's process.
    """

    arm: Arm
    """
    The arm that operates the switches.
    """

    run_after_heat_off_s: float = 5.0
    """
    How long the motor runs on after "Heat" OFF ("a few seconds").
    """

    @property
    def _action_plan(self) -> PlanNode:
        return sequential(
            [
                MoveTorsoAction(TorsoState.MID),
                OperateElementAction(self.machine.heat_switch, self.arm, 0.0),
                LetFlossMachineRunAction(self.process, seconds=self.run_after_heat_off_s),
                OperateElementAction(self.machine.motor_switch, self.arm, 0.0),
                LetFlossMachineRunAction(self.process, until_phase=FlossMachinePhase.OFF, timeout_s=30.0),
                ParkArmsAction(self.robot.all_arms),
            ]
        )

    @staticmethod
    def post_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The machine is off.
        """
        return variable_from(kwargs["process"]).phase == FlossMachinePhase.OFF


@dataclass
class RefillSpinnerHeadAction(ActionDescription):
    """
    Refill a running machine: stop it, fill the stopped head, start it again ("When the floss head needs to be
    refilled with sugar ... turn the Heat Switch OFF", GM_MAN_EXP p. 10).
    """

    machine: CottonCandyMachine
    """
    The machine to refill.
    """

    process: FlossMachineProcess
    """
    The machine's process.
    """

    scoop: SugarScoop
    """
    The scoop the sugar is poured with.
    """

    tray: SugarTray
    """
    The working sugar tray.
    """

    arm: Arm
    """
    The arm that operates the machine and the scoop.
    """

    @property
    def _action_plan(self) -> PlanNode:
        return sequential(
            [
                StopFlossMachineAction(self.machine, self.process, self.arm),
                FillSpinnerHeadAction(self.machine, self.process, self.scoop, self.tray, self.arm),
                StartFlossMachineAction(self.machine, self.process, self.arm),
            ]
        )


# %% top level: making and serving


@dataclass(kw_only=True)
class GatherFlossAction(ToolMotionAction):
    """
    Collect the web of floss from the pan with a held stick (GM_MAN_EXP p. 11, steps 2-4): dip the stick tip into
    the floss at the stabilizer, sweep it once around the pan to wind the ring of floss onto it, and lift it out.
    "DO NOT roll floss while the cone is inside the pan."
    """

    pan: Body
    """
    The floss pan.
    """

    gather_radius: float = 0.24
    """
    Radius in metres of the circle the tip sweeps along, just inside the floss stabilizer.
    """

    gather_height: float = -0.06
    """
    Height of the sweep relative to the pan origin (the middle of the pan wall).
    """

    turns: float = 1.25
    """
    How many times the tip goes around the pan.
    """

    def _build_tool_path(self) -> ToolPath:
        r, h, turns = self.gather_radius, self.gather_height, self.turns
        lift = 0.25

        def approach(tau: float) -> np.ndarray:
            return np.array([r, 0.0, lift - (lift - h) * tau])

        def sweep(tau: float) -> np.ndarray:
            angle = 2 * math.pi * turns * tau
            return np.array([r * math.cos(angle), r * math.sin(angle), h])

        end_angle = 2 * math.pi * turns

        def lift_out(tau: float) -> np.ndarray:
            radius = r * (1.0 - tau)
            return np.array([radius * math.cos(end_angle), radius * math.sin(end_angle), h + (lift - h) * tau])

        return ToolPath(
            segments=[
                ToolPathSegment(ToolPathSegmentKind.APPROACH, 1.0, approach),
                ToolPathSegment(ToolPathSegmentKind.SPIRAL, 4.0, sweep),
                ToolPathSegment(ToolPathSegmentKind.RETRACT, 1.0, lift_out),
            ]
        )

    def _path_frame(self) -> HomogeneousTransformationMatrix:
        return self.pan.global_pose.homogeneous_matrix

    @property
    def _alignment_target(self) -> Optional[Union[Body, Pose]]:
        return self.pan


@dataclass(kw_only=True)
class WrapFlossAction(ToolMotionAction):
    """
    Wrap the lifted floss onto the stick with a figure-eight movement above the pan ("This leaves giant pockets and
    makes the final product appear larger", GM_MAN_EXP p. 11).
    """

    pan: Body
    """
    The floss pan the wrap is done above.
    """

    height_above_rim: float = 0.30
    """
    Height of the figure eight above the pan origin.
    """

    size: float = 0.10
    """
    Half width of the figure eight in metres.
    """

    cycles: int = 2
    """
    Number of figure eights.
    """

    def _build_tool_path(self) -> ToolPath:
        a, z, cycles = self.size, self.height_above_rim, self.cycles

        def figure_eight(tau: float) -> np.ndarray:
            t = 2 * math.pi * cycles * tau
            return np.array([a * math.sin(t), a * math.sin(t) * math.cos(t), z])

        return ToolPath(segments=[ToolPathSegment(ToolPathSegmentKind.STIR, 3.0, figure_eight)])

    def _path_frame(self) -> HomogeneousTransformationMatrix:
        return self.pan.global_pose.homogeneous_matrix

    @property
    def _alignment_target(self) -> Optional[Union[Body, Pose]]:
        return self.pan


@dataclass
class MakeCottonCandyAction(ActionDescription):
    """
    Make one portion: take a stick from the quiver, wait until a portion of floss has collected, gather the floss
    from the pan onto the stick and wrap it with a figure eight.
    """

    machine: CottonCandyMachine
    """
    The producing machine.
    """

    process: FlossMachineProcess
    """
    The machine's process.
    """

    stick: CandyStick
    """
    The stick the floss is wound onto.
    """

    arm: Arm
    """
    The arm holding the stick.
    """

    @property
    def _action_plan(self) -> PlanNode:
        pan = self.machine.floss_pan.root
        return sequential(
            [
                MoveTorsoAction(TorsoState.HIGH),
                PickUpAction(GraspCandidate.from_body_origin(self.stick), self.arm),
                LetFlossMachineRunAction(self.process, until_portion=True, timeout_s=120.0),
                GatherFlossAction(arm=self.arm, tool=self.stick, pan=pan),
                code(self.process.take_portion),
                WrapFlossAction(arm=self.arm, tool=self.stick, pan=pan),
            ]
        )

    @staticmethod
    def pre_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The machine produces floss and the arm is free to take a stick.
        """
        return and_(
            variable_from(kwargs["process"]).phase == FlossMachinePhase.PRODUCING,
            GripperIsFree(variables["arm"].end_effector),
        )

    @staticmethod
    def post_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The arm holds the stick with the portion.
        """
        return GripperIsNotFree(variables["arm"].end_effector)


@dataclass
class ServeCottonCandyAction(ActionDescription):
    """
    Hand a finished portion to the customer: drive to the serving station, hold the stick upright in the handover
    zone over the counter, let go once the customer holds it, and return to the machine.
    """

    stick: CandyStick
    """
    The stick carrying the portion.
    """

    handover: HandoverZone
    """
    Where over the counter the portion is handed over.
    """

    arm: Arm
    """
    The arm holding the stick.
    """

    serving_station: Pose
    """
    Where the robot's base stands to serve.
    """

    machine_station: Pose
    """
    Where the robot's base returns to afterwards.
    """

    def _handover_pose(self) -> Pose:
        zone = self.handover.root.global_pose.to_np()
        return Pose.from_xyz_rpy(
            x=float(zone[0, 3]), y=float(zone[1, 3]), z=float(zone[2, 3]), pitch=-math.pi / 2,
            reference_frame=self.world.root,
        )

    @property
    def _action_plan(self) -> PlanNode:
        return sequential(
            [
                NavigateAction(self.serving_station),
                PlaceAction(self.stick, self._handover_pose()),
                ParkArmsAction(self.robot.all_arms),
                NavigateAction(self.machine_station),
            ]
        )

    @staticmethod
    def pre_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The arm holds the stick.
        """
        return GripperIsNotFree(variables["arm"].end_effector)

    @staticmethod
    def post_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The arm is free again: the customer has the portion.
        """
        return GripperIsFree(variables["arm"].end_effector)


@dataclass
class SellCottonCandyAction(ActionDescription):
    """
    Sell one portion: refill the head first if it holds less sugar than one portion, make the portion and serve it.
    """

    machine: CottonCandyMachine
    """
    The producing machine.
    """

    process: FlossMachineProcess
    """
    The machine's process.
    """

    stick: CandyStick
    """
    The stick for this portion.
    """

    scoop: SugarScoop
    """
    The scoop, in case the head must be refilled.
    """

    tray: SugarTray
    """
    The working sugar tray.
    """

    handover: HandoverZone
    """
    Where the portion is handed over.
    """

    machine_arm: Arm
    """
    The arm that operates the machine and makes the portion.
    """

    serving_station: Pose
    """
    Where the robot's base stands to serve.
    """

    machine_station: Pose
    """
    Where the robot's base stands at the machine.
    """

    @property
    def _action_plan(self) -> PlanNode:
        steps = []
        if self.process.sugar_in_head_kg + self.process.floss_in_pan_kg < self.process.timings.portion_sugar_kg:
            steps.append(RefillSpinnerHeadAction(self.machine, self.process, self.scoop, self.tray, self.machine_arm))
        steps += [
            MakeCottonCandyAction(self.machine, self.process, self.stick, self.machine_arm),
            ServeCottonCandyAction(self.stick, self.handover, self.machine_arm, self.serving_station,
                                   self.machine_station),
        ]
        return sequential(steps)


# %% top level: end of the day


@dataclass
class ShutDownFlossMachineAction(ActionDescription):
    """
    Shut the machine down for the day (GM_MAN_EXP p. 13): run the head empty, burn out the remaining sugar at
    maximum heat for 3-4 minutes, "Heat" OFF and let the motor cool the head for 1-2 minutes, then "Motor & Master"
    OFF and wait for a complete stop.
    """

    machine: CottonCandyMachine
    """
    The machine to shut down.
    """

    process: FlossMachineProcess
    """
    The machine's process.
    """

    arm: Arm
    """
    The arm that operates the controls.
    """

    @property
    def _action_plan(self) -> PlanNode:
        timings = self.process.timings
        return sequential(
            [
                MoveTorsoAction(TorsoState.MID),
                LetFlossMachineRunAction(self.process, until_phase=FlossMachinePhase.RUNNING_EMPTY, timeout_s=600.0),
                OperateElementAction(self.machine.heat_control, self.arm, 1.0),
                LetFlossMachineRunAction(self.process, seconds=timings.burn_out_s),
                OperateElementAction(self.machine.heat_switch, self.arm, 0.0),
                LetFlossMachineRunAction(self.process, seconds=timings.cool_down_s),
                OperateElementAction(self.machine.motor_switch, self.arm, 0.0),
                LetFlossMachineRunAction(self.process, until_phase=FlossMachinePhase.OFF, timeout_s=30.0),
                ParkArmsAction(self.robot.all_arms),
            ]
        )

    @staticmethod
    def pre_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The arm is free (no stick or scoop held while working the controls).
        """
        return GripperIsFree(variables["arm"].end_effector)

    @staticmethod
    def post_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The machine is off and the head has been burnt out for the full time.
        """
        process = variable_from(kwargs["process"])
        return and_(
            process.phase == FlossMachinePhase.OFF,
            process.burnt_out_s >= kwargs["process"].timings.burn_out_s - 1.0,
        )


@dataclass
class CleanFlossMachineAction(ActionDescription):
    """
    Clean the cooled machine (GM_MAN_EXP p. 13): wipe the pan with a damp cloth. "NEVER put water in the floss head."
    """

    machine: CottonCandyMachine
    """
    The machine to clean.
    """

    process: FlossMachineProcess
    """
    The machine's process (must be off).
    """

    sponge: Sponge
    """
    The damp sponge.
    """

    arm: Arm
    """
    The arm holding the sponge.
    """

    def _sponge_rest_pose(self) -> Pose:
        pose = self.sponge.root.global_pose.to_np()
        return Pose.from_xyz_rpy(x=float(pose[0, 3]), y=float(pose[1, 3]), z=float(pose[2, 3]),
                                 reference_frame=self.world.root)

    @property
    def _action_plan(self) -> PlanNode:
        rest = self._sponge_rest_pose()
        return sequential(
            [
                PickUpAction(GraspCandidate.from_body_origin(self.sponge), self.arm),
                WipingAction(arm=self.arm, tool=self.sponge, surface=self.machine.root,
                             technique=WipingTechnique.WIPE, length=0.20, cycles=2.0),
                PlaceAction(self.sponge, rest),
                ParkArmsAction(self.robot.all_arms),
            ]
        )

    @staticmethod
    def pre_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The machine is off ("Allow to cool before cleaning").
        """
        return variable_from(kwargs["process"]).phase == FlossMachinePhase.OFF
