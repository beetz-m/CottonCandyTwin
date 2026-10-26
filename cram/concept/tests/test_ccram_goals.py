"""D10: goals are templates of state evolutions; perform infers the goal, achieve-family goals are refined."""
import os
import sys

sys.path.insert(0, os.path.expanduser("~/Documents/ConceptualCRAM"))
from ccram.activity import load  # noqa: E402

load(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).configure()        # ccram core + booth.ttl
from ccram import goals as G  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORMS = G.parse(open(os.path.join(HERE, "booth.lisp")).read())
ACTS, PLANS, _ = G.schemas_of(FORMS)
G.use_ontology()
G.PROCESS_PREDS.update(G.process_preds(FORMS))
G.PLANS.update(PLANS)


def P(s):
    return G.parse(s)[0]


def test_perform_infers_the_goal_template():
    iv, parts = G.goal_of(P("(an action (type putting-down) (object (the sponge)) (destination (its destination)))"), ACTS)
    forms = [G.show(p.form()) for p in parts]
    assert "(achieve (on (the sponge) (its destination)) :at (end ?i))" in forms
    assert any(f.startswith("(prevent (dropped (the sponge))") for f in forms)


def test_achieve_refines_by_property_subsumption():
    # on (soma:isOntopOf) SubPropertyOf at (dul:hasLocation): putting-down achieves "at its destination"
    c = G.refine(P("(achieve (at (each tool) (its destination)))"), ACTS)
    assert any(k == "action" and "putting-down" in G.show(f) for k, f in c)
    assert not any("navigating" in G.show(f) for k, f in c if k == "action")      # tools are not the robot


def test_agent_is_not_a_patient():
    c = G.refine(P("(achieve (at (the robot) (the station (tag serving))))"), ACTS)
    kinds = [G.show(f) for k, f in c if k == "action"]
    assert any("navigating" in f for f in kinds) and not any("putting-down" in f for f in kinds)


def test_maintain_refines_to_protection_monitor_repair_and_prevent_to_gate():
    m = [k for k, _ in G.refine(P("(maintain (held-by ?s ?a) :until (delivered ?c))"), ACTS)]
    assert m[:2] == ["protection", "monitor"] and "repair" in m
    p = [k for k, _ in G.refine(P("(prevent (poured-into (some sugar) (tagged spinner-head machine)))"), ACTS)]
    assert p[0] == "gate" and "guarded-by-schema" in p


def test_plan_schemas_refine_their_success_condition():
    c = G.refine(P("(achieve (mode floss-machine off))"), ACTS)
    assert ("plan", ["perform-plan", "stop-machine"]) in c


def test_trajectory_check_achieve_maintain_prevent_while():
    goal = (None, [G.Part("achieve", ["contains", "head", "sugar"], ":at", ["end", "?i"]),
                   G.Part("maintain", ["held-by", "carton", "?arm"], ":during", "?i"),
                   G.Part("prevent", ["poured-into", "sugar", "head"], ":while", ["not", ["mode", "m", "off"]])])
    good = [(0.0, [["mode", "m", "off"], ["held-by", "carton", "r"]]),
            (0.5, [["mode", "m", "off"], ["held-by", "carton", "r"], ["poured-into", "sugar", "head"]]),
            (1.0, [["mode", "m", "off"], ["held-by", "carton", "r"], ["contains", "head", "sugar"]])]
    assert G.check(goal, good)[0]
    bad = [(t, [x if x[0] != "mode" else ["mode", "m", "spinning"] for x in a]) for t, a in good]
    ok, v = G.check(goal, bad)
    assert not ok and v[0][1] == 0.5 and v[0][2] == "happened"


def test_booth_coverage_is_complete():
    cov = G.coverage(FORMS)
    assert cov["without_telos"] == [] and cov["unrefinable"] == []
