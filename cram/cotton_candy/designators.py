"""
Entity designators of the cotton candy service: symbolic descriptions ("the candy I am making", "the stick it is
on", "the sugar it is made of", "the customer it is for") that are resolved against the robot's belief state - the
candy belief store and the booth's scene graph - each time the plan needs them.

Each designator is an EQL query (krrood): ``the(...)`` for descriptions that must denote exactly one entity, ``a(...)``
for descriptions any matching entity satisfies. Re-resolving them after every step lets the plan follow the world:
"the stick" is a free stick in the quiver before one is taken, and the held stick afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, List, Optional

from krrood.entity_query_language.factories import a, an, and_, contains, entity, the, variable
from semantic_digital_twin.semantic_annotations.semantic_annotations import Human

from cotton_candy.process import CandyStage, CottonCandyBelief, FlossMachineProcess
from cotton_candy.semantic_annotations import (
    CandyStick,
    CottonCandyMachine,
    HandoverZone,
    StickQuiver,
    SugarCarton,
)


def resolve(designator) -> Any:
    """
    :return: The entity a designator denotes (all solutions are materialised, so ``the`` raises when there is not
        exactly one; for ``a``/``an`` the first solution is taken).
    """
    solutions = list(designator.evaluate())
    if not solutions:
        raise LookupError(f"the designator denotes nothing: {designator}")
    return solutions[0]


def resolve_or_none(designator) -> Optional[Any]:
    """
    :return: The first entity a designator denotes, or None when it denotes nothing.
    """
    solutions = list(designator.evaluate())
    return solutions[0] if solutions else None


@dataclass
class ServiceDesignators:
    """
    The designators of the service, over the belief state they are matched against.
    """

    process: FlossMachineProcess
    """
    The machine's process, holding the candy belief store.
    """

    world: Any
    """
    The booth's scene graph (CRAM world).
    """

    materials: List[Any]
    """
    The ontology's materials (ingredients are matched against them).
    """

    tool_frame: Any = None
    """
    The operating gripper's tool frame (an empty stick held there is the stick for a candy not yet on one).
    """

    # %% the candy

    def the_candy(self):
        """
        "The candy I am making": the one ordered portion that is not delivered yet.
        """
        candy = variable(CottonCandyBelief, self.process.candies)
        return the(entity(candy).where(candy.stage != CandyStage.DELIVERED))

    # %% its action context

    def the_stick_of(self, candy: CottonCandyBelief):
        """
        "The stick the candy is on"; before the candy is on a stick, "the empty stick in hand", else "a free stick in
        the quiver".
        """
        stick = variable(CandyStick, self.world.semantic_annotations)
        if candy.stick is not None:
            return the(entity(stick).where(stick.root.name.name == candy.stick))
        if self.tool_frame is not None:
            in_hand = a(entity(stick).where(stick.root.parent_kinematic_structure_entity == self.tool_frame))
            if resolve_or_none(in_hand) is not None:
                return in_hand
            stick = variable(CandyStick, self.world.semantic_annotations)
        quiver = resolve(the(entity(variable(StickQuiver, self.world.semantic_annotations))))
        return a(entity(stick).where(stick.root.parent_kinematic_structure_entity == quiver.root))

    def the_ingredients_of(self, candy: CottonCandyBelief):
        """
        "The ingredients of the candy": the ontology's materials named in the candy's order.
        """
        material = variable(type(self.materials[0]), self.materials)
        return an(entity(material).where(contains(candy.ingredients, material.name)))

    def the_sugar_for(self, candy: CottonCandyBelief):
        """
        "The sugar for the candy": a sugar carton whose contents include every ingredient of the candy.
        """
        carton = variable(SugarCarton, self.world.semantic_annotations)
        return a(entity(carton).where(and_(*[contains(carton.contents, i) for i in candy.ingredients])))

    def the_customer_of(self, candy: CottonCandyBelief):
        """
        "The customer the candy is for" (any customer if the order names none).
        """
        customer = variable(Human, self.world.semantic_annotations)
        if candy.ordered_by is None:
            return a(entity(customer))
        return the(entity(customer).where(customer.root.name.name == candy.ordered_by))

    def the_machine(self):
        """
        "The floss machine".
        """
        return the(entity(variable(CottonCandyMachine, self.world.semantic_annotations)))

    def the_handover_zone(self):
        """
        "The handover zone".
        """
        return the(entity(variable(HandoverZone, self.world.semantic_annotations)))
