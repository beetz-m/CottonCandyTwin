"""
Export the CRAM layer's results for the report: data/cram_results.json in the twin.

It executes, kinematically, the full shift (step by step, recording the machine's process state after every
top-level designator) and the generalized plan from the scenario states of tests/test_universal_plan.py; it also
records the ontology's production steps and categories and answers every competency question with cramera's EQL
runner.

Run: cram/run.sh python cram/export_results.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tests"))

from coraplex.datastructures.dataclasses import Context
from coraplex.execution_environment import kinematically_simulated_robot
from coraplex.plans.factories import sequential
from cramera.knowledge.query_runner import EqlQueryRunner
from krrood.entity_query_language.exceptions import MultipleSolutionFound
from semantic_digital_twin.robots.pr2 import PR2

from cotton_candy.actions import (
    CleanFlossMachineAction,
    FillSpinnerHeadAction,
    FormPortionAction,
    SellCottonCandyAction,
    ShutDownFlossMachineAction,
    StartFlossMachineAction,
    project_refills,
)
from cotton_candy.booth_world import BoothWorldBuilder, RobotStation, TwinModule
from cotton_candy.competency_questions import QUESTIONS, CottonCandyKnowledgeSource
from cotton_candy.manipulation_categories import ApproachDirection, TransportingAction
from cotton_candy.ontology.production import OntologyBuilder
from cotton_candy.process import CandyStage, FlossMachineProcess, FlossMachineTimings
from cotton_candy.recipes import Flavour
from cotton_candy.semantic_annotations import CandyStick, CottonCandyMachine, HandoverZone, Sponge, SugarCarton
from cotton_candy.universal_plan import GoalUnachievable
from test_competency_questions import _plain, _rows
from test_universal_plan import belief, fresh

TWIN = HERE.parent
OUT = TWIN / "data" / "cram_results.json"


def booth():
    world = BoothWorldBuilder().build()
    robot = world.get_semantic_annotations_by_type(PR2)[0]
    machine = world.get_semantic_annotations_by_type(CottonCandyMachine)[0]
    process = FlossMachineProcess(machine, FlossMachineTimings.from_twin_register(TwinModule.PARAMS.load()))
    context = Context(world, robot, sampling_seed=0)
    return world, robot, machine, process, context


def machine_state(process) -> dict:
    return {"time_s": round(process.time_s, 1), "phase": process.phase.value,
            "sugar_in_head_g": round(1000 * process.sugar_in_head_kg, 1),
            "floss_in_pan_g": round(1000 * max(process.floss_in_pan_kg, 0.0), 1),
            "portions_served": process.portions_served}


def shift() -> list:
    """
    The full shift, one top-level designator at a time.
    """
    world, robot, machine, process, context = booth()
    one = lambda t: world.get_semantic_annotations_by_type(t)[0]
    arm, carton = robot.right_arm, one(SugarCarton)
    sticks = world.get_semantic_annotations_by_type(CandyStick)
    st = {s: s.pose(world.root) for s in RobotStation}
    steps = [("Fill the spinner head", FillSpinnerHeadAction(machine, process, carton, arm, st[RobotStation.MACHINE],
                                                             st[RobotStation.MACHINE_CLOSE])),
             ("Start the machine", StartFlossMachineAction(machine, process, arm))]
    for i, refill in enumerate(project_refills(process, 2)):
        steps.append((f"Sell portion {i + 1}" + (" (refill first)" if refill else ""),
                      SellCottonCandyAction(machine, process, sticks[i], carton, one(HandoverZone), arm,
                                            st[RobotStation.SERVING], st[RobotStation.MACHINE],
                                            st[RobotStation.MACHINE_CLOSE], refill_first=refill)))
    steps += [("Shut down (burn-out)", ShutDownFlossMachineAction(machine, process, arm)),
              ("Clean the machine", CleanFlossMachineAction(machine, process, one(Sponge), arm))]
    rows = []
    for name, designator in steps:
        started = time.time()
        with kinematically_simulated_robot:
            sequential([designator], context).perform()
        rows.append({"step": name, "designator": type(designator).__name__,
                     "wall_s": round(time.time() - started, 1), **machine_state(process)})
    return rows


def scenarios() -> list:
    """
    The generalized plan started from different states (as in tests/test_universal_plan.py).
    """
    def run(name, prepare=None, flavour=Flavour.RASPBERRY, second_order=False, two_open=False):
        world, robot, context, machine, process, plan = fresh(flavour)
        arm = robot.right_arm
        carton = world.get_semantic_annotations_by_type(SugarCarton)[0]
        stick = world.get_semantic_annotations_by_type(CandyStick)[0]
        setup = {
            "taken": [FillSpinnerHeadAction(machine, process, carton, arm, RobotStation.MACHINE.pose(world.root),
                                            RobotStation.MACHINE_CLOSE.pose(world.root)),
                      StartFlossMachineAction(machine, process, arm),
                      TransportingAction(stick, arm, ApproachDirection.TOWARDS_LEFT_WALL)],
        }
        if prepare in ("taken", "wrapped"):
            designators = setup["taken"] + ([FormPortionAction(machine, process, stick, arm)] if prepare == "wrapped" else [])
            with kinematically_simulated_robot:
                sequential(designators, context).perform()
        if second_order:
            with kinematically_simulated_robot:
                plan.perform()
            process.new_order(Flavour.RASPBERRY.value, ordered_by="Customer")
            plan.trace.clear()
        if prepare == "lost":
            process.candy.stage, process.candy.stick = CandyStage.WRAPPED, "CandyStick2"
        if two_open:
            process.new_order(Flavour.RASPBERRY.value)
        row = {"scenario": name}
        started = time.time()
        try:
            b = belief(plan)
            row["projection"] = plan.projection(b)
            with kinematically_simulated_robot:
                final = plan.perform()
            row.update(outcome="delivered" if final.delivered else final.stage.value, trace=list(plan.trace),
                       failures=[f"{f.tag}: {f.description}" for f in plan.failures])
        except (GoalUnachievable, MultipleSolutionFound) as error:
            row.update(outcome=type(error).__name__, trace=list(plan.trace), message=str(error)[:200])
        row["wall_s"] = round(time.time() - started, 1)
        row["process_time_s"] = round(process.time_s, 1)
        return row

    return [run("cold machine, first order"),
            run("stick already taken, machine running", "taken"),
            run("wrapped candy already in hand", "wrapped"),
            run("believed candy whose stick is not in hand", "lost"),
            run("second order, machine still running", second_order=True),
            run("blueberry ordered, only raspberry sugar", flavour=Flavour.BLUEBERRY),
            run("two open orders", two_open=True)]


def ontology_and_questions() -> dict:
    world, robot, context, machine, process, plan = fresh()
    with kinematically_simulated_robot:
        plan.perform()                       # one delivered candy, so the belief questions have answers
    process.new_order(Flavour.RASPBERRY.value, ordered_by="Customer")
    ontology = OntologyBuilder(world, context, process).build()
    source = CottonCandyKnowledgeSource(ontology, process, world)
    knowledge = source.knowledge()[0]
    runner = EqlQueryRunner(domains=knowledge.domains, extra_names=knowledge.extra_names)
    answers = []
    for q in QUESTIONS:
        rows = [tuple(_plain(v) for v in r) if isinstance(r, tuple) else _plain(r)
                for r in _rows(runner.build(q.code).evaluate())]
        answers.append({"competence": q.competence, "question": q.text, "code": q.code, "rows": len(rows),
                        "answer": [list(map(str, r)) if isinstance(r, tuple) else str(r) for r in rows][:12]})
    steps = [{"order": s.order, "name": s.name, "designator": s.designator_name, "performed_by": s.performed_by,
              "categories": s.category_names, "acts_on": s.acts_on_names, "precondition": s.precondition,
              "effect": s.effect, "family": s.task_family} for s in ontology.steps]
    categories = [{"name": c.name, "parent": c.parent, "defined_in": c.defined_in} for c in ontology.categories]
    counts = {k: len(getattr(ontology, k)) for k in ("steps", "artefacts", "materials", "hazards", "measures",
                                                     "regulations", "register", "categories", "qualities")}
    plan_rows = [{"index": s.index, "tag": s.tag, "kernel": s.kernel_text, "protects": s.protects is not None}
                 for s in plan.steps()]
    plain = lambda obj: {k: v for k, v in vars(obj).items() if isinstance(v, (str, int, float, bool)) or v is None}
    materials = [plain(m) for m in ontology.materials]
    flavours = [{"name": f.name, "label": f.value, "ingredients": f.ingredients} for f in Flavour]
    return {"questions": answers, "steps": steps, "categories": categories, "counts": counts, "plan_rows": plan_rows,
            "materials": materials, "flavours": flavours}


def main() -> None:
    sys.path.insert(0, str(TWIN / "site"))
    import provenance

    inputs = sorted(str(p) for p in (HERE / "cotton_candy").rglob("*.py")) + [
        str(TWIN / "site" / "params.py"), str(TWIN / "site" / "layout.py"), str(Path(__file__).resolve())]
    results = {"_provenance": provenance.stamp(inputs), "generated_by": "cram/export_results.py",
               "shift": shift(), "scenarios": scenarios(), **ontology_and_questions()}
    OUT.write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str))
    print(f"wrote {OUT}: {len(results['shift'])} shift steps, {len(results['scenarios'])} scenarios, "
          f"{len(results['questions'])} questions")


if __name__ == "__main__":
    main()
