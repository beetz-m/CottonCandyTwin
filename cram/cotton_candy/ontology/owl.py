"""
OWL 2 export (functional-style syntax) of the cotton candy production ontology.

The TBox mirrors the dataclasses of :mod:`.production` and places the manipulation action categories under the
effect classes of the CRAM action-category module (``action-category-dl.md``); the ABox carries every individual
with its links. Individuals that stand for things in the booth carry the semantic annotation class and body name of
the CRAM world (and the Isaac Sim prim name) as data properties, so the ontology node and the scene-graph node stay
distinct but joined (the Cuxhaven OKF commitment: an SDT node is not its referent).

Run: cram/run.sh python -m cotton_candy.ontology.owl  (writes ontology/build/cotton_candy_production.ofn in the twin)
"""

from __future__ import annotations

import os
import re

from typing_extensions import Iterable, List

from cotton_candy.ontology.production import CottonCandyProductionOntology

PREFIX = "https://aicor.ai/twins/cotton-candy#"


def iri(name: str) -> str:
    """
    :return: The prefixed IRI of a name (characters outside [A-Za-z0-9_] become underscores).
    """
    return ":" + re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_")


def literal(value) -> str:
    """
    :return: An OWL literal for a Python value.
    """
    if isinstance(value, bool):
        return f'"{str(value).lower()}"^^xsd:boolean'
    if isinstance(value, (int, float)):
        return f'"{value}"^^xsd:decimal'
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def tbox(ontology: CottonCandyProductionOntology) -> List[str]:
    """
    :return: Axioms of the class level: domain classes, the category taxonomy, properties.
    """
    axioms = []
    classes = ["ProductionStep", "Artefact", "Material", "Hazard", "SafetyMeasure", "Regulation", "RegisterEntry",
               "ProductQuality", "ManipulationActionCategory", "EvidenceStatus"]
    axioms += [f"Declaration(Class({iri(c)}))" for c in classes]
    for effect in ("ObjectDisplacement", "ConfigurationChange", "SubstanceManipulation", "SurfaceTreatment",
                   "InteractionAction", "MaintenanceAction", "PerceptionAction", "Transferring"):
        axioms += [f"Declaration(Class({iri(effect)}))"]
    for effect in ("ObjectDisplacement", "ConfigurationChange", "SubstanceManipulation", "SurfaceTreatment",
                   "InteractionAction", "MaintenanceAction", "PerceptionAction"):
        axioms.append(f"SubClassOf({iri(effect)} {iri('ManipulationActionCategory')})")
    axioms.append(f"SubClassOf({iri('Transferring')} {iri('SubstanceManipulation')})")
    for category in ontology.categories:
        axioms += [f"Declaration(Class({iri(category.name)}))",
                   f"SubClassOf({iri(category.name)} {iri(category.parent)})",
                   f"AnnotationAssertion(rdfs:comment {iri(category.name)} {literal('defined in ' + category.defined_in)})"]
    for kind in sorted({a.kind.value for a in ontology.artefacts}):
        axioms += [f"Declaration(Class({iri(kind)}))", f"SubClassOf({iri(kind)} {iri('Artefact')})"]
    for kind in sorted({m.kind.value for m in ontology.materials}):
        axioms += [f"Declaration(Class({iri(kind)}))", f"SubClassOf({iri(kind)} {iri('Material')})"]
    object_properties = ["hasCategory", "actsOn", "partOf", "causedBy", "mitigatedBy", "implementedBy",
                         "enforcedIn", "requiredBy", "satisfiedBy", "hasEvidenceStatus", "describedBy"]
    data_properties = ["order", "designator", "taskFamily", "precondition", "effect", "manualReference",
                       "performedBy", "annotationClass", "sceneBody", "eNumber", "requiresWarning", "allergen",
                       "value", "unit", "source", "reference", "requirement", "combustible"]
    axioms += [f"Declaration(ObjectProperty({iri(p)}))" for p in object_properties]
    axioms += [f"Declaration(DataProperty({iri(p)}))" for p in data_properties]
    axioms.append(f"ObjectPropertyDomain({iri('hasCategory')} {iri('ProductionStep')})")
    axioms.append(f"ObjectPropertyRange({iri('hasCategory')} {iri('ManipulationActionCategory')})")
    axioms.append(f"ObjectPropertyDomain({iri('actsOn')} {iri('ProductionStep')})")
    axioms.append(f"ObjectPropertyRange({iri('actsOn')} {iri('Artefact')})")
    axioms.append(f"TransitiveObjectProperty({iri('partOf')})")
    return axioms


def abox(ontology: CottonCandyProductionOntology) -> List[str]:
    """
    :return: Axioms of the individuals and their links.
    """
    axioms = []

    def individual(name: str, cls: str) -> str:
        axioms.append(f"Declaration(NamedIndividual({iri(name)}))")
        axioms.append(f"ClassAssertion({iri(cls)} {iri(name)})")
        return name

    def link(prop: str, a: str, b: str) -> None:
        axioms.append(f"ObjectPropertyAssertion({iri(prop)} {iri(a)} {iri(b)})")

    def data(prop: str, a: str, value) -> None:
        axioms.append(f"DataPropertyAssertion({iri(prop)} {iri(a)} {literal(value)})")

    for status in sorted({e.status.value for e in ontology.register}):
        individual("status_" + status, "EvidenceStatus")
    for entry in ontology.register:
        n = individual("register_" + entry.key, "RegisterEntry")
        data("value", n, entry.value if isinstance(entry.value, (int, float, bool)) else str(entry.value))
        data("unit", n, entry.unit)
        data("source", n, entry.source)
        link("hasEvidenceStatus", n, "status_" + entry.status.value)
    for category in ontology.categories:
        individual("category_" + category.name, category.name)
    for artefact in ontology.artefacts:
        n = individual("artefact_" + artefact.name, artefact.kind.value)
        data("annotationClass", n, artefact.annotation_type)
        data("sceneBody", n, artefact.body)
        data("combustible", n, artefact.combustible)
        if artefact.part_of is not None:
            link("partOf", n, "artefact_" + artefact.part_of.name)
        for key in artefact.register_keys:
            link("describedBy", n, "register_" + key)
    for material in ontology.materials:
        n = individual("material_" + material.name, material.kind.value)
        if material.e_number:
            data("eNumber", n, material.e_number)
        data("requiresWarning", n, material.requires_warning)
        if material.allergen:
            data("allergen", n, material.allergen)
        for key in material.register_keys:
            link("describedBy", n, "register_" + key)
    for step in ontology.steps:
        n = individual("step_" + step.name, "ProductionStep")
        data("order", n, step.order)
        data("designator", n, step.designator_name)
        data("taskFamily", n, step.task_family)
        data("precondition", n, step.precondition)
        data("effect", n, step.effect)
        data("manualReference", n, step.manual_reference)
        data("performedBy", n, step.performed_by)
        for category in step.categories:
            link("hasCategory", n, "category_" + category.name)
        for artefact in step.acts_on:
            link("actsOn", n, "artefact_" + artefact.name)
    for regulation in ontology.regulations:
        n = individual("regulation_" + regulation.name, "Regulation")
        data("reference", n, regulation.reference)
        data("requirement", n, regulation.requirement)
        for artefact in regulation.satisfied_by:
            link("satisfiedBy", n, "artefact_" + artefact.name)
        link("describedBy", n, "register_" + regulation.register_key)
    for measure in ontology.measures:
        n = individual("measure_" + measure.name, "SafetyMeasure")
        for artefact in measure.implemented_by:
            link("implementedBy", n, "artefact_" + artefact.name)
        for step in measure.enforced_in:
            link("enforcedIn", n, "step_" + step.name)
        if measure.regulation is not None:
            link("requiredBy", n, "regulation_" + measure.regulation.name)
    for hazard in ontology.hazards:
        n = individual("hazard_" + hazard.name, "Hazard")
        link("causedBy", n, "artefact_" + hazard.caused_by.name)
        for measure in hazard.mitigated_by:
            link("mitigatedBy", n, "measure_" + measure.name)
        for key in hazard.register_keys:
            link("describedBy", n, "register_" + key)
    for quality in ontology.qualities:
        n = individual("quality_" + quality.name, "ProductQuality")
        link("describedBy", n, "register_" + quality.entry.key)
    return axioms


def functional_syntax(ontology: CottonCandyProductionOntology) -> str:
    """
    :return: The whole ontology as an OWL 2 functional-style document.
    """
    head = [
        f"Prefix(:=<{PREFIX}>)",
        "Prefix(owl:=<http://www.w3.org/2002/07/owl#>)",
        "Prefix(rdfs:=<http://www.w3.org/2000/01/rdf-schema#>)",
        "Prefix(xsd:=<http://www.w3.org/2001/XMLSchema#>)",
        "",
        f"Ontology(<{PREFIX.rstrip('#')}>",
    ]
    body = list(dict.fromkeys(tbox(ontology) + abox(ontology)))
    return "\n".join(head + ["    " + axiom for axiom in body] + [")", ""])


def write(ontology: CottonCandyProductionOntology, path: str) -> str:
    """
    Write the ontology to ``path`` and return the path.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(functional_syntax(ontology))
    return path


def main() -> None:
    from coraplex.datastructures.dataclasses import Context
    from semantic_digital_twin.robots.pr2 import PR2

    from cotton_candy.booth_world import BoothWorldBuilder, TwinModule, twin_root
    from cotton_candy.ontology.production import OntologyBuilder
    from cotton_candy.process import FlossMachineProcess, FlossMachineTimings
    from cotton_candy.semantic_annotations import CottonCandyMachine

    world = BoothWorldBuilder().build()
    robot = world.get_semantic_annotations_by_type(PR2)[0]
    machine = world.get_semantic_annotations_by_type(CottonCandyMachine)[0]
    process = FlossMachineProcess(machine, FlossMachineTimings.from_twin_register(TwinModule.PARAMS.load()))
    ontology = OntologyBuilder(world, Context(world, robot, sampling_seed=0), process).build()
    out = write(ontology, os.path.join(twin_root(), "ontology", "build", "cotton_candy_production.ofn"))
    counts = {k: len(v) for k, v in vars(ontology).items()}
    print("wrote", out, counts)


if __name__ == "__main__":
    main()
