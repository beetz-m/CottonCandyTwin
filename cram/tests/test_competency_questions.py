"""
The competency questions answered by cramera's EQL runner, against hand-curated gold answers (not round trips of the
ontology generator: the expectations below are written from the manual, the regulations and the twin's layout).
"""

from __future__ import annotations

import pytest

from coraplex.datastructures.dataclasses import Context
from cramera.knowledge.query_runner import EqlQueryRunner
from semantic_digital_twin.robots.pr2 import PR2

from cotton_candy.booth_world import BoothWorldBuilder, TwinModule
from cotton_candy.competency_questions import QUESTIONS, CottonCandyKnowledgeSource
from cotton_candy.ontology.production import OntologyBuilder
from cotton_candy.process import FlossMachineProcess, FlossMachineTimings
from cotton_candy.semantic_annotations import CottonCandyMachine


@pytest.fixture(scope="module")
def source():
    world = BoothWorldBuilder().build()
    robot = world.get_semantic_annotations_by_type(PR2)[0]
    machine = world.get_semantic_annotations_by_type(CottonCandyMachine)[0]
    process = FlossMachineProcess(machine, FlossMachineTimings.from_twin_register(TwinModule.PARAMS.load()))
    ontology = OntologyBuilder(world, Context(world, robot, sampling_seed=0), process).build()
    return CottonCandyKnowledgeSource(ontology, process, world)


@pytest.fixture(scope="module")
def runner(source):
    knowledge = source.knowledge()[0]
    return EqlQueryRunner(domains=knowledge.domains, extra_names=knowledge.extra_names)


def answer(runner, competence: str, text_start: str) -> list:
    question = next(q for q in QUESTIONS if q.competence == competence and q.text.startswith(text_start))
    return [tuple(_plain(v) for v in row) if isinstance(row, tuple) else _plain(row)
            for row in _rows(runner.build(question.code).evaluate())]


def _rows(result) -> list:
    rows = []
    for item in result:
        if hasattr(item, "values") and callable(item.values):
            rows.append(tuple(item.values()))
        elif isinstance(item, dict):
            rows.append(tuple(item.values()))
        else:
            rows.append(item)
    return rows


def _plain(value):
    return getattr(value, "value", value) if not isinstance(value, (list, str, int, float)) else value


def flat(rows) -> list:
    out = []
    for row in rows:
        out += list(row) if isinstance(row, (tuple, list)) else [row]
    return out


# %% every question builds and verbalizes


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda q: q.text[:40])
def test_every_question_builds_and_answers(runner, question):
    result = list(runner.build(question.code).evaluate())
    # belief questions are about orders, which may not exist yet; all others must answer
    assert result or question.competence == "Belief", question.text


# %% gold answers


def test_shift_has_eight_steps_and_unlocking_is_staff_work(runner):
    rows = flat(answer(runner, "Ablauf", "Welche Schritte"))
    assert "FillSpinnerHeadAction" in rows and "CleanFlossMachineAction" in rows
    assert "staff" in rows   # the Lock-N-Go handles are out of the PR2's reach


def test_sugar_only_into_a_stopped_head(runner):
    rows = flat(answer(runner, "Ablauf", "Was muss gelten"))
    assert any("stands still" in str(r) for r in rows)


def test_pressing_buttons_happens_when_starting_stopping_and_shutting_down(runner):
    rows = set(flat(answer(runner, "Kategorien", "Welche Schritte enthalten")))
    # the make-and-serve plan starts a cold machine, so it presses the switches as well
    assert rows == {"Start the machine", "Make cotton candy and hand it to a customer", "Stop the machine",
                    "Shut the machine down"}


def test_start_is_press_watch_press_turn_watch_turn(runner):
    rows = answer(runner, "Kategorien", "Aus welchen")
    profile = rows[0] if isinstance(rows[0], list) else flat(rows)
    assert profile == ["PressingButton", "MonitoringProcess", "PressingButton", "Turning", "MonitoringProcess",
                       "Turning"]


def test_only_transporting_pouring_and_wiping_exist_in_cram_l2(runner):
    rows = answer(runner, "Kategorien", "Welche Kategorien")
    existing = {r[0] for r in rows if r[2] == "action-category-dl.md"}
    assert existing == {"Transporting", "Pouring", "Wiping"}


def test_starting_acts_on_the_switches_knob_head_and_pan(runner):
    rows = answer(runner, "Verankerung", "Auf welche Teile")
    names = set(rows[0] if isinstance(rows[0], list) else flat(rows))
    assert {"MotorMasterSwitch", "HeatSwitch", "HeatControlKnob", "SpinnerHead", "FlossPan"} <= names


def test_machine_parts_are_its_operating_elements_head_and_pan(runner):
    names = set(flat(answer(runner, "Verankerung", "Welche Teile gehoeren")))
    assert names == {"MotorMasterSwitch", "HeatSwitch", "HeatControlKnob", "SpinnerHead", "FlossPan",
                     "LockNGoHandleLeft", "LockNGoHandleRight"}


def test_only_e129_needs_the_azo_warning(runner):
    rows = flat(answer(runner, "Zutaten", "Welche Zutaten"))
    assert "E129" in rows and "E133" not in rows


def test_milk_is_the_allergen(runner):
    rows = flat(answer(runner, "Zutaten", "Welche Allergene"))
    assert "milk" in rows


def test_the_info_board_satisfies_the_labelling_rules(runner):
    rows = answer(runner, "Vorschriften", "Welche Vorschrift")
    by_rule = {r[0]: r[2] for r in rows}
    assert "InfoBoard" in by_rule["azo-dye warning"] and "HandwashStation" in by_rule["hand washing facility"]


def test_humidity_collapse_is_sourced(runner):
    rows = answer(runner, "Prozessphysik", "Bei welcher")
    assert {r[1] for r in rows} == {33.0, 11.0}
    assert {str(r[3]) for r in rows} == {"SOURCED"}


def test_live_no_combustible_is_inside_the_regulated_clearance(runner):
    rows = answer(runner, "Live", "Welche brennbaren")
    assert all(r[1] >= 0.5 - 1e-3 for r in rows)          # agrees with twin check C4


def test_live_machine_starts_off(runner):
    rows = flat(answer(runner, "Live", "In welcher Phase"))
    assert "off" in [str(getattr(r, "value", r)) for r in rows]


def test_belief_question_finds_the_open_order(source, runner):
    source.process.candies.clear()
    source.process.new_order("raspberry (pink)", ordered_by="Customer")
    rows = flat(answer(runner, "Belief", "Wie weit"))
    assert "raspberry (pink)" in rows and "Customer" in rows
