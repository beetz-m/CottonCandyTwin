"""
Whether a gripper is free or holds something, as EQL predicates.

coraplex had ``GripperIsFree`` and ``GripperIsNotFree`` until November 2026; CRAM main keeps only their base,
:class:`~coraplex.querying.predicates.GripperOccupancy`, and ``GripperHolds``. The booth's designator conditions ask
whether the operating gripper is free, so the two predicates are kept here with the same meaning: something is held
when the kinematic structure below the tool frame is not empty.
"""

from __future__ import annotations

from dataclasses import dataclass

from coraplex.querying.predicates import GripperOccupancy
from krrood.entity_query_language.predicate import Predicate, RenderedFields
from krrood.entity_query_language.verbalization.fragments.base import VerbalizationFragment
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import Adjective, Copula, Noun, clause


@dataclass
class GripperIsFree(GripperOccupancy, Predicate):
    """
    The gripper holds nothing.
    """

    def __call__(self) -> bool:
        return self.check_manipulator_occupancy(lambda bodies: len(bodies) == 0)

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        :return: The clause *"<end effector> is free"*.
        """
        return clause(Noun(fields["end_effector"]), Copula(), Adjective("free"))


@dataclass
class GripperIsNotFree(GripperOccupancy, Predicate):
    """
    The gripper holds something.
    """

    def __call__(self) -> bool:
        return self.check_manipulator_occupancy(lambda bodies: len(bodies) != 0)

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        :return: The clause *"<end effector> is occupied"*.
        """
        return clause(Noun(fields["end_effector"]), Copula(), Adjective("occupied"))
