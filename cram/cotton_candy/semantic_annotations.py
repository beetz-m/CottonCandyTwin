"""
Semantic annotations of the cotton candy booth: the floss machine and its operating elements, the tools and
consumables the robot handles, and the booth itself.

The machine follows the Gold Medal Econo Floss 3017 export manual (twin register, source ``GM_MAN_EXP``): a
"Motor & Master" and a "Heat" lighted rocker switch, a heat control knob, two Lock-N-Go transport handles, a
spinner head that rotates at up to 3450 rpm inside an aluminium floss pan with a floss stabilizer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import List, Union

from krrood.ormatic.utils import classproperty
from semantic_digital_twin.datastructures.alignment import AlignmentPair
from semantic_digital_twin.semantic_annotations.mixins import (
    HasHandle,
    HasMovableJoint,
    HasRootBody,
    PartWholeRelationship,
)
from semantic_digital_twin.semantic_annotations.part_whole import IsPartWholeRelationship
from semantic_digital_twin.semantic_annotations.semantic_annotations import (
    Container,
    Food,
    Tool,
)
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Pose, Vector3
from semantic_digital_twin.world_description.world_entity import Body


# %% operating elements


@dataclass(eq=False)
class OperatingElement(HasMovableJoint):
    """
    A control of a machine that is moved about or along its own joint, such as a switch, a knob or a lever.

    Its joint turns about the element's own origin, so the joint frame is the element frame.
    """

    def calculate_self_T_movable_joint(self, axis: Vector3) -> HomogeneousTransformationMatrix:
        """
        :param axis: The axis the element moves about, in the element frame.
        :return: The identity: the element turns about its own origin.
        """
        return HomogeneousTransformationMatrix()

    @property
    def travel_fraction(self) -> float:
        """
        :return: How far the element stands between the lower (0) and the upper (1) end of its joint range.
        """
        limits = self.movable_joint.dof.limits
        return (self.movable_joint.position - limits.lower.position) / (
            limits.upper.position - limits.lower.position
        )


@dataclass(eq=False)
class RockerSwitch(OperatingElement):
    """
    A two-position lighted rocker switch: OFF at the lower end of its joint range, ON at the upper end.
    """

    @classproperty
    def on_fraction(cls) -> float:
        """
        The travel fraction above which the rocker counts as switched on.
        """
        return 0.5

    @property
    def is_on(self) -> bool:
        """
        :return: Whether the rocker stands in its ON position.
        """
        return self.travel_fraction > self.on_fraction


@dataclass(eq=False)
class ControlKnob(OperatingElement):
    """
    A rotary control whose turn sets a continuous quantity, here the power of the heating element.

    Clockwise (towards the upper end of the joint range) increases the setting.
    """


@dataclass(eq=False)
class LockHandle(OperatingElement):
    """
    A Lock-N-Go handle that clamps the floating bell housing for transport.

    LOCKED at the lower end of its joint range, UNLOCKED at the upper end; the machine must not run locked.
    """

    @property
    def is_unlocked(self) -> bool:
        """
        :return: Whether the handle stands in its UNLOCKED (operating) position.
        """
        return self.travel_fraction > 0.5


@dataclass(eq=False)
class SpinnerHead(OperatingElement):
    """
    The spinner head: sugar poured into its top is melted at the heating ribbon and spun out through the slots
    of its floss band as fibres.
    """


@dataclass(eq=False)
class FlossPan(Container):
    """
    The pan around the spinner head in which the floss collects on the floss stabilizer.
    """


# %% the machine


@dataclass(eq=False)
class CottonCandyMachine(HasRootBody, PartWholeRelationship):
    """
    A cotton candy (candy floss) machine with its operating elements, spinner head and floss pan.
    """

    motor_switch: RockerSwitch | None = field(default=None, metadata=IsPartWholeRelationship().as_dict())
    """
    The "Motor & Master" switch: runs the motor and powers the heat switch.
    """

    heat_switch: RockerSwitch | None = field(default=None, metadata=IsPartWholeRelationship().as_dict())
    """
    The "Heat" switch: powers the heating ribbon in the spinner head.
    """

    heat_control: ControlKnob | None = field(default=None, metadata=IsPartWholeRelationship().as_dict())
    """
    The heat control knob: sets the power of the heating ribbon.
    """

    spinner_head: SpinnerHead | None = field(default=None, metadata=IsPartWholeRelationship().as_dict())
    """
    The spinner head the sugar is poured into.
    """

    floss_pan: FlossPan | None = field(default=None, metadata=IsPartWholeRelationship().as_dict())
    """
    The pan the floss is collected from.
    """

    lock_handles: List[LockHandle] = field(
        default_factory=list, hash=False, kw_only=True, metadata=IsPartWholeRelationship().as_dict()
    )
    """
    The Lock-N-Go transport handles.
    """


# %% tools and consumables


@dataclass(eq=False)
class SugarScoop(Tool, Container):
    """
    A scoop that holds one portion of floss sugar and is tipped over the spinner head to fill it.
    """

    def tool_alignment(self, target: Union[Body, Pose]) -> List[AlignmentPair]:
        return [
            AlignmentPair(
                tip_normal=Vector3(0, 0, 1, reference_frame=self.root),
                goal_normal=Vector3(0, 0, 1, reference_frame=target),
            )
        ]


@dataclass(eq=False)
class SugarCarton(Tool, Container):
    """
    A half-gallon Flossugar carton with an "E-Z pour spout for filling your machine" (GM_MAN_EXP p. 9).

    Its tool frame (``<root>_end_effector``) is the spout on top; held near its bottom and tilted forward, the spout
    reaches over the spinner head from the near side of the pan.
    """

    def tool_alignment(self, target: Union[Body, Pose]) -> List[AlignmentPair]:
        return [
            AlignmentPair(
                tip_normal=Vector3(0, 0, 1, reference_frame=self.root),
                goal_normal=Vector3(0, 0, 1, reference_frame=target),
            )
        ]


@dataclass(eq=False)
class CandyStick(Tool):
    """
    A wooden stick (40 cm, 4 x 4 mm pine) the floss is wound onto.

    The stick's root frame has its x axis along the stick towards the tip that collects the floss; the tip
    points down into the pan while the floss is gathered.
    """

    def tool_alignment(self, target: Union[Body, Pose]) -> List[AlignmentPair]:
        return [
            AlignmentPair(
                tip_normal=Vector3(1, 0, 0, reference_frame=self.root),
                goal_normal=Vector3(0, 0, -1, reference_frame=target),
            )
        ]


@dataclass(eq=False)
class SugarTray(Container):
    """
    The stainless Gastronorm 1/6 container that holds the working sugar next to the machine.
    """


@dataclass(eq=False)
class StickQuiver(HasRootBody):
    """
    The wall quiver that holds the unused candy sticks.
    """


@dataclass(eq=False)
class CottonCandy(Food):
    """
    A portion of cotton candy: amorphous sucrose fibres wound onto a stick.
    """


@dataclass(eq=False)
class Sponge(Tool):
    """
    A damp cloth sponge used to wipe the machine after it has cooled down.
    """

    def tool_alignment(self, target: Union[Body, Pose]) -> List[AlignmentPair]:
        frame = target if isinstance(target, Body) else target.reference_frame
        return [
            AlignmentPair(
                tip_normal=Vector3(0, 0, -1, reference_frame=self.root),
                goal_normal=Vector3(0, 0, -1, reference_frame=frame),
            )
        ]


# %% the booth


@dataclass(eq=False)
class SalesFlap(OperatingElement, HasHandle):
    """
    The top-hinged sales flap of the booth front; raised it serves as an awning over the customers.
    """


@dataclass(eq=False)
class HandoverZone(HasRootBody):
    """
    The region in the flap opening where a portion is handed to a customer.
    """


@dataclass(eq=False)
class HandwashStation(HasRootBody):
    """
    The hand-wash station with running water required for stands selling unpackaged food
    (Reg. (EC) 852/2004 Annex II Ch. III 2(a)).
    """


@dataclass(eq=False)
class FireExtinguisher(HasRootBody):
    """
    The 6 kg ABC powder extinguisher (EN 3) required per stand by the market regulations.
    """


@dataclass(eq=False)
class InformationBoard(HasRootBody):
    """
    The board at the counter with price, the colour declaration "mit Farbstoff", the azo-dye warning for E129 and
    the milk (lactose) allergen information.
    """


@dataclass(eq=False)
class CottonCandyBooth(HasRootBody, PartWholeRelationship):
    """
    A 2 x 2 m wooden fairground booth selling cotton candy.
    """

    machine: CottonCandyMachine | None = field(default=None, metadata=IsPartWholeRelationship().as_dict())
    """
    The floss machine of the booth.
    """

    sales_flap: SalesFlap | None = field(default=None, metadata=IsPartWholeRelationship().as_dict())
    """
    The sales flap the customers are served through.
    """
