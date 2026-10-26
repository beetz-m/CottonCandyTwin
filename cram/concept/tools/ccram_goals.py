"""Goals as templates of state evolutions (decision D10).

A goal denotes the set of admissible world-state trajectories over an interval i: a conjunction of parts
    (achieve phi [:at (end i)] [:within d])     phi holds at the end of i (within d of its start)
    (maintain phi [:during i] [:until psi])     phi holds at every state of i (until psi holds)
    (prevent phi [:during i] [:while chi])      phi holds at no state of i (no state where chi holds)
    (monitor phi :until psi)                    phi observed at every state until psi (deviations -> failures, Q2)
A plan / action succeeds iff its realised trajectory lies in the set (AICOR: successful state trajectories).

perform and achieve are complementary:
    goal_of(designator)   perform -> the schema's :telos template instantiated with the designator's roles
    refine(statement)     achieve -> action designators whose template achieves phi; maintain -> protection + repair;
                          prevent -> gate constraint + monitor; monitor -> monitoring action + failure handlers
    check(goal, traj)     does a trajectory (list of (t, set of ground atoms)) lie in the goal's set?
    coverage(forms)       every action schema has a telos template (goal inferable); every achieve-family goal of
                          the plans / problems is refinable by some schema (or reported)

    .venv_onto/bin/python tools/ccram_goals.py booth.lisp
"""
import collections
import os
import sys

sys.path.insert(0, os.path.expanduser("~/Documents/HouseholdTwin/tools"))
from sdt_sexpr import parse  # noqa: E402

FORMERS = ("achieve", "maintain", "prevent", "monitor", "protect")
DETS = ("a", "an", "the", "some", "its", "each", "every")


def show(x):
    if isinstance(x, list):
        return "(" + " ".join(show(y) for y in x) + ")"
    if isinstance(x, float) and x == int(x):
        return str(int(x))
    return str(x)


def is_var(x):
    return isinstance(x, str) and x.startswith("?")


# ---------------------------------------------------------------------------------------------------- templates
class Part:
    def __init__(self, former, phi, qual=None, arg=None):
        self.former, self.phi, self.qual, self.arg = former, phi, qual, arg

    def form(self):
        f = [self.former, self.phi]
        if self.qual:
            f += [self.qual, self.arg]
        return f

    def __repr__(self):
        return show(self.form())


def template(telos):
    """(:telos (:over ?i) part ...) or the pre-D10 (:telos phi) == (achieve phi :at (end ?i))."""
    body = telos[1:] if telos and telos[0] == ":telos" else telos
    if body and isinstance(body[0], list) and body[0] and body[0][0] == ":over":
        iv, parts = body[0][1], body[1:]
    else:
        iv, parts = "?i", [["achieve", body[0], ":at", ["end", "?i"]]] if body else []
    out = []
    for p in parts:
        if isinstance(p, list) and p and p[0] in FORMERS:
            out.append(Part(p[0], p[1], p[2] if len(p) > 3 else None, p[3] if len(p) > 3 else None))
    return iv, out


def subst(x, b):
    if isinstance(x, list):
        return [subst(y, b) for y in x]
    return b.get(x, x) if is_var(x) else x


def schemas_of(forms):
    acts, plans, problems = {}, {}, []
    for f in forms:
        if not (isinstance(f, list) and len(f) > 1):
            continue
        if f[0] == "def-action-schema":
            acts[f[1]] = {c[0]: c for c in f[2:] if isinstance(c, list) and c and isinstance(c[0], str)}
        elif f[0] == "def-plan-schema":
            plans[f[1]] = {c[0]: c for c in f[3:] if isinstance(c, list) and c and isinstance(c[0], str)}
        elif f[0] == "assessed-against":
            problems += [c for c in f[2:] if isinstance(c, list) and c and c[0] == "problem"]
    return acts, plans, problems


# ---------------------------------------------------------------------------------------------------- perform -> goal
def goal_of(designator, acts):
    """perform: the goal of an action designator = its schema's telos template with the roles bound."""
    t = next((c[1] for c in designator[2:] if isinstance(c, list) and c and c[0] == "type"), None)
    s = acts.get(t)
    if s is None or ":telos" not in s:
        return None
    b = {"?" + c[0]: c[1] for c in designator[2:] if isinstance(c, list) and len(c) > 1 and c[0] != "type"}
    iv, parts = template(s[":telos"])
    return iv, [Part(p.former, subst(p.phi, b), p.qual, subst(p.arg, b)) for p in parts]


# ---------------------------------------------------------------------------------------------------- achieve -> refine
ONTO = None          # (implies_rel, compatible_type) from the ontology (D9), set by use_ontology()


def use_ontology():
    """Predicate and type reasoning from the ontology: a template predicate Q achieves a goal predicate P when
    Q SubPropertyOf* P (on -> at); two designators match when their types are related by subsumption."""
    global ONTO
    import rdflib
    from rdflib.namespace import RDFS
    import ccram_lang as CL
    o = CL.Ontology()
    lex = CL.Lexicon(o)

    def sup_props(p):
        out, todo = {p}, [p]
        while todo:
            for q in o.g.objects(todo.pop(), RDFS.subPropertyOf):
                if isinstance(q, rdflib.URIRef) and q not in out:
                    out.add(q)
                    todo.append(q)
        return out

    def implies_rel(q, p):
        rq, rp = lex.resolve("rel", q), lex.resolve("rel", p)
        return bool(rq and rp and rp[0] in sup_props(rq[0]))

    def is_agent(a):
        t = lex.resolve("type", a)
        return bool(t) and o.is_a(t[0], CL.DUL.Agent) or bool(t) and o.is_a(t[0], CL.DUL.PhysicalAgent)

    def compatible(a, b):
        ta, tb = lex.resolve("type", a), lex.resolve("type", b)
        if not ta or not tb:
            return a == b
        return o.is_a(ta[0], tb[0]) or o.is_a(tb[0], ta[0])
    ONTO = (implies_rel, compatible, is_agent)
    return ONTO


def noun(d):
    if d[1] in ("action", "object", "location", "motion"):
        k = next((c[1] for c in d[2:] if isinstance(c, list) and c and c[0] == "type"), None)
        return k or d[1]
    return d[1]


def unify(pat, x, b):
    """Template pattern (variables ?x) against a goal formula. Designators are resolved by the climb, not here: two
    designators match when their types are compatible (ontology subsumption; equal nouns without the ontology)."""
    if is_var(pat):
        if pat in b and b[pat] != x:
            return None
        return {**b, pat: x}
    if isinstance(pat, list) and isinstance(x, list) and len(pat) == 2 == len(x) and pat[0] == "mass" == x[0] \
            and isinstance(pat[1], (int, float)) and isinstance(x[1], (int, float)):
        return b if x[1] >= pat[1] - 1e-3 else None    # a mass in a goal: at least that much (1 g resolution)
    if isinstance(pat, list) and isinstance(x, list):
        dp, dx = bool(pat and pat[0] in DETS), bool(x and x[0] in DETS)
        if dp and dx:
            a, c = noun(pat), noun(x)
            generic = {"object", "thing", "location"}
            ok = a in generic or c in generic or (ONTO[1](a, c) if ONTO else a == c)
            return b if ok else None
        if dp or dx:
            return b
        if len(pat) != len(x):
            return None
        for p, y in zip(pat, x):
            b = unify(p, y, b)
            if b is None:
                return None
        return b
    if isinstance(pat, list) and pat and pat[0] in DETS and isinstance(x, str) or \
            isinstance(x, list) and x and x[0] in DETS and isinstance(pat, str):
        d, sym = (pat, x) if isinstance(pat, list) else (x, pat)
        tag = next((c[1] for c in d[2:] if isinstance(c, list) and len(c) > 1 and c[0] == "tag"), None)
        return b if tag is None or tag == sym else None   # a designator against an entity's symbol: it may refer
        #                                                   to it -- a tagged one only to that tag
    if isinstance(pat, (int, float)) and isinstance(x, (int, float)) and not isinstance(pat, bool):
        return b if abs(float(pat) - float(x)) <= NUM_TOL else None
    return b if pat == x else None


NUM_TOL = 0.02     # a commanded setting is a region, not a point: reached within the controller's tolerance


def head_match(p_phi, g_phi):
    """Template part predicate vs goal predicate: equal, or the template's implies the goal's (ontology)."""
    if not (isinstance(p_phi, list) and isinstance(g_phi, list) and p_phi and g_phi):
        return False
    if p_phi[0] == g_phi[0]:
        return True
    return bool(ONTO and isinstance(p_phi[0], str) and isinstance(g_phi[0], str) and ONTO[0](p_phi[0], g_phi[0]))


PLANS = {}             # plan schemas (refinement into plans), set by coverage() / main()
PROCESS_PREDS = set()   # states a process produces by itself (microtheory): reached by waiting (monitoring-process)


def refine(stmt, acts):
    """A goal statement -> what achieves it. Returns a list of (kind, form) candidates."""
    former, phi = stmt[0], stmt[1]
    out = []
    if former in ("achieve", "maintain", "protect"):
        for name, s in acts.items():
            if ":telos" not in s:
                continue
            _, parts = template(s[":telos"])
            for p in parts:
                if p.former != "achieve":
                    continue
                if is_var(p.phi):                       # (achieve ?until ...): waiting -- only for process states
                    if not (isinstance(phi, list) and phi and phi[0] in PROCESS_PREDS):
                        continue
                    b = {p.phi: phi}
                elif not head_match(p.phi, phi):
                    continue
                else:
                    b = unify([phi[0]] + p.phi[1:], phi, {})
                if b is None:
                    continue
                roles = [[k[1:], v] for k, v in b.items() if k[1:] in
                         {r[0] for r in s.get(":roles", [None])[1:] if isinstance(r, list)}]
                if ONTO and any(r == "object" and isinstance(v, list) and v and v[0] in DETS and ONTO[2](noun(v))
                                for r, v in roles):
                    continue                            # an agent cannot be the patient (SOMA Patient: non-agentive)
                out.append(("action", ["an", "action", ["type", name]] + roles))
        for name, ps in PLANS.items():                  # plan schemas achieve their success condition (:succ)
            for c in ps.get(":succ", [None])[1:]:
                for phi_s in (c[1:] if isinstance(c, list) and c and c[0] == "and" else [c]):
                    if isinstance(phi_s, list) and head_match(phi_s, phi) and \
                            unify([phi[0]] + phi_s[1:], phi, {}) is not None:
                        out.append(("plan", ["perform-plan", name]))
        if former in ("maintain", "protect"):
            out = [("protection", ["protect", phi, ":until", stmt[3] if len(stmt) > 3 else ["end", "?i"]]),
                   ("monitor", ["monitor", phi])] + [("repair", f) for _, f in out]
    elif former == "prevent":
        guard = []
        for name, s in acts.items():
            _, parts = template(s.get(":telos", [":telos"]))
            for p in parts:
                if p.former == "prevent" and unify(p.phi, phi, {}) is not None:
                    guard.append(name)
        out.append(("gate", ["prevent", phi] + (stmt[2:] if len(stmt) > 2 else [])))
        out.append(("monitor", ["monitor", ["not", phi]]))
        out += [("guarded-by-schema", name) for name in guard]
    elif former == "monitor":
        out.append(("action", ["an", "action", ["type", "monitoring-process"], ["process", phi],
                               ["until", stmt[3] if len(stmt) > 3 else "?until"]]))
    return out


# ---------------------------------------------------------------------------------------------------- trajectories
def holds(phi, atoms):
    """phi at one state: (and ..), (or ..), (not ..) over ground atoms; designator arguments match any value."""
    if isinstance(phi, list) and phi:
        if phi[0] == "and":
            return all(holds(x, atoms) for x in phi[1:])
        if phi[0] == "or":
            return any(holds(x, atoms) for x in phi[1:])
        if phi[0] == "not":
            return not holds(phi[1], atoms)
    pat = phi if isinstance(phi, list) else [phi]
    if any(unify(pat, a, {}) is not None for a in atoms):
        return True
    if ONTO and pat and isinstance(pat[0], str):        # an atom whose predicate implies the goal's (on -> at)
        return any(isinstance(a, list) and a and isinstance(a[0], str) and a[0] != pat[0] and ONTO[0](a[0], pat[0])
                   and unify(pat, [pat[0]] + a[1:], {}) is not None for a in atoms)
    return False


def check(goal, traj):
    """Does the trajectory [(t, [atom, ...]), ...] lie in the goal's set? -> (ok, [violations])."""
    _, parts = goal
    bad = []
    t0 = traj[0][0]
    for p in parts:
        states = traj
        if p.qual == ":until" and p.arg is not None:
            k = next((i for i, (_, a) in enumerate(traj) if holds(p.arg, a)), None)
            states = traj[:k] if k is not None else traj
            if p.former in ("monitor",) and k is None:
                bad.append((p, None, "until-condition never reached"))
        if p.qual == ":while":
            states = [(t, a) for t, a in traj if holds(p.arg, a)]
        if p.former == "achieve":
            if p.qual == ":within":
                lim = t0 + float(p.arg) if isinstance(p.arg, (int, float)) else None
                ok = any(holds(p.phi, a) for t, a in traj if lim is None or t <= lim)
            else:
                ok = holds(p.phi, traj[-1][1])
            if not ok:
                bad.append((p, traj[-1][0], "not achieved"))
        elif p.former == "monitor":             # an observation, not a truth requirement: its deviations are
            continue                            # signalled as failures at run time (Q2); :until via achieve parts
        elif p.former in ("maintain", "protect"):
            for t, a in states:
                if not holds(p.phi, a):
                    bad.append((p, t, "not maintained"))
                    break
        elif p.former == "prevent":
            for t, a in states:
                if holds(p.phi, a):
                    bad.append((p, t, "happened"))
                    break
    return not bad, bad


# ---------------------------------------------------------------------------------------------------- coverage
def process_preds(forms):
    """Microtheory states: 'mode', the quantities, and what plans wait for with monitoring-process (until ...)."""
    out = {"mode"}
    for f in forms:
        if isinstance(f, list) and f and f[0] == "def-microtheory":
            for c in f[2:]:
                if isinstance(c, list) and c and c[0] == ":quantities":
                    out |= {q[0] for q in c[1:] if isinstance(q, list)}

    def walk(x):
        if isinstance(x, list) and x:
            if x[0] == "until" and len(x) > 1 and isinstance(x[1], list) and x[1]:
                out.add(x[1][0])
            for y in x:
                walk(y)
    walk(forms)
    return out


def coverage(forms):
    acts, plans, problems = schemas_of(forms)
    PROCESS_PREDS.update(process_preds(forms))
    PLANS.update(plans)
    no_telos = [n for n, s in acts.items() if ":telos" not in s]
    goals = []

    def walk(x, where):
        if isinstance(x, list) and x:
            if x[0] in ("achieve", "maintain", "protect") and len(x) > 1 and isinstance(x[1], list):
                goals.append((where, x))
            for y in x[1:]:
                walk(y, where)
    for n, p in plans.items():
        walk(p.get(":body", []), f"plan {n}")
    for pr in problems:
        walk(pr, f"problem {pr[1]}")
    unrefined = []
    for where, g in goals:
        for phi in (g[1:] if g[0] == "achieve" else [g[1]]):
            if not isinstance(phi, list) or phi[0] in (":at", ":during", ":until", ":within", ":while"):
                continue
            if not any(k in ("action", "repair", "plan") for k, _ in refine([g[0], phi], acts)):
                unrefined.append((where, show([g[0], phi])))
    return dict(schemas=len(acts), without_telos=no_telos, goal_statements=len(goals), unrefinable=unrefined)


def main(path):
    use_ontology()
    forms = parse(open(path).read())
    PROCESS_PREDS.update(process_preds(forms))
    PLANS.update(schemas_of(forms)[1])
    acts, _, _ = schemas_of(forms)
    print("== perform -> goal (one designator per schema, roles as in the booth plans)")
    d = parse("(an action (type pouring-into) (object ?sugar) (destination (tagged spinner-head ?machine)) "
              "(amount (some substance (mass portion-batch))))")[0]
    iv, parts = goal_of(d, acts)
    for p in parts:
        print("   ", p)
    print("== achieve / maintain / prevent / monitor -> refinement")
    for s in ["(achieve (on (the sponge) (its destination)))", "(achieve (at (each tool) (its destination)))", "(achieve (at (the robot) (the station (tag serving))))",
              "(achieve (contains (tagged spinner-head machine) (some sugar)))",
              "(prevent (poured-into (some sugar) (tagged spinner-head machine)) :while (not (mode floss-machine off)))",
              "(maintain (held-by ?stick ?arm) :until (delivered ?candy))",
              "(achieve (delivered (each cotton-candy (ordered-by (a customer)))))", "(achieve (mode floss-machine off))",
              "(monitor (mode floss-machine) :until (portion-spun))"]:
        print("  ", s)
        for k, f in refine(parse(s)[0], acts):
            print("      ", k, show(f) if isinstance(f, list) else f)
    print("== coverage")
    for k, v in coverage(forms).items():
        print("  ", k, v)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "booth.lisp")
