"""The language derived from the ontology catches what it should (run: ~/Documents/ConceptualCRAM/.venv/bin/python -m pytest tests -q --ignore=tests/test_kernel_runs.py)."""
import os
import sys

sys.path.insert(0, os.path.expanduser("~/Documents/ConceptualCRAM"))
from ccram.activity import load  # noqa: E402

load(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).configure()        # ccram core + booth.ttl
from ccram import lang as CL  # noqa: E402

ONTO = CL.Ontology()
LEX = CL.Lexicon(ONTO)


def lint(text):
    return [(lvl, msg) for lvl, _, msg in CL.Linter(ONTO, LEX).lint_text(text, "t").items]


def plan(body):
    return f"(def-plan-schema p ((m cotton-candy-machine)) (:body {body}))"


def test_keywords_resolve_by_position():
    assert CL.short(LEX.resolve("type", "turning")[0]) == "ccram:TurningControl"       # alias wins over soma:Turning
    assert CL.short(LEX.resolve("type", "turning-motion")[0]) == "soma:Turning"
    assert CL.short(LEX.resolve("type", "container")[0]) == "ccram:ContainerObject"    # type reading
    assert CL.short(LEX.resolve("role", "container")[0]) == "soma:Container"           # role reading
    assert CL.short(LEX.resolve("role", "object")[0]) == "soma:Patient"
    assert CL.short(LEX.resolve("type", "cup")[0]) == "soma:Cup"                       # derived: any SOMA class


def test_well_formed_designator_passes():
    assert lint(plan("(perform (an action (type wiping) (tool (the sponge)) (surface (tagged floss-pan ?m))))")) == []


def test_role_not_admissible():
    r = lint(plan("(perform (an action (type pouring-into) (destination (a container)) (recipient (the customer))))"))
    assert any(lvl == "ERROR" and "recipient" in m and "not admissible" in m for lvl, m in r)


def test_action_type_must_be_a_task():
    r = lint(plan("(perform (an action (type turning-motion) (object (a control-knob))))"))
    assert any(lvl == "ERROR" and "not a task" in m for lvl, m in r)


def test_unknown_keyword_gets_a_suggestion():
    r = lint(plan("(perform (an action (type pooring-into) (destination (a container))))"))
    assert any(lvl == "ERROR" and "pouring-into" in m for lvl, m in r)


def test_missing_required_role_is_left_to_the_climb():
    r = lint(plan("(perform (an action (type wiping) (tool (the sponge))))"))
    assert any(lvl == "INFO" and "surface" in m for lvl, m in r)


def test_library_claim_that_contradicts_the_ontology_is_a_meta_finding():
    r = lint("(def-action-schema wiping (:specializes configuration-change) (:roles (tool (a sponge)) (surface (a surface))))")
    assert any(lvl == "META" and "configuration-change" in m for lvl, m in r)


def test_schema_without_slot_for_a_required_role():
    r = lint("(def-action-schema pressing-button (:roles (object (a rocker-switch))))")
    assert any(lvl == "META" and "'state'" in m for lvl, m in r)


def test_dl_reading_attributive_vs_referential():
    d = CL.parse("(an action (type pouring-into) (destination (tagged spinner-head machine)))")[0]
    e = CL.to_dl(d, LEX)
    assert "dul:executesTask some soma:PouringInto" in e and "{machine/spinner-head}" in e
    assert CL.to_dl(CL.parse("(the sponge)")[0], LEX).startswith("the-one(")


# ---- failures (Q2): typed failure descriptions, caught by the enclosing plan; checked statically
MT = """(def-microtheory floss-machine (:modes (running-empty :when x :class recoverable :signals head-running-empty)))
(def-failure head-running-empty (:specializes process-failure) (:signalled-by (microtheory floss-machine)))
(def-action-schema monitoring-process (:roles (process (a process)) (until (a condition)))
  (:causal (:microtheory floss-machine)))
"""


def test_unhandled_failure_is_a_has_fallback_finding():
    r = lint(MT + "(def-plan-schema p ((m cotton-candy-machine)) (:body (perform (an action (type monitoring-process) (process x) (until y)))))")
    assert any(lvl == "META" and "head-running-empty" in m and "has-fallback" in m for lvl, m in r)


def test_handler_matches_by_ontology_subsumption():
    r = lint(MT + "(def-plan-schema p ((m cotton-candy-machine)) (:body (with-failure-handling ((process-failure (f) (retry))) "
                  "(perform (an action (type monitoring-process) (process x) (until y))))))")
    assert any(lvl == "INFO" and "head-running-empty" in m and "handled" in m for lvl, m in r)
    assert not any(lvl == "META" for lvl, m in r)


def test_declared_escape_is_accepted():
    r = lint(MT + "(def-plan-schema p ((m cotton-candy-machine)) (:escapes process-failure) "
                  "(:body (perform (an action (type monitoring-process) (process x) (until y)))))")
    assert any(lvl == "INFO" and "escapes" in m for lvl, m in r) and not any(lvl == "META" for lvl, m in r)


def test_handling_a_closing_event_is_an_error():
    r = lint(MT + "(def-plan-schema p ((m cotton-candy-machine)) (:body (with-failure-handling "
                  "((sugar-poured-into-spinning-head (f) (continue))) (seq))))")
    assert any(lvl == "ERROR" and "prevented by the gate" in m for lvl, m in r)


def test_positional_plan_argument_mismatch_is_an_error():
    lib = ("(def-plan-schema fill ((machine cotton-candy-machine) (sugar sugar-carton) (arm arm)) (:body (seq)))"
           "(def-plan-schema make ((machine cotton-candy-machine) (arm arm)) (:body (perform-plan fill ?machine ?arm)))")
    r = lint(lib)
    assert any(lvl == "ERROR" and "positional mismatch" in m for lvl, m in r)
    ok = lint(lib.replace("(perform-plan fill ?machine ?arm)", "(perform-plan fill ?machine (a sugar-carton) ?arm)"))
    assert not any(lvl == "ERROR" for lvl, m in ok)
