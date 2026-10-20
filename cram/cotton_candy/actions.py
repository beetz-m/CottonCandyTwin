"""
Top-level action designators for a robot that operates a cotton candy booth.

Each top-level designator is a composition of manipulation action categories
(:mod:`cotton_candy.manipulation_categories`) bound to the booth's objects, following the reference machine's manual
(twin register ``GM_MAN_EXP`` pp. 5, 8-13). The mapping, top-level designator -> categories (plan order):

======================================  =====================================================================  ==========
Top-level designator                    Manipulation action categories                                         Family
======================================  =====================================================================  ==========
:class:`PrepareFlossMachineAction`      Turning (lever) x2                                                     B access
:class:`FillSpinnerHeadAction`          Transporting (carton) - Pouring (spout) - Transporting (carton back)   B load
:class:`StartFlossMachineAction`        PressingButton - Monitoring - PressingButton - Turning (knob) -        B operate
                                        Monitoring - Turning (knob)
:class:`MakeCottonCandyAction`          Transporting (stick) - Monitoring - Gathering - Wrapping               D portion
:class:`ServeCottonCandyAction`         HandingOver                                                            J handover
:class:`StopFlossMachineAction`         PressingButton - Monitoring - PressingButton - Monitoring              B operate
:class:`RefillSpinnerHeadAction`        Stop + Fill + Start                                                    B
:class:`SellCottonCandyAction`          (Refill) + Make + Serve                                                activity
:class:`ShutDownFlossMachineAction`     Monitoring - Turning - Monitoring - PressingButton - Monitoring -      B / maint.
                                        PressingButton - Monitoring
:class:`CleanFlossMachineAction`        Transporting (sponge) - Wiping - Transporting (sponge back)            G wipe
======================================  =====================================================================  ==========

The floss machine's behaviour (phases, sugar, floss) comes from :class:`~cotton_candy.process.FlossMachineProcess`;
waiting on it is the Monitoring category.
"""

from __future__ import annotations

from dataclasses import dataclass

import math

import numpy as np

from typing_extensions import Any, Dict, Optional

from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.factories import ConditionType, and_, variable_from
from krrood.ormatic.utils import classproperty

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import WipingTechnique
from coraplex.plans.factories import sequential
from coraplex.plans.plan_node import PlanNode
from coraplex.querying.predicates import GripperIsFree, GripperIsNotFree
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction, ParkArmsAction
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.spatial_types.spatial_types import Pose

from cotton_candy.manipulation_categories import (
    ApproachDirection,
    CategorisedWipingAction,
    GatheringAction,
    HandingOverAction,
    HasManipulationCategory,
    ManipulationActionCategory,
    PouringIntoAction,
    PressingButtonAction,
    PuttingDownAction,
    TransportingAction,
    TurningAction,
    WrappingAction,
)
from cotton_candy.process import FlossMachinePhase, FlossMachineProcess
from cotton_candy.process_nodes import process_step
from cotton_candy.semantic_annotations import (
    CandyStick,
    CottonCandyMachine,
    HandoverZone,
    Sponge,
    SugarCarton,
)


def pose_above(body_pose, dz: float, world_root) -> Pose:
    """
    :return: A world-aligned pose ``dz`` above a body's origin.
    """
    m = body_pose.to_np()
    return Pose.from_xyz_rpy(x=float(m[0, 3]), y=float(m[1, 3]), z=float(m[2, 3]) + dz, reference_frame=world_root)


# %% monitoring the machine's process


@dataclass
class MonitoringProcessAction(ActionDescription, HasManipulationCategory):
    """
    Watch the machine's process: for a time, until a phase is reached, or until a portion of floss has collected.

    The plan advances the process model; with a real or Isaac Sim machine the same node waits for the machine's
    reported state instead.
    """

    process: FlossMachineProcess
    """
    The process of the machine.
    """

    seconds: float = 0.0
    """
    How long to watch, if no phase or portion is waited for.
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

    @classproperty
    def manipulation_category(cls) -> ManipulationActionCategory:
        return ManipulationActionCategory.MONITORING

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
        return process_step(self._run)


# %% top level: preparing and filling


@dataclass
class PrepareFlossMachineAction(ActionDescription):
    """
    Make the machine ready to run: turn both Lock-N-Go handles to UNLOCKED so the bell housing floats on its
    springs ("DO NOT operate with handles in the transport position", GM_MAN_EXP p. 5).

    Categories: Turning (lever) x2.

    Reach: the handles sit under the pan's overhang; a PR2 cannot reach them with collision avoidance on (kinematic
    test 2026-10-20). Unlocking is therefore a set-up task for the staff; this designator documents it and is kept
    for robots that can reach under the pan.
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
            [MoveTorsoAction(TorsoState.LOW)]
            + [TurningAction(handle, self.arm, 1.0) for handle in self.machine.lock_handles]
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
    Fill the stopped spinner head to 90 % with floss sugar from the Flossugar carton ("With the spinner head stopped,
    pour flossugar into the spinner head. Always fill it 90% full", GM_MAN_EXP p. 10; cartons "with an E-Z pour
    spout for filling your machine", p. 9).

    Categories: Transporting (carton, held low) - Pouring (spout over the head) - Transporting (carton back).
    """

    machine: CottonCandyMachine
    """
    The machine whose head is filled.
    """

    process: FlossMachineProcess
    """
    The machine's process (receives the sugar).
    """

    carton: SugarCarton
    """
    The sugar carton poured from.
    """

    arm: Arm
    """
    The arm holding the carton.
    """

    machine_station: Pose
    """
    Where the robot's base stands (and parks) at the machine.
    """

    close_station: Pose
    """
    Where the base stands for pouring, nearer the machine (only reached with the carton held up; never park there).
    """

    grip_height: float = 0.03
    """
    Height of the grip above the carton's bottom (twin register sugar_carton_grip_height).
    """

    tilt_angle: float = 1.2
    """
    Forward tilt of the carton in radians (a spout carton runs from ~70 deg; a steeper tilt drops the forearm onto
    the pan rim).
    """

    pour_height: float = 0.24
    """
    Height of the grip above the spinner head's origin while pouring: the carton bottom clears the pan rim, and with
    the torso HIGH (shoulder above the pan rim) the arm still reaches (kinematic test 2026-10-20).
    """

    def _pour(self) -> None:
        timings = self.process.timings
        self.process.pour_sugar(
            max(0.0, timings.head_capacity_kg * timings.fill_fraction - self.process.sugar_in_head_kg)
        )

    def _carton_half_height(self) -> float:
        spout = self.carton.get_tool_frame().global_pose.to_np()
        root = self.carton.root.global_pose.to_np()
        return float(np.linalg.norm(spout[:3, 3] - root[:3, 3]))

    @property
    def _action_plan(self) -> PlanNode:
        rest = pose_above(self.carton.root.global_pose, 0.0, self.world.root)
        half = self._carton_half_height()
        spout_reach = (2 * half - self.grip_height) * math.sin(self.tilt_angle)
        grip_point = pose_above(self.carton.root.global_pose, -half + self.grip_height, self.world.root)
        return sequential(
            [
                MoveTorsoAction(TorsoState.HIGH),
                TransportingAction(self.carton, self.arm, ApproachDirection.TOWARDS_SALES_FRONT,
                                   grasp_offset=(0.0, 0.0, -half + self.grip_height)),
                NavigateAction(self.close_station),
                PouringIntoAction(self.arm, self.machine.spinner_head.root, standoff=spout_reach,
                                  pour_height=self.pour_height, tilt_angle=self.tilt_angle, lift_from=grip_point,
                                  may_touch=[self.machine.floss_pan.root,
                                             self.world.get_body_by_name("FlossBubble")]),
                process_step(self._pour),
                NavigateAction(self.machine_station),
                ParkArmsAction([self.arm]),
                PuttingDownAction(self.carton, rest),
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

    Categories: PressingButton - Monitoring - PressingButton - Turning - Monitoring - Turning.
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
    Heat control setting (fraction of its travel) once floss is produced (ILLUSTRATIVE; found by the operator).
    """

    @property
    def _action_plan(self) -> PlanNode:
        timings = self.process.timings
        return sequential(
            [
                MoveTorsoAction(TorsoState.LOW),
                PressingButtonAction(self.machine.motor_switch, self.arm, 1.0),
                MonitoringProcessAction(self.process, seconds=timings.master_to_heat_delay_s),
                PressingButtonAction(self.machine.heat_switch, self.arm, 1.0),
                TurningAction(self.machine.heat_control, self.arm, 1.0),
                MonitoringProcessAction(
                    self.process, until_phase=FlossMachinePhase.PRODUCING, timeout_s=3 * timings.warm_up_s
                ),
                TurningAction(self.machine.heat_control, self.arm, self.operating_heat),
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

    Categories: PressingButton - Monitoring - PressingButton - Monitoring.
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
                MoveTorsoAction(TorsoState.LOW),
                PressingButtonAction(self.machine.heat_switch, self.arm, 0.0),
                MonitoringProcessAction(self.process, seconds=self.run_after_heat_off_s),
                PressingButtonAction(self.machine.motor_switch, self.arm, 0.0),
                MonitoringProcessAction(self.process, until_phase=FlossMachinePhase.OFF, timeout_s=30.0),
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

    carton: SugarCarton
    """
    The sugar carton poured from.
    """

    arm: Arm
    """
    The arm that operates the machine and the carton.
    """

    machine_station: Pose
    """
    Where the robot's base stands at the machine.
    """

    close_station: Pose
    """
    Where the base stands for pouring.
    """

    @property
    def _action_plan(self) -> PlanNode:
        return sequential(
            [
                StopFlossMachineAction(self.machine, self.process, self.arm),
                FillSpinnerHeadAction(self.machine, self.process, self.carton, self.arm, self.machine_station, self.close_station),
                StartFlossMachineAction(self.machine, self.process, self.arm),
            ]
        )


# %% top level: making and serving


@dataclass
class MakeCottonCandyAction(ActionDescription):
    """
    Make one portion (GM_MAN_EXP p. 11): take a stick, wait until a portion of floss has collected, gather the web
    of floss from the pan onto the stick, lift it out and wrap it with a figure eight ("DO NOT roll floss while the
    cone is inside the pan").

    Categories: Transporting (stick, held) - Monitoring - Gathering - Wrapping.
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
                MoveTorsoAction(TorsoState.LOW),
                TransportingAction(self.stick, self.arm, ApproachDirection.TOWARDS_LEFT_WALL),
                MonitoringProcessAction(self.process, until_portion=True, timeout_s=120.0),
                GatheringAction(arm=self.arm, tool=self.stick, container=pan),
                process_step(self.process.take_portion),
                WrappingAction(arm=self.arm, tool=self.stick, above=pan),
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
    Hand a finished portion to the customer: drive to the serving station, present the stick in the handover zone
    over the counter, let go once the customer holds it, and return to the machine.

    Categories: HandingOver (with navigation before and after).
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
        """
        :return: The stick's pose in the handover zone: upright, the floss end up (the stick's x axis points to the
            floss end).
        """
        zone = self.handover.root.global_pose.to_np()
        return Pose.from_xyz_rpy(x=float(zone[0, 3]), y=float(zone[1, 3]), z=float(zone[2, 3]), pitch=-math.pi / 2,
                                 reference_frame=self.world.root)

    @property
    def _action_plan(self) -> PlanNode:
        return sequential(
            [
                NavigateAction(self.serving_station),
                HandingOverAction(self.stick, self.arm, self._handover_pose()),
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
    Sell one portion: refill the head first if it and the pan hold less than one portion, make the portion and
    serve it.
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

    carton: SugarCarton
    """
    The sugar carton, in case the head must be refilled.
    """

    handover: HandoverZone
    """
    Where the portion is handed over.
    """

    arm: Arm
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

    close_station: Pose
    """
    Where the base stands for pouring, in case the head must be refilled.
    """

    @property
    def _action_plan(self) -> PlanNode:
        steps = []
        if self.process.sugar_in_head_kg + self.process.floss_in_pan_kg < self.process.timings.portion_sugar_kg:
            steps.append(RefillSpinnerHeadAction(self.machine, self.process, self.carton, self.arm, self.machine_station, self.close_station))
        steps += [
            MakeCottonCandyAction(self.machine, self.process, self.stick, self.arm),
            ServeCottonCandyAction(self.stick, self.handover, self.arm, self.serving_station, self.machine_station),
        ]
        return sequential(steps)


# %% top level: end of the day


@dataclass
class ShutDownFlossMachineAction(ActionDescription):
    """
    Shut the machine down for the day (GM_MAN_EXP p. 13): run the head empty, burn out the remaining sugar at
    maximum heat for 3-4 minutes, "Heat" OFF and let the motor cool the head for 1-2 minutes, then "Motor & Master"
    OFF and wait for a complete stop.

    Categories: Monitoring - Turning - Monitoring - PressingButton - Monitoring - PressingButton - Monitoring.
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
                MoveTorsoAction(TorsoState.LOW),
                MonitoringProcessAction(
                    self.process, until_phase=FlossMachinePhase.RUNNING_EMPTY, timeout_s=600.0
                ),
                TurningAction(self.machine.heat_control, self.arm, 1.0),
                MonitoringProcessAction(self.process, seconds=timings.burn_out_s),
                PressingButtonAction(self.machine.heat_switch, self.arm, 0.0),
                MonitoringProcessAction(self.process, seconds=timings.cool_down_s),
                PressingButtonAction(self.machine.motor_switch, self.arm, 0.0),
                MonitoringProcessAction(self.process, until_phase=FlossMachinePhase.OFF, timeout_s=30.0),
                ParkArmsAction(self.robot.all_arms),
            ]
        )

    @staticmethod
    def pre_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The arm is free (no stick or carton held while working the controls).
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
    Clean the cooled machine (GM_MAN_EXP p. 13): wipe the stainless parts around it with a damp cloth ("Wipe the
    stainless steel parts with a clean cloth"); "NEVER put water in the floss head."

    Categories: Transporting (sponge, held) - Wiping - Transporting (sponge back).
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

    def _wipe_pose(self) -> Pose:
        """
        :return: The middle of the wiped strip: the stainless table top along its edge nearest the robot, beside the
            machine (within the arm's comfortable reach).
        """
        table = self.world.get_body_by_name("MachineTable")
        top = table.global_pose.to_np()
        bbox = table.collision.as_bounding_box_collection_in_frame(self.world.root).bounding_box()
        sponge = self.sponge.root.global_pose.to_np()
        return Pose.from_xyz_rpy(x=float(sponge[0, 3]), y=float(bbox.max_y) - 0.08, z=float(bbox.max_z),
                                 reference_frame=self.world.root)

    @property
    def _action_plan(self) -> PlanNode:
        rest = pose_above(self.sponge.root.global_pose, 0.0, self.world.root)
        return sequential(
            [
                TransportingAction(self.sponge, self.arm, ApproachDirection.TOWARDS_SALES_FRONT),
                CategorisedWipingAction(
                    arm=self.arm, tool=self.sponge, target_pose=self._wipe_pose(),
                    technique=WipingTechnique.WIPE, length=0.15, cycles=2.0,
                ),
                PuttingDownAction(self.sponge, rest),
                ParkArmsAction(self.robot.all_arms),
            ]
        )

    @staticmethod
    def pre_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The machine is off ("Allow to cool before cleaning").
        """
        return variable_from(kwargs["process"]).phase == FlossMachinePhase.OFF
