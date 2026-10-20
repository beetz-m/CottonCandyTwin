"""
The cotton candy production ontology: its classes (TBox, as dataclasses EQL can query) and the generation of its
individuals (ABox) from the booth's scene graph, the twin's parameter register and the action designators.

Every individual that stands for something in the booth links to the semantic annotation (and body) of the
CRAM world it represents; every production step links to the top-level designator that performs it and to the
manipulation action categories that designator is composed of; every number links to its register entry and
evidence status. The ontology is not a copy of the world: live properties (distances, the machine's phase) are read
from the world and the process model when a question is asked.

Class names follow the action-category framework (ResearchSpace ``foundation/kb/dl-axioms/cram/ontology/
action-category-dl.md``) and AICOR/SOMA usage where a counterpart exists; the OWL export is in :mod:`.owl`.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np
from typing_extensions import Any, Dict, List, Optional, Type

from coraplex.plans.factories import sequential
from semantic_digital_twin.semantic_annotations.mixins import HasRootBody
from semantic_digital_twin.semantic_annotations.semantic_annotations import Human

from cotton_candy import actions as A
from cotton_candy.booth_world import RobotStation, TwinModule
from cotton_candy.manipulation_categories import ManipulationActionCategory, category_profile
from cotton_candy.process import FlossMachineProcess
from cotton_candy.semantic_annotations import (
    CandyStick,
    ControlKnob,
    CottonCandyBooth,
    CottonCandyMachine,
    FireExtinguisher,
    FlossPan,
    HandoverZone,
    HandwashStation,
    InformationBoard,
    LockHandle,
    RockerSwitch,
    SalesFlap,
    SpinnerHead,
    Sponge,
    StickQuiver,
    SugarCarton,
)


# %% vocabulary


class EvidenceStatus(StrEnum):
    """
    How a number of the twin is known (the twin register's status labels).
    """

    SOURCED = "SOURCED"
    SOURCED_VERIFY = "SOURCED-VERIFY"
    STANDARD = "STANDARD"
    DERIVED = "DERIVED"
    PROXY = "PROXY"
    ANALOGUE = "ANALOGUE"
    MEASURED = "MEASURED"
    CALIBRATED = "CALIBRATED"
    ILLUSTRATIVE = "ILLUSTRATIVE"
    GAP = "GAP"


class ArtefactKind(StrEnum):
    """
    The kinds of things in the booth.
    """

    MACHINE = "Machine"
    MACHINE_PART = "MachinePart"
    OPERATING_ELEMENT = "OperatingElement"
    TOOL = "Tool"
    CONSUMABLE = "Consumable"
    BOOTH_ELEMENT = "BoothElement"
    SAFETY_EQUIPMENT = "SafetyEquipment"
    AGENT = "Agent"
    REGION = "Region"


class MaterialKind(StrEnum):
    """
    The kinds of materials of the product and its packaging.
    """

    INGREDIENT = "Ingredient"
    COLOUR = "FoodColour"
    ADDITIVE = "FoodAdditive"
    PACKAGING = "Packaging"


# %% classes (TBox)


@dataclass(eq=False)
class RegisterEntry:
    """
    One number (or fact) of the twin's parameter register.
    """

    key: str
    """
    The register key.
    """

    value: Any
    """
    The value.
    """

    unit: str
    """
    The unit.
    """

    status: EvidenceStatus
    """
    How the value is known.
    """

    source: str
    """
    The source key and what was read there.
    """

    note: str
    """
    The register's note.
    """


@dataclass(eq=False)
class ManipulationCategoryNode:
    """
    A manipulation action category (an action-category-dl.md class, or a proposed extension).
    """

    name: str
    """
    The OWL class name.
    """

    parent: str
    """
    The class it specialises.
    """

    effect: str
    """
    Its effect class.
    """

    primitives: List[str]
    """
    The primitive categories it is composed of (hasSubaction).
    """

    telos_state: str
    """
    The state its telos is defined over.
    """

    roles: List[str]
    """
    The participant roles of its intentional structure.
    """

    defined_in: str
    """
    ``action-category-dl.md`` or ``proposed``.
    """


@dataclass(eq=False)
class Artefact:
    """
    A thing in the booth, linked to the semantic annotation that represents it in the CRAM world.
    """

    name: str
    """
    The name of the individual (the annotation's root body name).
    """

    kind: ArtefactKind
    """
    What kind of thing it is.
    """

    annotation: Any
    """
    The semantic annotation of the CRAM world that represents it.
    """

    annotation_type: str
    """
    The class name of that annotation.
    """

    body: str
    """
    The name of the annotation's root body (the prim name in the Isaac Sim stage as well).
    """

    part_of: Optional[Artefact] = None
    """
    The artefact it is a part of.
    """

    combustible: bool = False
    """
    Whether it counts as a fire load (twin layout).
    """

    material: str = ""
    """
    What it is made of (twin layout).
    """

    register_keys: List[str] = field(default_factory=list)
    """
    The register entries that describe it.
    """

    heating_band: Any = None
    """
    The spinner head's root body, for the live distance (set on every artefact).
    """

    @property
    def distance_to_heating_band(self) -> float:
        """
        :return: Live distance in metres from this artefact's body (axis-aligned box) to the axis of the spinner
            head's heating band, minus the band radius.
        """
        if self.heating_band is None or self.annotation is None:
            return float("inf")
        band = self.heating_band.global_pose.to_np()[:3, 3]
        box = self.annotation.root.collision.as_bounding_box_collection_in_frame(
            self.annotation.root._world.root
        )
        if not box.bounding_boxes:
            return float("inf")
        bb = box.bounding_box()
        nearest = np.clip(band, [bb.min_x, bb.min_y, bb.min_z], [bb.max_x, bb.max_y, bb.max_z])
        return float(np.linalg.norm(band - nearest)) - 0.0698

    @property
    def part_of_name(self) -> str:
        """
        :return: The name of the artefact it is part of, or an empty string.
        """
        return self.part_of.name if self.part_of is not None else ""


@dataclass(eq=False)
class Material:
    """
    A material of the product or its packaging.
    """

    name: str
    """
    The material's name.
    """

    kind: MaterialKind
    """
    Ingredient, colour, additive or packaging.
    """

    e_number: str = ""
    """
    Its E number, if it is a food additive.
    """

    requires_warning: bool = False
    """
    Whether Reg. (EC) 1333/2008 Annex V requires the azo-dye warning.
    """

    allergen: str = ""
    """
    The allergen it carries (LMIV Annex II), if any.
    """

    register_keys: List[str] = field(default_factory=list)
    """
    The register entries that describe it.
    """


@dataclass(eq=False)
class ProductionStep:
    """
    A step of cotton candy production, performed by a top-level action designator.
    """

    order: int
    """
    Its position in the booth's shift.
    """

    name: str
    """
    The step's name.
    """

    designator: Type
    """
    The top-level designator class that performs it.
    """

    categories: List[ManipulationCategoryNode]
    """
    The manipulation action categories it is composed of, in plan order.
    """

    task_family: str
    """
    The task family of the CRAM task taxonomy (TASK-TAXONOMY.md).
    """

    acts_on: List[Artefact]
    """
    The artefacts the step acts on.
    """

    precondition: str
    """
    What must hold before it (the designator's pre-condition).
    """

    effect: str
    """
    What holds after it (the designator's post-condition).
    """

    manual_reference: str
    """
    Where the reference machine's manual describes it.
    """

    performed_by: str = "robot"
    """
    Who performs it: the robot, or the staff (set-up tasks the robot cannot reach).
    """

    @property
    def designator_name(self) -> str:
        """
        :return: The designator's class name.
        """
        return self.designator.__name__

    @property
    def category_names(self) -> List[str]:
        """
        :return: The names of its categories, in plan order.
        """
        return [category.name for category in self.categories]

    @property
    def acts_on_names(self) -> List[str]:
        """
        :return: The names of the artefacts it acts on.
        """
        return [artefact.name for artefact in self.acts_on]


@dataclass(eq=False)
class Regulation:
    """
    A rule that applies to the booth, and what in the booth satisfies it.
    """

    name: str
    """
    The rule's short name.
    """

    reference: str
    """
    The legal or normative reference.
    """

    requirement: str
    """
    What it requires.
    """

    satisfied_by: List[Artefact]
    """
    The artefacts that satisfy it.
    """

    register_key: str
    """
    The register entry recording it.
    """

    @property
    def satisfied_by_names(self) -> List[str]:
        """
        :return: The names of the artefacts that satisfy it.
        """
        return [artefact.name for artefact in self.satisfied_by]


@dataclass(eq=False)
class SafetyMeasure:
    """
    What mitigates a hazard: equipment in the booth, a rule of the procedure, or both.
    """

    name: str
    """
    The measure's name.
    """

    implemented_by: List[Artefact] = field(default_factory=list)
    """
    The artefacts that implement it.
    """

    enforced_in: List[ProductionStep] = field(default_factory=list)
    """
    The steps whose pre-conditions enforce it.
    """

    regulation: Optional[Regulation] = None
    """
    The rule that requires it, if any.
    """


@dataclass(eq=False)
class Hazard:
    """
    A hazard of cotton candy production.
    """

    name: str
    """
    The hazard's name.
    """

    caused_by: Artefact
    """
    The artefact it comes from.
    """

    mitigated_by: List[SafetyMeasure]
    """
    The measures that mitigate it.
    """

    register_keys: List[str] = field(default_factory=list)
    """
    The register entries that quantify it.
    """

    @property
    def caused_by_name(self) -> str:
        """
        :return: The name of the artefact it comes from.
        """
        return self.caused_by.name

    @property
    def mitigation_names(self) -> List[str]:
        """
        :return: The names of the measures that mitigate it.
        """
        return [measure.name for measure in self.mitigated_by]


@dataclass(eq=False)
class ProductQuality:
    """
    A quality of the product or its process, with its value from the register.
    """

    name: str
    """
    The quality's name.
    """

    entry: RegisterEntry
    """
    The register entry that gives its value.
    """

    @property
    def value(self) -> Any:
        """
        :return: The value.
        """
        return self.entry.value

    @property
    def unit(self) -> str:
        """
        :return: The unit.
        """
        return self.entry.unit

    @property
    def status(self) -> EvidenceStatus:
        """
        :return: How the value is known.
        """
        return self.entry.status


@dataclass
class CottonCandyProductionOntology:
    """
    The individuals of the cotton candy production ontology, by class.
    """

    register: List[RegisterEntry] = field(default_factory=list)
    categories: List[ManipulationCategoryNode] = field(default_factory=list)
    artefacts: List[Artefact] = field(default_factory=list)
    materials: List[Material] = field(default_factory=list)
    steps: List[ProductionStep] = field(default_factory=list)
    regulations: List[Regulation] = field(default_factory=list)
    measures: List[SafetyMeasure] = field(default_factory=list)
    hazards: List[Hazard] = field(default_factory=list)
    qualities: List[ProductQuality] = field(default_factory=list)

    def artefact(self, name: str) -> Artefact:
        """
        :return: The artefact with that name.
        """
        return next(artefact for artefact in self.artefacts if artefact.name == name)

    def entry(self, key: str) -> RegisterEntry:
        """
        :return: The register entry with that key.
        """
        return next(entry for entry in self.register if entry.key == key)


# %% generation (ABox)


@dataclass
class OntologyBuilder:
    """
    Generates the ontology's individuals from the booth world, the twin register and the designators.
    """

    world: Any
    """
    The CRAM world of the booth (built by :class:`~cotton_candy.booth_world.BoothWorldBuilder`).
    """

    context: Any
    """
    A plan context in that world (to read the designators' category profiles from their plans).
    """

    process: FlossMachineProcess
    """
    The machine's process model.
    """

    ontology: CottonCandyProductionOntology = field(default_factory=CottonCandyProductionOntology)
    """
    The ontology being built.
    """

    def build(self) -> CottonCandyProductionOntology:
        params, layout = TwinModule.PARAMS.load(), TwinModule.LAYOUT.load()
        self._register(params)
        self._categories()
        self._artefacts(layout)
        self._materials()
        self._steps()
        self._regulations()
        self._hazards()
        self._qualities()
        return self.ontology

    # %% register and categories

    def _register(self, params) -> None:
        for key, (value, unit, status, source, note) in params.P.items():
            sources = "; ".join(f"{s.strip()}: {params.SOURCES.get(s.strip(), '')[:160]}" for s in source.split(";"))
            self.ontology.register.append(
                RegisterEntry(key, value, unit, EvidenceStatus(status), sources, note)
            )

    def _categories(self) -> None:
        for category in ManipulationActionCategory:
            spec = category.specification
            self.ontology.categories.append(
                ManipulationCategoryNode(
                    spec.name, spec.parent, spec.effect.value if spec.effect else "none", list(spec.subactions),
                    spec.telos_state, list(spec.roles), spec.defined_in,
                )
            )

    def _category(self, category: ManipulationActionCategory) -> ManipulationCategoryNode:
        return next(node for node in self.ontology.categories if node.name == category.specification.name)

    # %% artefacts, linked to the semantic annotations

    def _artefacts(self, layout) -> None:
        kinds: Dict[type, ArtefactKind] = {
            CottonCandyMachine: ArtefactKind.MACHINE,
            SpinnerHead: ArtefactKind.MACHINE_PART,
            FlossPan: ArtefactKind.MACHINE_PART,
            RockerSwitch: ArtefactKind.OPERATING_ELEMENT,
            ControlKnob: ArtefactKind.OPERATING_ELEMENT,
            LockHandle: ArtefactKind.OPERATING_ELEMENT,
            SugarCarton: ArtefactKind.CONSUMABLE,
            CandyStick: ArtefactKind.CONSUMABLE,
            StickQuiver: ArtefactKind.BOOTH_ELEMENT,
            Sponge: ArtefactKind.TOOL,
            CottonCandyBooth: ArtefactKind.BOOTH_ELEMENT,
            SalesFlap: ArtefactKind.BOOTH_ELEMENT,
            HandoverZone: ArtefactKind.REGION,
            HandwashStation: ArtefactKind.SAFETY_EQUIPMENT,
            FireExtinguisher: ArtefactKind.SAFETY_EQUIPMENT,
            InformationBoard: ArtefactKind.SAFETY_EQUIPMENT,
            Human: ArtefactKind.AGENT,
        }
        items = {item["name"]: item for item in layout.items()}
        machine = self.world.get_semantic_annotations_by_type(CottonCandyMachine)[0]
        head_body = machine.spinner_head.root
        by_annotation: Dict[int, Artefact] = {}
        for annotation in self.world.semantic_annotations:
            kind = kinds.get(type(annotation))
            if kind is None or not isinstance(annotation, HasRootBody):
                continue
            body = annotation.root.name.name
            item = items.get(body, {})
            artefact = Artefact(
                name=body, kind=kind, annotation=annotation, annotation_type=type(annotation).__name__, body=body,
                combustible=bool(item.get("combustible", False)), material=str(item.get("sdt", {}).get("material", "")),
                heating_band=head_body,
            )
            by_annotation[id(annotation)] = artefact
            self.ontology.artefacts.append(artefact)
        for part in (machine.motor_switch, machine.heat_switch, machine.heat_control, machine.spinner_head,
                     machine.floss_pan, *machine.lock_handles):
            by_annotation[id(part)].part_of = by_annotation[id(machine)]
        register = {
            "CottonCandyMachine": ["m_power_230", "m_mass", "m_overall_height", "m_cabinet_material"],
            "SpinnerHead": ["head_rpm", "head_band_diameter", "head_sugar_capacity", "head_fill_fraction"],
            "FlossPan": ["pan_inner_diameter", "pan_height", "pan_material"],
            "SugarCarton": ["sugar_carton", "sugar_carton_size"],
            "CandyStick": ["stick_length", "stick_section"],
            "HandwashStation": ["reg_handwash_required", "handwash_unit"],
            "FireExtinguisher": ["reg_fire_extinguisher_kg"],
            "InformationBoard": ["reg_colour_label", "reg_azo_warning", "reg_allergen_lactose", "price_portion"],
        }
        for artefact in self.ontology.artefacts:
            artefact.register_keys = register.get(artefact.annotation_type, [])

    # %% materials

    def _materials(self) -> None:
        self.ontology.materials += [
            Material("sucrose (floss sugar)", MaterialKind.INGREDIENT,
                     register_keys=["sucrose_density", "sucrose_melt", "portion_sugar"]),
            Material("Allura Red (pink colour)", MaterialKind.COLOUR, e_number="E129", requires_warning=True,
                     register_keys=["colour_sugar_pink", "reg_azo_warning"]),
            Material("Brilliant Blue (blue colour)", MaterialKind.COLOUR, e_number="E133",
                     register_keys=["colour_sugar_pink"]),
            Material("silica (anti-caking agent)", MaterialKind.ADDITIVE, e_number="E551",
                     register_keys=["colour_sugar_pink"]),
            Material("lactose (carrier of the colour sugar)", MaterialKind.INGREDIENT, allergen="milk",
                     register_keys=["colour_sugar_pink", "reg_allergen_lactose"]),
            Material("flavouring", MaterialKind.INGREDIENT, register_keys=["colour_sugar_pink"]),
            Material("pine wood (stick)", MaterialKind.PACKAGING, register_keys=["stick_length", "stick_section"]),
            Material("cardboard (sugar carton)", MaterialKind.PACKAGING, register_keys=["sugar_carton"]),
        ]

    # %% steps, linked to the designators and their categories

    def _artefacts_in(self, action) -> List[Artefact]:
        annotations = []
        for value in vars(action).values():
            values = value if isinstance(value, list) else [value]
            annotations += [v for v in values if isinstance(v, HasRootBody)]
            if isinstance(value, CottonCandyMachine):
                annotations += [value.motor_switch, value.heat_switch, value.heat_control, value.spinner_head,
                                value.floss_pan]
        by_id = {id(a.annotation): a for a in self.ontology.artefacts}
        return [by_id[id(a)] for a in annotations if id(a) in by_id]

    def _steps(self) -> None:
        w, process = self.world, self.process
        machine = w.get_semantic_annotations_by_type(CottonCandyMachine)[0]
        arm = self.context.robot.right_arm
        one = lambda t: w.get_semantic_annotations_by_type(t)[0]
        station = lambda s: s.pose(w.root)
        shift = [
            ("Prepare the machine (unlock the transport handles)", A.PrepareFlossMachineAction(machine, arm),
             "B machine tending: access", "GM_MAN_EXP p. 5 'Setup for Use', step 2", "staff"),
            ("Fill the spinner head", A.FillSpinnerHeadAction(machine, process, one(SugarCarton), arm,
                                                             station(RobotStation.MACHINE),
                                                             station(RobotStation.MACHINE_CLOSE)),
             "B machine tending: load", "GM_MAN_EXP p. 9-10 (step 3), carton p. 9", "robot"),
            ("Start the machine", A.StartFlossMachineAction(machine, process, arm), "B machine tending: operate",
             "GM_MAN_EXP p. 10, steps 4-6", "robot"),
            ("Make a portion", A.MakeCottonCandyAction(machine, process, one(CandyStick), arm), "D portion",
             "GM_MAN_EXP p. 11 'Making Floss'", "robot"),
            ("Serve the portion", A.ServeCottonCandyAction(one(CandyStick), one(HandoverZone), arm,
                                                           station(RobotStation.SERVING),
                                                           station(RobotStation.MACHINE)),
             "J handover / F serve", "-", "robot"),
            ("Stop the machine", A.StopFlossMachineAction(machine, process, arm), "B machine tending: operate",
             "GM_MAN_EXP p. 10, step 8", "robot"),
            ("Shut the machine down", A.ShutDownFlossMachineAction(machine, process, arm),
             "B machine tending / maintenance", "GM_MAN_EXP p. 13 'Shut Down Procedure'", "robot"),
            ("Clean the machine", A.CleanFlossMachineAction(machine, process, one(Sponge), arm), "G wipe",
             "GM_MAN_EXP p. 13 'Care and Cleaning'", "robot"),
        ]
        for order, (name, action, family, manual, by) in enumerate(shift, start=1):
            sequential([action], self.context)
            categories = [self._category(c) for c in category_profile(action)]
            self.ontology.steps.append(
                ProductionStep(
                    order=order, name=name, designator=type(action), categories=categories, task_family=family,
                    acts_on=self._artefacts_in(action),
                    precondition=_doc(type(action).pre_condition), effect=_doc(type(action).post_condition),
                    manual_reference=manual, performed_by=by,
                )
            )

    # %% regulation, hazards, qualities

    def _regulations(self) -> None:
        o = self.ontology
        a = lambda t: [x for x in o.artefacts if x.annotation_type == t]
        o.regulations += [
            Regulation("hand washing facility", "Reg. (EC) 852/2004 Annex II Ch. III 2(a); Muenster MB 25",
                       "running water, soap and towels at stands selling unpackaged food", a("HandwashStation"),
                       "reg_handwash_required"),
            Regulation("colour declaration", "LMZDV par. 5(1) Nr. 1", "loose food with colours: 'mit Farbstoff'",
                       a("InformationBoard"), "reg_colour_label"),
            Regulation("azo-dye warning", "Reg. (EC) 1333/2008 Annex V",
                       "E129: 'Kann Aktivitaet und Aufmerksamkeit bei Kindern beeintraechtigen.'",
                       a("InformationBoard"), "reg_azo_warning"),
            Regulation("allergen information", "Reg. (EU) 1169/2011 Art. 9(1)c / 44", "milk (lactose) declared",
                       a("InformationBoard"), "reg_allergen_lactose"),
            Regulation("fire extinguisher per stand", "market regulations (GEJA 2026, Heilbronn 2022)",
                       "6 kg ABC powder extinguisher", a("FireExtinguisher"), "reg_fire_extinguisher_kg"),
            Regulation("clearance of heating devices", "fire service leaflet Heilbronn 2022",
                       "0.50 m from combustibles or surfaces <= 85 C", a("CottonCandyMachine"), "reg_heat_clearance"),
            Regulation("no remote operation", "EN 60335 / GM_MAN_EXP",
                       "the machine is not operated by an external timer or remote control - the robot presses its "
                       "own switches", a("RockerSwitch"), "m_switch_motor"),
        ]

    def _hazards(self) -> None:
        o = self.ontology
        step = lambda n: next(s for s in o.steps if s.name.startswith(n))
        art = lambda t: next(x for x in o.artefacts if x.annotation_type == t)
        reg = lambda n: next(r for r in o.regulations if r.name == n)
        bubble = SafetyMeasure("floss bubble (spectator protection)", [art("FlossPan")])
        stopped_head = SafetyMeasure("sugar only into a stopped head", enforced_in=[step("Fill")])
        clearance = SafetyMeasure("0.5 m clearance of the heating band", [art("CottonCandyMachine")],
                                  regulation=reg("clearance of heating devices"))
        cool = SafetyMeasure("clean only after cool-down", enforced_in=[step("Clean")])
        extinguisher = SafetyMeasure("fire extinguisher", [art("FireExtinguisher")],
                                     regulation=reg("fire extinguisher per stand"))
        handwash = SafetyMeasure("hand washing", [art("HandwashStation")], regulation=reg("hand washing facility"))
        labels = SafetyMeasure("colour, azo and allergen labelling", [art("InformationBoard")],
                               regulation=reg("azo-dye warning"))
        o.measures += [bubble, stopped_head, clearance, cool, extinguisher, handwash, labels]
        o.hazards += [
            Hazard("rotating spinner head (3450 rpm)", art("SpinnerHead"), [bubble, stopped_head], ["head_rpm"]),
            Hazard("hot heating band (molten sugar ~170 C)", art("SpinnerHead"), [clearance, cool, extinguisher],
                   ["head_melt_temp", "sucrose_burn"]),
            Hazard("food hygiene (unpackaged food)", art("CottonCandyMachine"), [handwash],
                   ["reg_handwash_required"]),
            Hazard("azo colour and milk allergen for customers", art("InformationBoard"), [labels],
                   ["reg_azo_warning", "reg_allergen_lactose"]),
        ]

    def _qualities(self) -> None:
        o = self.ontology
        for name, key in (
            ("sucrose melting point", "sucrose_melt"),
            ("glass transition of amorphous sucrose", "sucrose_tg_dry"),
            ("relative humidity at which floss collapses (3 days)", "floss_collapse_rh"),
            ("relative humidity at which floss stays stable", "floss_stable_rh"),
            ("fibre diameter", "fibre_diameter"),
            ("spinner head speed", "head_rpm"),
            ("warm-up time to first floss", "op_warmup"),
            ("rated output", "op_output_rate"),
            ("sugar per portion", "portion_sugar"),
            ("price of a small portion (Oktoberfest 2025)", "price_portion"),
        ):
            o.qualities.append(ProductQuality(name, o.entry(key)))


def _doc(function) -> str:
    """
    :return: The first paragraph of a function's docstring, or "-".
    """
    doc = inspect.getdoc(function) or ""
    return doc.split("\n\n")[0].replace("\n", " ") if doc else "-"
