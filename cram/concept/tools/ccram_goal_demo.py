"""D10 on the executable floss machine model: goal templates checked against trajectories that the twin's process
model (cram/cotton_candy/process.py, FlossMachineProcess) produces. The process logic runs as is; only the switches are
stubs (no robot presses them here) -- the trajectories are the machine's state evolution, sampled every 0.5 s.

    ~/.virtualenvs/cram-env/bin/python tools/ccram_goal_demo.py      (needs krrood from the CRAM environment)
Writes ontology/goal_demo.json.
"""
import json
import os
import sys
from types import SimpleNamespace

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, os.path.dirname(HERE))                         # cram/ -> cotton_candy
import ccram_goals as G  # noqa: E402
from cotton_candy.process import FlossMachineProcess, SugarPouredIntoSpinningHead  # noqa: E402

HEAD = ["tagged", "spinner-head", "machine"]


class Booth:
    """Machine stub + process + the atoms of each 0.5 s state (what the trajectory checker sees)."""

    def __init__(self):
        sw = lambda: SimpleNamespace(is_on=False)                  # noqa: E731
        self.m = SimpleNamespace(motor_switch=sw(), heat_switch=sw(), heat_control=SimpleNamespace(travel_fraction=1.0))
        self.p = FlossMachineProcess(self.m)
        self.traj, self.events, self.held = [], set(), set()

    def atoms(self):
        a = [["mode", "floss-machine", self.p.phase.value.replace("_", "-")]]
        if self.p.sugar_in_head_kg > 1e-6:
            a.append(["contains", HEAD, "sugar"])
        if self.p.portion_ready:
            a.append(["portion-spun"])
        if self.p.burnt_out_s >= self.p.timings.burn_out_s if hasattr(self.p.timings, "burn_out_s") else False:
            a.append(["burnt-out", "machine"])
        a += [["held-by", o, "right-arm"] for o in self.held]
        a += [list(e) for e in self.events]
        return a

    def tick(self, seconds):
        n = int(round(seconds / 0.5))
        for _ in range(n):
            self.traj.append((self.p.time_s, self.atoms()))
            self.events.clear()
            self.p.advance(0.5)

    def switch(self, motor=None, heat=None):
        if motor is not None:
            self.m.motor_switch.is_on = motor
        if heat is not None:
            self.m.heat_switch.is_on = heat
        self.p.notice_switches()

    def pour(self, kg):
        self.events.add(("poured-into", "sugar", tuple(HEAD)))
        try:
            self.p.pour_sugar(kg)
            return None
        except SugarPouredIntoSpinningHead as e:                  # the twin's closing event (process.py)
            return type(e).__name__


def tuples_to_lists(traj):
    fix = lambda x: [fix(y) for y in x] if isinstance(x, (list, tuple)) else x   # noqa: E731
    return [(t, [fix(a) for a in atoms]) for t, atoms in traj]


def run():
    forms = G.parse(open(os.path.join(HERE, "booth.lisp")).read())
    acts, plans, _ = G.schemas_of(forms)
    pour_designator = G.parse("(an action (type pouring-into) (object sugar-carton) (destination (tagged spinner-head "
                              "machine)) (amount sugar))")[0]
    pour_goal = G.goal_of(pour_designator, acts)
    out = {"pour_goal": [G.show(p.form()) for p in pour_goal[1]]}

    # A: refill done right -- carton held, poured with the machine off
    b = Booth()
    b.held.add("sugar-carton")
    b.tick(1.0)
    exc = b.pour(0.054)
    b.tick(1.0)
    ok, bad = G.check(pour_goal, tuples_to_lists(b.traj))
    out["A_pour_machine_off"] = dict(raised=exc, satisfied=ok, violations=[(G.show(p.form()), t, w) for p, t, w in bad])

    # B: the same action with the motor running -- the process raises its closing-event failure; the template is
    #    violated at the pour instant (prevent ... :while (not (mode floss-machine off)))
    b = Booth()
    b.held.add("sugar-carton")
    b.switch(motor=True)
    b.tick(1.0)
    exc = b.pour(0.054)
    b.tick(1.0)
    ok, bad = G.check(pour_goal, tuples_to_lists(b.traj))
    out["B_pour_motor_running"] = dict(raised=exc, satisfied=ok, violations=[(G.show(p.form()), t, w) for p, t, w in bad])

    # C: a service shift with one head filling, then the closing burn-out -- the same state evolution judged by the
    #    two problems' templates (Q2: running-empty is a fault in service, the goal at closing)
    b = Booth()
    b.pour(0.054)
    b.switch(motor=True, heat=True)
    b.tick(400.0)                                     # warm up, produce until the head runs empty, burn out
    traj = tuples_to_lists(b.traj)
    service = (None, [G.Part("prevent", ["mode", "floss-machine", "running-empty"], ":during", "?shift")])
    closing = (None, [G.Part("achieve", ["mode", "floss-machine", "running-empty"], ":within", 400.0)])
    first_empty = next((t for t, a in traj if ["mode", "floss-machine", "running-empty"] in a), None)
    out["C_service_prevent_running_empty"] = dict(satisfied=G.check(service, traj)[0], first_running_empty_s=first_empty,
                                                  phases=sorted({a[0][2] for _, a in traj}))
    out["C_closing_achieve_burn_out_mode"] = dict(satisfied=G.check(closing, traj)[0])
    out["note"] = ("trajectories from cram/cotton_candy/process.py (FlossMachineProcess) with stub switches; timings "
                   "= FlossMachineTimings defaults")
    json.dump(out, open(os.path.join(HERE, "ontology", "goal_demo.json"), "w"), indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    run()
