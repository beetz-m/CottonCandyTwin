"""M1: booth.lisp executed by ccram's generic kernel through the booth adapter on the CRAM booth (kinematic PR2, FlossMachineProcess).

Needs the CRAM environment:   cram/run.sh pytest cram/concept/tests/test_kernel_runs.py      (several minutes)
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.expanduser("~/Documents/ConceptualCRAM"))
pytest.importorskip("coraplex")
os.environ.setdefault("CORAPLEX_VISUALIZATION", "none")
from ccram.activity import load  # noqa: E402
from ccram.session import demonstration  # noqa: E402

ACTIVITY = load(HERE)


def run(plan, scenario=""):
    demo = demonstration(ACTIVITY, plan, scenario)
    demo.run()
    demo.process = demo.session.adapter.process
    performs = [n for n in demo.interp.episode if "schema" in n]
    notes = [n["note"] for n in demo.interp.episode if "note" in n]
    return demo, performs, notes


def test_fill_spinner_head_all_goals_achieved():
    demo, performs, _ = run("fill-spinner-head")
    assert demo.failure is None
    assert [n["schema"] for n in performs] == ["transporting", "navigating", "pouring-into", "navigating", "putting-down"]
    assert all(n["verdict"] == "goal achieved" for n in performs)
    assert abs(demo.process.sugar_in_head_kg - 0.054) < 1e-6           # 90 % of the 60 g head (GM_MAN_EXP)


def test_gate_refuses_pouring_into_a_running_machine_and_the_carton_goes_back():
    demo, performs, _ = run("fill-spinner-head", "motor-on-after-take")
    assert demo.failure is not None and demo.failure.kind == "sugar-poured-into-spinning-head"
    pour = next(n for n in performs if n["schema"] == "pouring-into")
    assert pour["verdict"].startswith("refused by the gate")
    put = next(n for n in performs if n["schema"] == "putting-down")      # evap-protect tail still ran
    assert put["verdict"] == "goal achieved"
    assert demo.process.sugar_in_head_kg == 0.0


def test_whole_shift_delivers_and_closes():
    demo, performs, notes = run("booth-shift")
    assert demo.failure is None
    assert all(n["verdict"] in ("goal achieved", "skipped: goal holds") for n in performs)
    assert any("achieve by (an action (type navigating)" in m for m in notes)   # :pre achieved by refinement
    assert demo.process.phase.value == "off"
    assert demo.process.candies[0].stage.value == "delivered"


def test_running_empty_is_repaired_in_service_and_expected_at_closing():
    demo, performs, notes = run("booth-two-orders", "two-orders-underfilled")
    assert demo.failure is None
    assert any(m.startswith("handled head-running-empty") for m in notes)          # service: unwind + repair
    assert any(m.startswith("signal head-running-empty: expected here") for m in notes)  # closing: continue
    assert [c.stage.value for c in demo.process.candies] == ["delivered", "delivered"]
    pre = [n for n in performs if n["verdict"].startswith("pre-empted")]          # D4: predicted, not run into
    assert pre and pre[0]["schema"] == "monitoring-process" and "head-running-empty" in pre[0]["prediction"]
    assert any(n.get("warrant") == "rational" for n in performs)
