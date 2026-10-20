"""
Manipulation action categories and the generic, domain-independent designators that realise them.

The categories follow the CRAM action-category framework (ResearchSpace
``foundation/kb/dl-axioms/cram/ontology/action-category-dl.md``): every category specialises one effect class
(ObjectDisplacement, ConfigurationChange, SubstanceManipulation, SurfaceTreatment, InteractionAction,
MaintenanceAction), composes primitives (Reaching, Grasping, Lifting, Tilting, Stroking) via ``hasSubaction``, and
has a telos defined over a force-dynamic terminal state. Transporting, Pouring and Wiping exist in that module;
PressingButton, Turning, Scooping, Gathering, Wrapping and HandingOver are proposed here as extensions (marked
``defined_in = "proposed"``), with the primitive vocabulary of ``okf/cram/TASK-TAXONOMY.md`` §3 (press (button),
turn (knob), stir/scoop, handover, ...).

Each category designator carries its category as :attr:`HasManipulationCategory.manipulation_category`, so the
domain's top-level designators are compositions of categories and the plan can be read as a category profile.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from scipy.spatial.transform import Rotation
from typing_extensions import Any, Dict, List, Optional, Tuple, Union

from giskardpy.motion_statechart.data_types import DefaultWeights
from giskardpy.motion_statechart.goals.open_close import Open
from giskardpy.motion_statechart.goals.templates import Parallel
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.factories import ConditionType, and_, variable_from
from krrood.ormatic.utils import classproperty

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import ToolPathSegmentKind
from coraplex.plans.factories import code, sequential
from coraplex.plans.plan_node import PlanNode
from coraplex.querying.predicates import GripperIsFree, GripperIsNotFree
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.robot_plans.actions.composite.tool_based import FullBodyControlledAction, ToolMotionAction, WipingAction
from coraplex.robot_plans.actions.composite.tool_paths import ToolPath, ToolPathSegment
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.pick_up import GraspingAction, PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from coraplex.robot_plans.motions.base import BaseMotion
from giskardpy.motion_statechart.goals.collision_avoidance import UpdateTemporaryCollisionRules
from semantic_digital_twin.collision_checking.collision_rules import (
    AllowCollisionForBodies,
    AllowCollisionForEndEffector,
)
from coraplex.robot_plans.motions.gripper import MoveGripperMotion, MoveToolCenterPointMotion
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.semantic_annotations.mixins import HasRootBody
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.world_entity import Body

from cotton_candy.semantic_annotations import OperatingElement


# %% the category vocabulary


class EffectDimension(Enum):
    """
    The effect classes of the action-category framework (``effectDimension``, pairwise disjoint).
    """

    DISPLACEMENT = "ObjectDisplacement"
    CONFIGURATION = "ConfigurationChange"
    SUBSTANCE = "SubstanceManipulation"
    SURFACE = "SurfaceTreatment"
    CONNECTION = "ConnectingAction"
    SOCIAL = "InteractionAction"
    MAINTENANCE = "MaintenanceAction"


@dataclass(frozen=True)
class CategorySpecification:
    """
    One manipulation action category: where it sits in the taxonomy, what it is made of and what it achieves.
    """

    name: str
    """
    The OWL class name of the category.
    """

    parent: str
    """
    The class it specialises.
    """

    effect: EffectDimension | None
    """
    Its effect class, or None for non-manipulation categories (monitoring).
    """

    subactions: Tuple[str, ...]
    """
    The primitive categories it is composed of (``hasSubaction``).
    """

    telos_state: str
    """
    The force-dynamic (or process) state its telos is defined over.
    """

    roles: Tuple[str, ...]
    """
    The participant roles of its intentional structure.
    """

    task_taxonomy_primitive: str
    """
    The matching atomic primitive of TASK-TAXONOMY.md §3.
    """

    defined_in: str
    """
    ``action-category-dl.md`` if the class exists in the CRAM L2 module, ``proposed`` if it is an extension made here.
    """


class ManipulationActionCategory(Enum):
    """
    The manipulation action categories the cotton candy booth needs.
    """

    TRANSPORTING = CategorySpecification(
        "Transporting", "ObjectDisplacement", EffectDimension.DISPLACEMENT,
        ("Reaching", "Grasping", "Lifting"), "PlacedState", ("AgentRole", "PatientRole", "GoalRole"),
        "pick / carry / place", "action-category-dl.md",
    )
    PRESSING_BUTTON = CategorySpecification(
        "PressingButton", "ConfigurationChange", EffectDimension.CONFIGURATION,
        ("Reaching", "Pushing"), "SwitchedState", ("AgentRole", "ControlRole"),
        "press (button)", "proposed",
    )
    TURNING = CategorySpecification(
        "Turning", "ConfigurationChange", EffectDimension.CONFIGURATION,
        ("Reaching", "Grasping", "Rotating"), "SetState", ("AgentRole", "ControlRole"),
        "turn (knob)", "proposed",
    )
    SCOOPING = CategorySpecification(
        "Scooping", "Transferring", EffectDimension.SUBSTANCE,
        ("Reaching", "Stroking", "Lifting"), "ContainedState", ("AgentRole", "SubstanceRole", "SourceRole",
                                                                 "InstrumentRole"),
        "stir/scoop", "proposed",
    )
    POURING = CategorySpecification(
        "Pouring", "Transferring", EffectDimension.SUBSTANCE,
        ("Grasping", "Tilting"), "AccumulatedState", ("AgentRole", "SubstanceRole", "SourceRole", "GoalRole"),
        "pour", "action-category-dl.md",
    )
    GATHERING = CategorySpecification(
        "Gathering", "Transferring", EffectDimension.SUBSTANCE,
        ("Reaching", "Stroking", "Lifting"), "AccumulatedState", ("AgentRole", "SubstanceRole", "SourceRole",
                                                                  "InstrumentRole"),
        "stir/scoop", "proposed",
    )
    WRAPPING = CategorySpecification(
        "Wrapping", "SubstanceManipulation", EffectDimension.SUBSTANCE,
        ("Stroking",), "ShapedState", ("AgentRole", "SubstanceRole", "InstrumentRole"),
        "fold/unfold (deformable)", "proposed",
    )
    HANDING_OVER = CategorySpecification(
        "HandingOver", "InteractionAction", EffectDimension.SOCIAL,
        ("Reaching", "Releasing"), "ReceivedState", ("AgentRole", "PatientRole", "RecipientRole"),
        "handover", "proposed",
    )
    WIPING = CategorySpecification(
        "Wiping", "SurfaceTreatment", EffectDimension.SURFACE,
        ("Grasping", "Stroking"), "CleanState", ("AgentRole", "InstrumentRole", "PatientRole"),
        "wipe", "action-category-dl.md",
    )
    MONITORING = CategorySpecification(
        "MonitoringProcess", "PerceptionAction", None,
        (), "ObservedState", ("AgentRole", "ProcessRole"),
        "check-state / monitor (family K)", "proposed",
    )

    @property
    def specification(self) -> CategorySpecification:
        """
        :return: The category's specification.
        """
        return self.value


@dataclass
class HasManipulationCategory:
    """
    Mixin for designators that realise a manipulation action category.
    """

    @classproperty
    def manipulation_category(cls) -> ManipulationActionCategory:
        """
        The category this designator realises.
        """
        raise NotImplementedError(cls)


# %% grasps


class ApproachDirection(Enum):
    """
    The world direction a gripper moves along to reach an object (its tool frame's x axis points this way).
    """

    TOWARDS_SALES_FRONT = (0.0, 0.0, -math.pi / 2)
    """
    Towards -y: onto the machine's front panel, which faces the operator, or forward over the counter.
    """

    FROM_ABOVE = (0.0, math.pi / 2, 0.0)
    """
    Downwards: onto a tool lying on a surface.
    """

    TOWARDS_LEFT_WALL = (0.0, 0.0, math.pi)
    """
    Towards -x: into the stick quiver on the left wall.
    """

    def grasp(self, graspable: HasRootBody, offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)) -> GraspCandidate:
        """
        :param graspable: The object to grasp.
        :param offset: Where to grasp relative to the object's origin, in the object's frame.
        :return: A grasp approached along this direction, expressed in the object's frame.
        """
        roll, pitch, yaw = self.value
        world_R_grasp = Rotation.from_euler("xyz", [roll, pitch, yaw]).as_matrix()
        root_R_world = graspable.root.global_pose.to_np()[:3, :3].T
        qx, qy, qz, qw = Rotation.from_matrix(root_R_world @ world_R_grasp).as_quat()
        return GraspCandidate(
            graspable,
            Pose.from_xyz_quaternion(pos_x=offset[0], pos_y=offset[1], pos_z=offset[2], quat_x=qx, quat_y=qy,
                                     quat_z=qz, quat_w=qw, reference_frame=graspable.root),
        )


# %% configuration change: pressing, turning


@dataclass
class TurnToMotion(BaseMotion):
    """
    Turn a held operating element to a position of its joint.
    """

    object_part: Body
    """
    The body of the element.
    """

    arm: Arm
    """
    The arm moving it.
    """

    goal_position: float
    """
    The joint position to turn to.
    """

    def perform(self):
        return

    @property
    def _motion_chart(self):
        turn = Open(
            tip_link=self.arm.end_effector.tool_frame,
            environment_link=self.object_part,
            goal_joint_state=self.goal_position,
            mechanism_weight=DefaultWeights.WEIGHT_BELOW_COLLISION_AVOIDANCE,
        )
        # coraplex's OpeningMotion/ClosingMotion leave the base free, so it drifts while the element is moved;
        # hold it like the other arm motions do
        hold_base = self.keep_base_still()
        if not hold_base:
            return turn
        return Parallel([turn, *hold_base], name="TurnTo")


@dataclass
class MoveTCPMayTouchMotion(MoveToolCenterPointMotion):
    """
    Move the tool centre point while the arm may touch some bodies, e.g. rest on a pan rim while reaching over it.

    Everything else stays under collision avoidance; the end effector and what it holds may touch the environment.
    """

    may_touch: List[Body] = field(default_factory=list, kw_only=True)
    """
    The bodies the arm's links may touch during this motion.
    """

    def _only_allow_gripper_collision_rules(self, end_effector):
        return [
            UpdateTemporaryCollisionRules(
                temporary_rules=[
                    AllowCollisionForEndEffector(end_effector=end_effector),
                    AllowCollisionForBodies(allowed_collision_bodies=set(self.may_touch)),
                ]
            )
        ]


@dataclass
class ElementActuationAction(ActionDescription):
    """
    Bring an operating element to a fraction of its travel and leave it there (common plan of pressing and turning).
    """

    element: OperatingElement
    """
    The operating element.
    """

    arm: Arm
    """
    The arm that actuates it.
    """

    travel_fraction: float
    """
    Target position: 0 is the lower end of the joint range (OFF, LOCKED, minimum), 1 the upper end (ON, UNLOCKED,
    maximum).
    """

    approach: ApproachDirection = ApproachDirection.TOWARDS_SALES_FRONT
    """
    The direction the gripper comes from.
    """

    release_clearance: float = 0.05
    """
    Gap in metres between element and gripper after letting go.
    """

    def _goal_position(self) -> float:
        limits = self.element.movable_joint.dof.limits
        return limits.lower.position + self.travel_fraction * (limits.upper.position - limits.lower.position)

    def _mechanism_motion(self) -> BaseMotion:
        limits = self.element.movable_joint.dof.limits
        margin = 0.01 * (limits.upper.position - limits.lower.position)
        goal = min(max(self._goal_position(), limits.lower.position + margin), limits.upper.position - margin)
        return TurnToMotion(self.element.root, self.arm, goal)

    def _contact_plan(self) -> List[Any]:
        """
        :return: How the gripper takes the element before it is moved.
        """
        return [GraspingAction(self.approach.grasp(self.element), self.arm)]

    @property
    def _action_plan(self) -> PlanNode:
        back_off = Pose.from_xyz_rpy(x=-self.release_clearance, reference_frame=self.arm.end_effector.tool_frame)
        return sequential(
            [ParkArmsAction([self.arm])]
            + self._contact_plan()
            + [
                self._mechanism_motion(),
                MoveGripperMotion(GripperState.OPEN, self.arm.end_effector, allow_gripper_collision=True),
                MoveToolCenterPointMotion(back_off, self.arm, allow_gripper_collision=True),
            ]
        )

    @staticmethod
    def pre_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The actuating gripper has to be free.
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
class PressingButtonAction(ElementActuationAction, HasManipulationCategory):
    """
    Press a button or rocker into a position: push it with the closed gripper's fingertips.

    The push is executed as a mechanism motion on the rocker's joint, coupled to the gripper.
    """

    @classproperty
    def manipulation_category(cls) -> ManipulationActionCategory:
        return ManipulationActionCategory.PRESSING_BUTTON

    def _contact_plan(self) -> List[Any]:
        return [
            MoveGripperMotion(GripperState.CLOSE, self.arm.end_effector, allow_gripper_collision=True),
            GraspingAction(self.approach.grasp(self.element), self.arm),
        ]


@dataclass
class TurningAction(ElementActuationAction, HasManipulationCategory):
    """
    Grasp a knob or lever and turn it to a position.
    """

    @classproperty
    def manipulation_category(cls) -> ManipulationActionCategory:
        return ManipulationActionCategory.TURNING


# %% displacement and interaction: transporting, handing over


@dataclass
class TransportingAction(ActionDescription, HasManipulationCategory):
    """
    Pick an object up and, if a target is given, put it down there; without a target the object stays held.
    """

    graspable: HasRootBody
    """
    The object to transport.
    """

    arm: Arm
    """
    The arm that carries it.
    """

    approach: ApproachDirection
    """
    The direction the gripper comes from.
    """

    target: Optional[Pose] = None
    """
    Where to put the object down, or None to keep holding it.
    """

    grasp_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    """
    Where to grasp relative to the object's origin, in the object's frame.
    """

    @classproperty
    def manipulation_category(cls) -> ManipulationActionCategory:
        return ManipulationActionCategory.TRANSPORTING

    @property
    def _action_plan(self) -> PlanNode:
        steps = [ParkArmsAction([self.arm]), PickUpAction(self.approach.grasp(self.graspable, self.grasp_offset), self.arm)]
        if self.target is not None:
            steps.append(PlaceAction(self.graspable, self.target))
        return sequential(steps)


@dataclass
class PuttingDownAction(ActionDescription, HasManipulationCategory):
    """
    Put a held object down at a pose (the second half of a transport).
    """

    graspable: HasRootBody
    """
    The held object.
    """

    target: Pose
    """
    Where to put it down.
    """

    arm: Optional[Arm] = None
    """
    The holding arm; needed only for the via point.
    """

    via_height: float = 0.0
    """
    If positive (and an arm is given), the object is first carried level - at its current height, or this height
    above the target if that is higher - to above the target, keeping its orientation, and then lowered, so the arm
    clears obstacles between where it is and where it goes (e.g. a pan rim).
    """

    retreat: float = 0.0
    """
    If positive (and an arm is given), the object is first pulled back towards the agent (+y) by this distance at its
    current height, before it is carried over to the target.
    """

    @classproperty
    def manipulation_category(cls) -> ManipulationActionCategory:
        return ManipulationActionCategory.TRANSPORTING

    @property
    def _action_plan(self) -> PlanNode:
        steps = []
        if self.arm is not None and self.retreat > 0.0:
            tool = self.arm.end_effector.tool_frame.global_pose.to_np()
            qx, qy, qz, qw = Rotation.from_matrix(tool[:3, :3]).as_quat()
            steps.append(
                MoveToolCenterPointMotion(
                    Pose.from_xyz_quaternion(
                        pos_x=float(tool[0, 3]), pos_y=float(tool[1, 3]) + self.retreat, pos_z=float(tool[2, 3]),
                        quat_x=qx, quat_y=qy, quat_z=qz, quat_w=qw, reference_frame=self.world.root,
                    ),
                    self.arm,
                    allow_gripper_collision=True,
                )
            )
        if self.arm is not None and self.via_height > 0.0:
            tool = self.arm.end_effector.tool_frame.global_pose.to_np()
            target = self.target.to_np()
            qx, qy, qz, qw = Rotation.from_matrix(tool[:3, :3]).as_quat()
            grasp_offset = tool[:3, 3] - self.graspable.root.global_pose.to_np()[:3, 3]
            steps.append(
                MoveToolCenterPointMotion(
                    Pose.from_xyz_quaternion(
                        pos_x=float(target[0, 3] + grasp_offset[0]), pos_y=float(target[1, 3] + grasp_offset[1]),
                        pos_z=max(float(tool[2, 3]), float(target[2, 3] + grasp_offset[2]) + self.via_height),
                        quat_x=qx, quat_y=qy, quat_z=qz, quat_w=qw, reference_frame=self.world.root,
                    ),
                    self.arm,
                    allow_gripper_collision=True,
                )
            )
        steps.append(PlaceAction(self.graspable, self.target))
        return sequential(steps)


@dataclass
class HandingOverAction(ActionDescription, HasManipulationCategory):
    """
    Hand a held object to a person: present it in the handover zone and release it once the person holds it.
    """

    graspable: HasRootBody
    """
    The object handed over.
    """

    arm: Arm
    """
    The arm holding it.
    """

    handover_pose: Pose
    """
    Where the object is presented.
    """

    @classproperty
    def manipulation_category(cls) -> ManipulationActionCategory:
        return ManipulationActionCategory.HANDING_OVER

    @property
    def _action_plan(self) -> PlanNode:
        return sequential([PlaceAction(self.graspable, self.handover_pose)])

    @staticmethod
    def pre_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The arm holds what is handed over.
        """
        return GripperIsNotFree(variables["arm"].end_effector)

    @staticmethod
    def post_condition(variables: Dict[str, Variable], context: Context, kwargs: Dict[str, Any]) -> ConditionType:
        """
        The arm has let go: the recipient holds it.
        """
        return GripperIsFree(variables["arm"].end_effector)


# %% substance manipulation: scooping, pouring, gathering, wrapping


@dataclass
class ScoopingAction(ActionDescription, HasManipulationCategory):
    """
    Dip a held scoop into a container of granular substance and lift it out filled.
    """

    arm: Arm
    """
    The arm holding the scoop.
    """

    source: Body
    """
    The container scooped from.
    """

    dip_height: float = 0.06
    """
    Height above the container's origin the scoop dips to, in metres (just below the rim of a 10 cm tray).
    """

    approach_height: float = 0.14
    """
    Height above the container's origin the scoop approaches from and lifts out to, in metres.
    """

    @classproperty
    def manipulation_category(cls) -> ManipulationActionCategory:
        return ManipulationActionCategory.SCOOPING

    @property
    def _action_plan(self) -> PlanNode:
        source = self.source.global_pose.to_np()
        tool = self.arm.end_effector.tool_frame.global_pose.to_np()
        quat = Rotation.from_matrix(tool[:3, :3]).as_quat()

        def at(z: float) -> Pose:
            return Pose.from_xyz_quaternion(
                pos_x=float(source[0, 3]), pos_y=float(source[1, 3]), pos_z=float(source[2, 3]) + z,
                quat_x=quat[0], quat_y=quat[1], quat_z=quat[2], quat_w=quat[3], reference_frame=self.world.root,
            )

        return sequential(
            [
                MoveToolCenterPointMotion(at(self.approach_height), self.arm, allow_gripper_collision=True),
                MoveToolCenterPointMotion(at(self.dip_height), self.arm, allow_gripper_collision=True),
                MoveToolCenterPointMotion(at(self.approach_height), self.arm, allow_gripper_collision=True),
            ]
        )


@dataclass
class PouringIntoAction(FullBodyControlledAction, HasManipulationCategory):
    """
    Pour the contents of a held container into a target: hold it above the target, offset towards the agent, and
    tilt it forward about the world x axis so the contents run out over the target.

    (coraplex's PouringAction chooses its pouring side relative to the arm; here the pouring direction is fixed by
    the operator's position in front of the machine.) Full-body controlled: the base may lean in, within collision
    avoidance, because the head lies beyond the arm's reach from a parked station.
    """

    arm: Arm
    """
    The arm holding the source container.
    """

    target: Body
    """
    The body poured into.
    """

    pour_height: float = 0.10
    """
    Height of the held container above the target's origin, in metres.
    """

    standoff: float = 0.14
    """
    Horizontal offset towards the agent (+y), in metres: the container's lip reaches ahead of the gripper and the
    contents fall ahead of the lip when tilted, so the stream lands over the target from this offset.
    """

    tilt_angle: float = 1.6
    """
    Forward tilt in radians.
    """

    grip: ApproachDirection = ApproachDirection.TOWARDS_SALES_FRONT
    """
    The direction the container was grasped from; it fixes the gripper's orientation while the container is held
    upright. (The plan is expanded before it runs, so the orientation must not be read from the current gripper.)
    """

    lift_from: Optional[Pose] = None
    """
    Where the container was picked up (its grip point). If given, it is first lifted straight up from there to the
    approach height and carried over at that height - a fixed, collision-free route instead of a diagonal through the
    target's surroundings.
    """

    may_touch: List[Body] = field(default_factory=list)
    """
    Bodies the arm may touch while reaching over to the target (the pan rim, the bubble), as a person rests a forearm
    on a rim; passed to every motion as a temporary collision allowance.

    Limitation (coraplex, 2026-10-20): the execution environment adds its collision-avoidance tasks before a motion's
    temporary rules apply, so this allowance does not lift the arm's buffer to the pan. Reaching over the 0.66 m pan
    with a PR2 therefore only succeeds when the pour runs with collision avoidance off (see demo.py).
    """

    position_tolerance: float = 0.03
    """
    How close the held container has to get to the pour pose, in metres: the stream only has to land in the target's
    opening (the spinner head's sugar inlet is ~0.06 m wide, twin register head_cap_top_diameter).
    """

    approach_lift: float = 0.15
    """
    How much higher than the pour pose, and 0.25 m nearer the agent, the container is carried first, so the arm
    clears the rim of the target's surroundings (e.g. the floss pan) with its elbow up.
    """

    @classproperty
    def manipulation_category(cls) -> ManipulationActionCategory:
        return ManipulationActionCategory.POURING

    @property
    def _action_plan(self) -> PlanNode:
        target = self.target.global_pose.to_np()
        upright = Rotation.from_euler("xyz", list(self.grip.value)).as_matrix()
        x, y, z = float(target[0, 3]), float(target[1, 3]) + self.standoff, float(target[2, 3]) + self.pour_height

        def oriented(rotation: np.ndarray, dy: float = 0.0, dz: float = 0.0) -> Pose:
            qx, qy, qz, qw = Rotation.from_matrix(rotation).as_quat()
            return Pose.from_xyz_quaternion(pos_x=x, pos_y=y + dy, pos_z=z + dz, quat_x=qx, quat_y=qy, quat_z=qz,
                                            quat_w=qw, reference_frame=self.world.root)

        tilt = Rotation.from_euler("x", self.tilt_angle).as_matrix()   # top of the held container towards -y
        lift = []
        if self.lift_from is not None:
            grip = self.lift_from.to_np()
            qx, qy, qz, qw = Rotation.from_matrix(upright).as_quat()
            lift = [
                MoveTCPMayTouchMotion(
                    Pose.from_xyz_quaternion(pos_x=float(grip[0, 3]), pos_y=float(grip[1, 3]),
                                             pos_z=z + self.approach_lift, quat_x=qx, quat_y=qy, quat_z=qz,
                                             quat_w=qw, reference_frame=self.world.root),
                    self.arm, allow_gripper_collision=True, may_touch=self.may_touch,
                )
            ]
        return sequential(
            lift
            + [
                MoveTCPMayTouchMotion(oriented(upright, 0.25, self.approach_lift), self.arm,
                                          allow_gripper_collision=True),
                MoveTCPMayTouchMotion(oriented(upright), self.arm, allow_gripper_collision=True, may_touch=self.may_touch,
                                          position_threshold=self.position_tolerance),
                MoveTCPMayTouchMotion(oriented(tilt @ upright), self.arm, allow_gripper_collision=True, may_touch=self.may_touch,
                                          position_threshold=self.position_tolerance),
                MoveTCPMayTouchMotion(oriented(upright), self.arm, allow_gripper_collision=True, may_touch=self.may_touch,
                                          position_threshold=self.position_tolerance),
                MoveTCPMayTouchMotion(oriented(upright, 0.25, self.approach_lift), self.arm,
                                          allow_gripper_collision=True),
            ]
            + lift
        )


@dataclass(kw_only=True)
class GatheringAction(ToolMotionAction, HasManipulationCategory):
    """
    Gather a fibrous or loose substance from a container onto a held instrument: dip the instrument's tip into it,
    sweep it around the container to accumulate the substance on the tip, and lift it out.
    """

    container: Body
    """
    The container the substance is gathered from.
    """

    sweep_radius: float = 0.20
    """
    Radius in metres of the arc the tip sweeps along, inside the container wall.
    """

    sweep_height: float = 0.0
    """
    Height of the sweep relative to the container origin.
    """

    arc_degrees: Tuple[float, float] = (40.0, 140.0)
    """
    Start and end of the arc, in degrees about the container's z axis from its +x axis; the default arc lies on the
    agent's side (+y) of the container ("roll cone in the web of floss building up in the pan", GM_MAN_EXP p. 11).
    """

    @classproperty
    def manipulation_category(cls) -> ManipulationActionCategory:
        return ManipulationActionCategory.GATHERING

    def _build_tool_path(self) -> ToolPath:
        r, h, lift = self.sweep_radius, self.sweep_height, 0.25
        start, end = (math.radians(angle) for angle in self.arc_degrees)

        def on_arc(tau: float) -> np.ndarray:
            angle = start + (end - start) * tau
            return np.array([r * math.cos(angle), r * math.sin(angle), h])

        return ToolPath(
            segments=[
                ToolPathSegment(
                    ToolPathSegmentKind.APPROACH, 1.0,
                    lambda tau: np.array([r * math.cos(start), r * math.sin(start), lift - (lift - h) * tau]),
                ),
                ToolPathSegment(ToolPathSegmentKind.SPIRAL, 3.0, on_arc),
                ToolPathSegment(
                    ToolPathSegmentKind.RETRACT, 1.0,
                    lambda tau: np.array([r * math.cos(end), r * math.sin(end), h + (lift - h) * tau]),
                ),
            ]
        )

    def _path_frame(self) -> HomogeneousTransformationMatrix:
        return self.container.global_pose.homogeneous_matrix

    @property
    def _alignment_target(self) -> Optional[Union[Body, Pose]]:
        return self.container


@dataclass(kw_only=True)
class WrappingAction(ToolMotionAction, HasManipulationCategory):
    """
    Wrap a loose substance around a held instrument with figure-eight strokes.
    """

    above: Body
    """
    The body the strokes are made above.
    """

    height: float = 0.30
    """
    Height of the strokes above the body's origin.
    """

    offset_towards_agent: float = 0.15
    """
    Horizontal offset of the strokes towards the agent (+y), in metres.
    """

    size: float = 0.10
    """
    Half width of the figure eight in metres.
    """

    cycles: int = 2
    """
    Number of figure eights.
    """

    @classproperty
    def manipulation_category(cls) -> ManipulationActionCategory:
        return ManipulationActionCategory.WRAPPING

    def _build_tool_path(self) -> ToolPath:
        a, z, n, dy = self.size, self.height, self.cycles, self.offset_towards_agent
        return ToolPath(
            segments=[
                ToolPathSegment(
                    ToolPathSegmentKind.STIR, 3.0,
                    lambda tau: np.array([a * math.sin(2 * math.pi * n * tau),
                                          dy + a * math.sin(2 * math.pi * n * tau) * math.cos(2 * math.pi * n * tau), z]),
                )
            ]
        )

    def _path_frame(self) -> HomogeneousTransformationMatrix:
        return self.above.global_pose.homogeneous_matrix

    @property
    def _alignment_target(self) -> Optional[Union[Body, Pose]]:
        return self.above


# %% surface treatment


@dataclass(kw_only=True)
class CategorisedWipingAction(WipingAction, HasManipulationCategory):
    """
    coraplex's wiping, labelled with its category.
    """

    @classproperty
    def manipulation_category(cls) -> ManipulationActionCategory:
        return ManipulationActionCategory.WIPING


# %% reading a plan as categories


def category_profile(action: ActionDescription) -> List[ManipulationActionCategory]:
    """
    The manipulation categories an action is composed of, in plan order: the action's own category if it has one,
    otherwise the categories of its children, recursively.

    :param action: An action whose plan has been built (attached to a plan with a context).
    """
    if isinstance(action, HasManipulationCategory):
        return [type(action).manipulation_category]
    profile = []
    for node in action._action_plan.children:
        designator = getattr(node, "designator", None)
        if isinstance(designator, HasManipulationCategory):
            profile.append(type(designator).manipulation_category)
        elif isinstance(designator, ActionDescription) and type(designator).__module__.startswith("cotton_candy"):
            sequential([designator], action.context)
            profile += category_profile(designator)
    return profile
