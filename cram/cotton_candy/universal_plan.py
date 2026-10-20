"""
A generalized plan for ``(perform (an action (type making-and-handing-over) (object ?candy)))``: make the candy the
robot is currently creating and hand it to the customer it is for, from whatever state the candy, the machine and
the booth are in.

Lineage (ResearchSpace ``foundation/okf/cram``):

* Beetz, *Concurrent Reactive Plans* (generalized routine plans): the plan is a sequence of ``(achieve G)`` sub-goals
  over entity designators. Every sub-goal is checked before it is acted on - a goal that already holds is skipped,
  which makes the plan idempotent and restartable. Designators ("the candy", "the stick it is on", "the sugar it is
  made of", "the customer it is for") are re-resolved against the belief state before every step. Protections guard
  effects later steps need (``PROTECTION :HARD (IN-HAND ?stick)``). Failures are handled by re-resolving and retrying
  within bounds. Each step carries a ``:TAG`` for plan revision. Irreversible steps (pouring sugar, spinning floss)
  are never repeated, because their goals are checked first.
* STRIPS triangle tables (Fikes, Hart & Nilsson 1972) give each sub-goal its *kernel*: the conditions under which
  the rest of the plan achieves the goal. PLANEX-style execution picks the highest-numbered sub-goal whose kernel
  holds, so achieved sub-goals are skipped and setbacks are repaired.
* Universal plans (Schoppers 1987): that selection maps every belief state to an action.
* RAPs (Firby 1987): each sub-goal is achieved by context-dependent methods and verified by its success test.

Limitation: protections are checked at step boundaries, after each executed step; they are not concurrent fluent
monitors (coraplex's ``MonitorNode`` watches giskard motion statecharts, not the process model).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from scipy.spatial.transform import Rotation
from typing_extensions import Any, Callable, Dict, List, Optional

from coraplex.datastructures.dataclasses import Context
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from krrood.entity_query_language.exceptions import MultipleSolutionFound
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.semantic_annotations.mixins import HasRootBody
from semantic_digital_twin.semantic_annotations.semantic_annotations import Human
from semantic_digital_twin.spatial_types.spatial_types import Pose

from cotton_candy.actions import (
    FillSpinnerHeadAction,
    FinishPortionAction,
    FormPortionAction,
    RefillSpinnerHeadAction,
    ServeCottonCandyAction,
    StartFlossMachineAction,
)
from cotton_candy.booth_world import RobotStation
from cotton_candy.designators import ServiceDesignators, resolve, resolve_or_none
from cotton_candy.manipulation_categories import ApproachDirection, PuttingDownAction, TransportingAction
from cotton_candy.process import CandyStage, CottonCandyBelief, FlossMachinePhase, FlossMachineProcess
from cotton_candy.semantic_annotations import CandyStick, Sponge, SugarCarton

logger = logging.getLogger(__name__)


# %% belief state


class Holding(Enum):
    """
    What the operating arm's gripper holds.
    """

    NOTHING = "nothing"
    STICK = "stick"
    OTHER = "other"


@dataclass
class ServiceBelief:
    """
    The belief state the plan conditions on: the designators resolved against the candy belief and the booth.
    """

    candy: CottonCandyBelief
    """
    "The candy I am making" (resolved).
    """

    stage: CandyStage
    """
    Its stage, reconciled with the world.
    """

    stick: Optional[CandyStick]
    """
    "The stick it is on", or a free stick before it is on one.
    """

    sugar: Optional[SugarCarton]
    """
    "The sugar it is made of": a carton holding all its ingredients, or None.
    """

    customer: Optional[Human]
    """
    "The customer it is for".
    """

    ingredients: List[Any]
    """
    Its ingredients (ontology materials).
    """

    phase: FlossMachinePhase
    """
    The machine's phase.
    """

    sugar_kg: float
    """
    Sugar in the head plus floss in the pan.
    """

    portion_kg: float
    """
    Sugar of one portion.
    """

    holding: Holding
    """
    What the gripper holds.
    """

    held: Optional[HasRootBody]
    """
    The held object, if any.
    """

    # %% fluents

    @property
    def gripper_free(self) -> bool:
        return self.holding is Holding.NOTHING

    @property
    def sugar_available(self) -> bool:
        return self.sugar is not None

    @property
    def enough_sugar(self) -> bool:
        return self.sugar_kg + 1e-9 >= self.portion_kg

    @property
    def producing(self) -> bool:
        return self.phase is FlossMachinePhase.PRODUCING

    @property
    def stick_in_hand(self) -> bool:
        return self.holding is Holding.STICK and self.held is self.stick

    @property
    def delivered(self) -> bool:
        return (self.stage is CandyStage.DELIVERED and self.customer is not None and self.stick is not None
                and self.stick.root.parent_kinematic_structure_entity is self.customer.root)


@dataclass
class BeliefEstimator:
    """
    Resolves the designators against the candy belief store and the booth, and reconciles belief with world.
    """

    process: FlossMachineProcess
    """
    The machine's process (with the candy belief store).
    """

    designators: ServiceDesignators
    """
    The service's entity designators.
    """

    arm: Arm
    """
    The operating arm.
    """

    graspables: List[HasRootBody]
    """
    The objects the gripper may hold.
    """

    def estimate(self, candy: CottonCandyBelief) -> ServiceBelief:
        d = self.designators
        tool = self.arm.end_effector.tool_frame
        held = next((o for o in self.graspables if o.root.parent_kinematic_structure_entity is tool), None)
        holding = Holding.NOTHING if held is None else Holding.STICK if isinstance(held, CandyStick) else Holding.OTHER
        stick = resolve_or_none(d.the_stick_of(candy))
        if stick is None and holding is Holding.STICK:
            stick = held
        stage = candy.stage
        # the world wins over the belief: a portion exists only on the held stick or with the customer
        if stage in (CandyStage.GATHERED, CandyStage.WRAPPED) and not (holding is Holding.STICK and held is stick):
            logger.warning("candy %d believed %s but its stick is not in hand: counted as lost", candy.order,
                           stage.value)
            candy.stage, candy.stick, stage = CandyStage.NONE, None, CandyStage.NONE
            stick = resolve_or_none(d.the_stick_of(candy))
        return ServiceBelief(
            candy=candy, stage=stage, stick=stick, sugar=resolve_or_none(d.the_sugar_for(candy)),
            customer=resolve_or_none(d.the_customer_of(candy)),
            ingredients=list(d.the_ingredients_of(candy).evaluate()),
            phase=self.process.phase, sugar_kg=self.process.sugar_in_head_kg + self.process.floss_in_pan_kg,
            portion_kg=self.process.timings.portion_sugar_kg, holding=holding, held=held,
        )


# %% sub-goals (achieve steps)


@dataclass
class AchieveStep:
    """
    One ``(achieve G)`` sub-goal of the generalized plan: its tag, goal (checked before acting), kernel (triangle
    table), methods (RAP) and the protection it establishes for later steps.
    """

    index: int
    """
    Its position in the plan (the goal is one past the last step).
    """

    tag: str
    """
    The ``:TAG`` the step is known by (for traces and plan revision).
    """

    goal: Callable[[ServiceBelief], bool]
    """
    What the step achieves; checked before acting.
    """

    kernel: Callable[[ServiceBelief], bool]
    """
    The conditions under which this step and all later ones achieve the plan's goal.
    """

    kernel_text: str
    """
    The kernel, written out.
    """

    methods: Callable[[ServiceBelief], List[ActionDescription]]
    """
    The designators that achieve the step in the given belief state.
    """

    protects: Optional[Callable[[ServiceBelief], bool]] = None
    """
    A condition this step establishes that must hold until the candy is delivered (``PROTECTION :HARD``).
    """


@dataclass
class Failure:
    """
    A failure description (``FAIL`` with a faildescrip).
    """

    tag: str
    """
    The step it happened in.
    """

    description: str
    """
    What went wrong.
    """


class GoalUnachievable(RuntimeError):
    """
    Raised when no sub-goal's kernel can be made to hold (e.g. there is no sugar for the ordered flavour).
    """


# %% the generalized plan


@dataclass
class MakeAndHandOverCandyPlan:
    """
    ``(perform (an action (type making-and-handing-over) (object (the candy I am making))))``.
    """

    context: Context
    """
    The plan context.
    """

    process: FlossMachineProcess
    """
    The machine's process.
    """

    designators: ServiceDesignators
    """
    The entity designators, re-resolved before every step.
    """

    estimator: BeliefEstimator
    """
    Resolves the designators and reconciles belief with world.
    """

    homes: Dict[str, Pose] = field(default_factory=dict)
    """
    Where held objects are put back (by root body name).
    """

    parents: Dict[str, Any] = field(default_factory=dict)
    """
    What held objects are put back into (by root body name): the body each was attached to when the plan was made.
    """

    max_retries: int = 2
    """
    How often a sub-goal may fail before the plan gives up.
    """

    trace: List[str] = field(default_factory=list)
    """
    The tags of the steps executed, in order.
    """

    failures: List[Failure] = field(default_factory=list)
    """
    The failures that occurred.
    """

    on_plan: Optional[Callable[[Any], None]] = None
    """
    Called with every sub-plan before it runs (e.g. to show it in a viewer).
    """

    def __post_init__(self):
        for obj in self.estimator.graspables:
            self.parents.setdefault(obj.root.name.name, obj.root.parent_kinematic_structure_entity)
            m = obj.root.global_pose.to_np()
            qx, qy, qz, qw = Rotation.from_matrix(m[:3, :3]).as_quat()
            self.homes.setdefault(obj.root.name.name, Pose.from_xyz_quaternion(
                pos_x=float(m[0, 3]), pos_y=float(m[1, 3]), pos_z=float(m[2, 3]),
                quat_x=qx, quat_y=qy, quat_z=qz, quat_w=qw, reference_frame=self.context.world.root,
            ))

    @property
    def arm(self) -> Arm:
        return self.estimator.arm

    def _station(self, station: RobotStation) -> Pose:
        return station.pose(self.context.world.root)

    # %% the plan's sub-goals

    def steps(self) -> List[AchieveStep]:
        p, arm = self.process, self.arm
        machine = resolve(self.designators.the_machine())
        return [
            AchieveStep(0, "FREE-GRIPPER", lambda b: b.gripper_free, lambda b: True, "true", self._free_gripper),
            AchieveStep(1, "MACHINE-READY", lambda b: b.producing and b.enough_sugar,
                        lambda b: b.gripper_free and b.sugar_available,
                        "gripper free AND there is sugar for the candy", self._make_ready),
            AchieveStep(2, "STICK-IN-HAND", lambda b: b.stick_in_hand,
                        lambda b: b.gripper_free and b.producing and b.enough_sugar and b.stick is not None,
                        "gripper free AND producing AND sugar >= portion AND a stick for the candy",
                        lambda b: [MoveTorsoAction(TorsoState.LOW),
                                   TransportingAction(b.stick, arm, ApproachDirection.TOWARDS_LEFT_WALL)],
                        protects=lambda b: b.stick_in_hand or b.delivered),
            AchieveStep(3, "CANDY-FORMED", lambda b: b.stage in (CandyStage.WRAPPED, CandyStage.DELIVERED),
                        lambda b: b.stick_in_hand and b.stage is CandyStage.NONE and b.producing and b.enough_sugar,
                        "stick in hand AND candy not started AND producing AND sugar >= portion",
                        lambda b: [FormPortionAction(machine, p, b.stick, arm)]),
            AchieveStep(4, "CANDY-WRAPPED", lambda b: b.stage in (CandyStage.WRAPPED, CandyStage.DELIVERED),
                        lambda b: b.stick_in_hand and b.stage is CandyStage.GATHERED,
                        "stick in hand AND floss gathered",
                        lambda b: [FinishPortionAction(machine, p, b.stick, arm)]),
            AchieveStep(5, "HANDED-OVER", lambda b: b.delivered,
                        lambda b: b.stick_in_hand and b.stage is CandyStage.WRAPPED and b.customer is not None,
                        "stick in hand AND candy wrapped AND the customer it is for is there",
                        lambda b: [ServeCottonCandyAction(b.stick, resolve(self.designators.the_handover_zone()),
                                                          arm, self._station(RobotStation.SERVING),
                                                          self._station(RobotStation.MACHINE),
                                                          customer=b.customer, process=p)]),
        ]

    @staticmethod
    def goal(belief: ServiceBelief) -> bool:
        """
        The plan's goal: the customer the candy is for holds it.
        """
        return belief.delivered

    # %% RAP methods

    def _free_gripper(self, belief: ServiceBelief) -> List[ActionDescription]:
        """
        Put back whatever is held (an empty stick goes back into the quiver while the machine is made ready).
        """
        if belief.held is None:
            return []
        name = belief.held.root.name.name
        return [PuttingDownAction(belief.held, self.homes[name], new_parent=self.parents.get(name))]

    def _make_ready(self, belief: ServiceBelief) -> List[ActionDescription]:
        """
        Bring the machine to producing with sugar for the candy: fill and start, start, or refill - with the sugar
        designated for the candy.
        """
        machine, p, arm = resolve(self.designators.the_machine()), self.process, self.arm
        stations = (self._station(RobotStation.MACHINE), self._station(RobotStation.MACHINE_CLOSE))
        if belief.phase is FlossMachinePhase.OFF:
            fill = [] if belief.enough_sugar else [FillSpinnerHeadAction(machine, p, belief.sugar, arm, *stations)]
            return fill + [StartFlossMachineAction(machine, p, arm)]
        if not belief.enough_sugar:
            return [RefillSpinnerHeadAction(machine, p, belief.sugar, arm, *stations)]
        return [] if belief.producing else [StartFlossMachineAction(machine, p, arm)]

    # %% interpretation

    def the_candy(self) -> CottonCandyBelief:
        """
        :return: "The candy I am making" (``the``: exactly one open order, else the plan cannot know what to make).
        """
        return resolve(self.designators.the_candy())

    def select(self, belief: ServiceBelief) -> Optional[AchieveStep]:
        """
        PLANEX: the highest-numbered sub-goal whose kernel holds and whose goal does not yet hold, or None when the
        plan's goal holds.

        :raises GoalUnachievable: When no kernel holds.
        """
        if self.goal(belief):
            return None
        candidates = [s for s in self.steps() if s.kernel(belief) and not s.goal(belief)]
        if not candidates:
            raise GoalUnachievable(
                f"no sub-goal applies for candy {belief.candy.order} ({belief.candy.flavour}): "
                f"sugar for it {'available' if belief.sugar_available else 'NOT available'}, "
                f"stick for it {'available' if belief.stick is not None else 'NOT available'}, "
                f"customer {'there' if belief.customer else 'not found'}"
            )
        return max(candidates, key=lambda s: s.index)

    def projection(self, belief: ServiceBelief) -> List[str]:
        """
        :return: The tags of the sub-goals that remain, from the selected one to the end, skipping those whose goals
            already hold (check-before-act).
        """
        step = self.select(belief)
        if step is None:
            return []
        return [s.tag for s in self.steps()[step.index:] if not s.goal(belief) or s.index == step.index]

    def perform(self, max_cycles: int = 14) -> ServiceBelief:
        """
        Check the goal; while it does not hold, re-resolve the designators, select the sub-goal (PLANEX), execute its
        method, check the protections, and handle failures by retrying from the re-estimated state.
        """
        protections: List[AchieveStep] = []
        retries: Dict[str, int] = {}
        for _ in range(max_cycles):
            belief = self.estimator.estimate(self.the_candy() if self._open_order() else self._last_candy())
            for step in list(protections):
                if not step.protects(belief):
                    self.failures.append(Failure(step.tag, "protection violated"))
                    protections.remove(step)
            step = self.select(belief)
            if step is None:
                return belief
            self.trace.append(step.tag)
            try:
                designators = step.methods(belief)
                if designators:
                    sub_plan = sequential(designators, self.context)
                    if self.on_plan is not None:
                        self.on_plan(sub_plan)
                    sub_plan.perform()
                if step.protects is not None and step not in protections:
                    protections.append(step)
            except (GoalUnachievable, MultipleSolutionFound):
                raise
            except Exception as failure:   # with-failure-handling: re-resolve and retry, bounded
                retries[step.tag] = retries.get(step.tag, 0) + 1
                self.failures.append(Failure(step.tag, f"{type(failure).__name__}: {failure}"[:200]))
                logger.warning("sub-goal %s failed (%s), re-resolving", step.tag, type(failure).__name__)
                if retries[step.tag] > self.max_retries:
                    raise
        raise GoalUnachievable("the plan did not reach its goal within its cycles")

    def _open_order(self) -> bool:
        return any(c.stage is not CandyStage.DELIVERED for c in self.process.candies)

    def _last_candy(self) -> CottonCandyBelief:
        return self.process.candies[-1]


def make_and_hand_over(context: Context, process: FlossMachineProcess, materials: List[Any]) -> MakeAndHandOverCandyPlan:
    """
    :return: The generalized plan for the booth world of ``context`` (the candy is whatever order is open in the
        process's belief store when the plan runs).
    """
    world = context.world
    designators = ServiceDesignators(process, world, materials, context.robot.right_arm.end_effector.tool_frame)
    graspables = (world.get_semantic_annotations_by_type(CandyStick) + world.get_semantic_annotations_by_type(SugarCarton)
                  + world.get_semantic_annotations_by_type(Sponge))
    estimator = BeliefEstimator(process, designators, context.robot.right_arm, graspables)
    return MakeAndHandOverCandyPlan(context, process, designators, estimator)
