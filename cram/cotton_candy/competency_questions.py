"""
Competency questions of the cotton candy production ontology, as EQL presets for cramera's query panel.

The questions range over the ontology's individuals (which link to the scene graph's semantic annotations) and over
the live state of the world and the machine's process. Each question names the competence it tests; the expected
answers are checked in ``tests/test_competency_questions.py`` against hand-curated gold answers.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, Dict, List

from cramera.knowledge.presets import Preset
from cramera.knowledge.query_domain import QueryDomain
from cramera.knowledge.queryable_knowledge import QueryableKnowledge, QueryScope

from cotton_candy.ontology.production import (
    Artefact,
    CottonCandyProductionOntology,
    Hazard,
    ManipulationCategoryNode,
    Material,
    ProductionStep,
    ProductQuality,
    RegisterEntry,
    Regulation,
    SafetyMeasure,
)
from cotton_candy.process import CandyStage, CottonCandyBelief, FlossMachineProcess


# %% the questions


@dataclass(frozen=True)
class CompetencyQuestion:
    """
    A question the ontology must be able to answer.
    """

    competence: str
    """
    What kind of knowledge it tests (procedure, grounding, categories, materials, hazards, regulation, data quality,
    process physics, live state).
    """

    text: str
    """
    The question as asked (German, as the booth's operators would ask it).
    """

    code: str
    """
    The EQL query that answers it.
    """

    @property
    def preset(self) -> Preset:
        """
        :return: The question as a cramera preset.
        """
        return Preset(f"[{self.competence}] {self.text}", self.code, requires_live=True)


QUESTIONS: List[CompetencyQuestion] = [
    CompetencyQuestion("Ablauf", "Welche Schritte hat eine Schicht, in welcher Reihenfolge, wer fuehrt sie aus?",
                       "set_of(step.order, step.name, step.designator_name, step.performed_by)"),
    CompetencyQuestion("Ablauf", "Was muss gelten, bevor Zucker in den Spinnkopf gefuellt werden darf?",
                       "an(entity(step.precondition).where(step.designator_name == 'FillSpinnerHeadAction'))"),
    CompetencyQuestion("Kategorien", "Welche Schritte enthalten 'Pressing Button'?",
                       "an(entity(step.name).where(contains(step.category_names, 'PressingButton')))"),
    CompetencyQuestion("Kategorien", "Aus welchen Manipulationskategorien besteht das Starten der Maschine?",
                       "an(entity(step.category_names).where(step.designator_name == 'StartFlossMachineAction'))"),
    CompetencyQuestion("Kategorien", "Welche Kategorien stammen aus dem CRAM-L2-Modul, welche sind neu vorgeschlagen?",
                       "set_of(category.name, category.parent, category.defined_in)"),
    CompetencyQuestion("Verankerung", "Auf welche Teile wirkt das Starten der Maschine?",
                       "an(entity(step.acts_on_names).where(step.designator_name == 'StartFlossMachineAction'))"),
    CompetencyQuestion("Verankerung", "Welche semantische Annotation steht fuer welches Ontologie-Individuum?",
                       "set_of(artefact.name, artefact.annotation_type, artefact.kind)"),
    CompetencyQuestion("Verankerung", "Welche Teile gehoeren zur Zuckerwattemaschine?",
                       "an(entity(artefact.name).where(artefact.part_of_name == 'FlossMachineCabinet'))"),
    CompetencyQuestion("Zutaten", "Welche Zutaten verlangen einen Warnhinweis, und welche E-Nummer haben sie?",
                       "set_of(material.name, material.e_number).where(material.requires_warning == True)"),
    CompetencyQuestion("Zutaten", "Welche Allergene enthaelt die pinke Zuckerwatte?",
                       "set_of(material.name, material.allergen).where(material.allergen != '')"),
    CompetencyQuestion("Gefahren", "Welche Gefahren gibt es, woher kommen sie, was mindert sie?",
                       "set_of(hazard.name, hazard.caused_by_name, hazard.mitigation_names)"),
    CompetencyQuestion("Vorschriften", "Welche Vorschrift wird durch welches Objekt im Stand erfuellt?",
                       "set_of(regulation.name, regulation.reference, regulation.satisfied_by_names)"),
    CompetencyQuestion("Datenqualitaet", "Welche Werte sind nur ILLUSTRATIVE (Annahmen dieser Rekonstruktion)?",
                       "set_of(entry.key, entry.value, entry.note).where(entry.status == 'ILLUSTRATIVE')"),
    CompetencyQuestion("Prozessphysik", "Bei welcher Luftfeuchte faellt Zuckerwatte zusammen, wie sicher ist das?",
                       "set_of(quality.name, quality.value, quality.unit, quality.status)"
                       ".where(contains(quality.name, 'humidity'))"),
    CompetencyQuestion("Live", "Welche brennbaren Objekte liegen gerade naeher als 0,6 m am Heizband?",
                       "set_of(artefact.name, artefact.distance_to_heating_band)"
                       ".where(artefact.combustible == True, artefact.distance_to_heating_band < 0.6)"),
    CompetencyQuestion("Belief", "Wie weit ist die Zuckerwatte, die ich gerade mache, und wofuer ist sie?",
                       "set_of(candy.order, candy.flavour, candy.stage, candy.stick, candy.ordered_by)"
                       ".where(candy.stage != CandyStage.DELIVERED)"),
    CompetencyQuestion("Belief", "Welche Zuckerwatten wurden schon an wen uebergeben?",
                       "set_of(candy.order, candy.flavour, candy.customer).where(candy.stage == CandyStage.DELIVERED)"),
    CompetencyQuestion("Live", "In welcher Phase ist die Maschine, wie viel Zucker ist im Kopf, wie viele Portionen?",
                       "set_of(process.phase, process.sugar_in_head_kg, process.floss_in_pan_kg, "
                       "process.portions_served)"),
]


# %% the knowledge source for cramera


@dataclass
class CottonCandyKnowledgeSource:
    """
    The ontology and the live process, offered to cramera's query panel.
    """

    ontology: CottonCandyProductionOntology
    """
    The production ontology.
    """

    process: FlossMachineProcess
    """
    The machine's live process.
    """

    world: Any
    """
    The CRAM world (also queryable natively).
    """

    def title(self) -> str:
        return "Zuckerwatte-Produktion"

    def domains(self) -> List[QueryDomain]:
        o = self.ontology
        return [
            QueryDomain("step", ProductionStep, o.steps),
            QueryDomain("artefact", Artefact, o.artefacts),
            QueryDomain("material", Material, o.materials),
            QueryDomain("hazard", Hazard, o.hazards),
            QueryDomain("measure", SafetyMeasure, o.measures),
            QueryDomain("regulation", Regulation, o.regulations),
            QueryDomain("entry", RegisterEntry, o.register),
            QueryDomain("category", ManipulationCategoryNode, o.categories),
            QueryDomain("quality", ProductQuality, o.qualities),
            QueryDomain("process", FlossMachineProcess, [self.process]),
            QueryDomain("candy", CottonCandyBelief, self.process.candies),
        ]

    def knowledge(self) -> List[QueryableKnowledge]:
        return [
            QueryableKnowledge(
                scope=QueryScope.CURRENT_STATE,
                domains=self.domains(),
                extra_names={"world": self.world, "CandyStage": CandyStage},
            )
        ]

    def presets(self) -> List[Preset]:
        return [question.preset for question in QUESTIONS]

    def register_on(self, bridge) -> None:
        """
        Offer this knowledge in a cramera live bridge's query panel.
        """
        bridge.register_query_source(self.knowledge(), self.title(), self.presets())
