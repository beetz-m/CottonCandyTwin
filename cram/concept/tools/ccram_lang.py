"""The conceptual CRAM language derived from the ontology (decision D9).

The language has no vocabulary of its own: every type, role and relation keyword denotes an ontology term (DUL, SOMA,
USD and the ccram modules in ../ontology). This tool
  * builds the LEXICON from the ontology: keyword -> term, per position (type / role / relation / construct). The
    keyword of a term is its explicit ccram:*Keyword annotation, otherwise its IRI local name in kebab-case.
    Collisions are reported (meta level: the language knows where it is ambiguous).
  * derives the GRAMMAR of action designators from axioms on the task classes:
        Task SubClassOf isTaskOf some R             required role R
        Task SubClassOf isTaskOf only (R1 or ...)   admissible roles
  * LINTS libraries and trees (booth.lisp, docs/sexpr/*.lisp): unknown keywords, roles a task does not admit,
    actions that are not tasks, and library claims that disagree with the ontology (:specializes, :sub, plan
    parameter types).
  * translates designators into DL class expressions (to_dl): a/an/some -> concept, the/tagged -> nominal.

    PY=.venv_onto/bin/python          (owlready2 + rdflib + owlrl; HermiT needs java)
    $PY tools/ccram_lang.py lexicon            # keyword tables, collisions
    $PY tools/ccram_lang.py grammar            # -> ontology/grammar.md
    $PY tools/ccram_lang.py lint booth.lisp    # -> report
    $PY tools/ccram_lang.py dl "(an action (type pouring-into) (destination (tagged spinner-head machine)))"
"""

import collections
import difflib
import glob
import json
import os
import re
import sys

import rdflib
from rdflib.namespace import OWL, RDF, RDFS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # cram/concept
ONTO = os.path.join(HERE, "ontology")
sys.path.insert(0, os.path.expanduser("~/Documents/HouseholdTwin/tools"))
from sdt_sexpr import parse  # noqa: E402  (one reader for trees and libraries)

DUL = rdflib.Namespace("http://www.ontologydesignpatterns.org/ont/dul/DUL.owl#")
SOMA = rdflib.Namespace("http://www.ease-crc.org/ont/SOMA.owl#")
CCRAM = rdflib.Namespace("https://aicor.knowledge/ccram#")
PREFIXES = {"dul": str(DUL), "soma": str(SOMA), "ccram": str(CCRAM), "cc": "https://aicor.knowledge/cotton-candy#",
            "sdt": "https://aicor.knowledge/sdt#", "usd": "https://ease-crc.org/ont/USD.owl#"}
MODULES = ["ccram-lang.ttl", "ccram-actions.ttl", "booth.ttl"]


def kebab(name):
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", s)
    return s.replace("_", "-").lower()


def local(iri):
    s = str(iri)
    return s.split("#")[-1] if "#" in s else s.rstrip("/").split("/")[-1]


def short(iri):
    s = str(iri)
    for p, ns in PREFIXES.items():
        if s.startswith(ns):
            return f"{p}:{s[len(ns):]}"
    return s


def load_graph(modules=MODULES, usd=True):
    """usd=False for DL reasoning: the USD ontology uses datatypes outside the OWL 2 datatype map (usd:vector3f ...)
    without definitions, which HermiT rejects."""
    g = rdflib.Graph()
    for f in sorted(glob.glob(os.path.join(ONTO, "imports", "rdf", "*.owl"))):
        g.parse(f, format="xml")
    if usd:
        g.parse(os.path.join(ONTO, "imports", "USD.owl"), format="xml")
    for m in modules:
        g.parse(os.path.join(ONTO, m), format="turtle")
    return g


class Ontology:
    def __init__(self, g=None):
        self.g = g or load_graph()
        g = self.g
        self.classes = {c for c in g.subjects(RDF.type, OWL.Class) if isinstance(c, rdflib.URIRef)}
        self.props = {p for t in (OWL.ObjectProperty, OWL.DatatypeProperty) for p in g.subjects(RDF.type, t)
                      if isinstance(p, rdflib.URIRef)}
        self._sup = collections.defaultdict(set)
        for c, o in g.subject_objects(RDFS.subClassOf):
            if isinstance(c, rdflib.URIRef) and isinstance(o, rdflib.URIRef):
                self._sup[c].add(o)
        for c, o in g.subject_objects(OWL.equivalentClass):
            if isinstance(c, rdflib.URIRef) and isinstance(o, rdflib.URIRef):
                self._sup[c].add(o)
                self._sup[o].add(c)
        self._anc = {}

    def ancestors(self, c):
        if c not in self._anc:
            out, todo = set(), [c]
            while todo:
                x = todo.pop()
                for s in self._sup.get(x, ()):
                    if s not in out:
                        out.add(s)
                        todo.append(s)
            self._anc[c] = out
        return self._anc[c]

    def is_a(self, c, sup):
        return c == sup or sup in self.ancestors(c)

    def ann(self, s, p):
        return [str(o) for o in self.g.objects(s, p)]

    def restrictions(self, c, prop):
        """(kind, filler-list) of the named class's own restrictions on prop."""
        out = []
        for r in self.g.objects(c, RDFS.subClassOf):
            if isinstance(r, rdflib.URIRef) or self.g.value(r, OWL.onProperty) != prop:
                continue
            for kind, p in (("some", OWL.someValuesFrom), ("only", OWL.allValuesFrom)):
                f = self.g.value(r, p)
                if f is None:
                    continue
                if isinstance(f, rdflib.URIRef):
                    out.append((kind, [f]))
                else:
                    u = self.g.value(f, OWL.unionOf)
                    out.append((kind, list(rdflib.collection.Collection(self.g, u)) if u else []))
        return out


class Lexicon:
    """keyword -> terms, per position. Explicit keywords win over derived ones; remaining collisions are reported and
    resolved by module preference (ccram / domain modules > SOMA > DUL > USD), first term = the reading used."""

    ORDER = ("https://aicor.knowledge/", str(SOMA), str(DUL), "https://ease-crc.org/ont/USD")

    @classmethod
    def rank(cls, t):
        s = str(t)
        return (next((i for i, ns in enumerate(cls.ORDER) if s.startswith(ns)), len(cls.ORDER)), s)

    def __init__(self, onto):
        self.o = onto
        g = onto.g
        self.type, self.role, self.rel, self.construct, self.head = {}, {}, {}, {}, {}
        self.collisions = []
        explicit_t = {(str(k)): c for c in onto.classes for k in g.objects(c, CCRAM.typeKeyword)}
        explicit_r = {(str(k)): c for c in onto.classes for k in g.objects(c, CCRAM.roleKeyword)}
        explicit_p = {(str(k)): p for p in onto.props for k in g.objects(p, CCRAM.relationKeyword)}
        role_cls = {c for c in onto.classes if onto.is_a(c, DUL.Role)}
        derived_t = collections.defaultdict(set)
        for c in onto.classes:
            dk = onto.ann(c, CCRAM.derivedKeyword)
            derived_t[dk[0] if dk else kebab(local(c))].add(c)
        for k, cs in derived_t.items():
            if k in explicit_t:
                cs = {c for c in cs if c == explicit_t[k]}
                if not cs:
                    continue
            cs = sorted(cs, key=self.rank)
            distinct = [c for i, c in enumerate(cs) if not any(c in onto._sup.get(d, ()) and d in onto._sup.get(c, ())
                                                               for d in cs[:i])]     # equivalent classes count once
            if len(distinct) > 1:
                self.collisions.append(("type", k, [short(c) for c in distinct]))
            self.type[k] = cs
        for k, c in explicit_t.items():
            self.type[k] = [c]
        # roles: explicit role keywords, otherwise derived from role classes
        for c in role_cls:
            k = kebab(local(c))
            if k not in explicit_r:
                self.role.setdefault(k, []).append(c)
        for k, c in explicit_r.items():
            self.role[k] = [c]
        derived_p = collections.defaultdict(set)
        for p in onto.props:
            derived_p[kebab(local(p))].add(p)
        for k, ps in derived_p.items():
            if k in explicit_p:
                continue
            ps = sorted(ps, key=self.rank)
            if len(ps) > 1:
                self.collisions.append(("relation", k, [short(p) for p in ps]))
            self.rel[k] = ps
        for k, p in explicit_p.items():
            self.rel[k] = [p]
        for kind in (CCRAM.PlanLanguageConstruct, CCRAM.DefinitionForm, CCRAM.SchemaFacet, CCRAM.Determiner,
                     CCRAM.TemporalQualifier):
            for cls in [c for c in onto.classes if onto.is_a(c, kind)]:
                for ind in g.subjects(RDF.type, cls):
                    for k in g.objects(ind, CCRAM.keyword):
                        self.construct[str(k)] = ind
        for c in onto.classes:
            for k in g.objects(c, CCRAM.headKeyword):
                self.head[str(k)] = c
        self.determiners = {k for k, v in self.construct.items()
                            if any(onto.is_a(t, CCRAM.Determiner) for t in g.objects(v, RDF.type))}

    def keyword_of(self, term, pos):
        """The keyword the language uses for a term in a position (explicit annotation first, then derived)."""
        g = self.o.g
        ann = {"type": CCRAM.typeKeyword, "role": CCRAM.roleKeyword, "rel": CCRAM.relationKeyword}[pos]
        ex = [str(k) for k in g.objects(term, ann)]
        if ex:
            return ex[0]
        dk = self.o.ann(term, CCRAM.derivedKeyword)
        return dk[0] if dk else kebab(local(term))

    def resolve(self, pos, k):
        table = {"type": self.type, "role": self.role, "rel": self.rel}[pos]
        if isinstance(k, str) and ":" in k and not k.startswith(":"):
            p, n = k.split(":", 1)
            if p in PREFIXES:
                cs = [c for c in self.o.classes if str(c).startswith(PREFIXES[p]) and kebab(local(c)) == n]
                return cs
        return table.get(k, [])

    def suggest(self, pos, k, n=3):
        table = {"type": self.type, "role": self.role, "rel": self.rel}[pos]
        return difflib.get_close_matches(str(k), list(table), n=n, cutoff=0.7)


def grammar(onto, lex):
    """Per task class: required and admissible roles (keywords), from the isTaskOf axioms (inherited)."""
    rows = {}
    tasks = [c for c in onto.classes if onto.is_a(c, DUL.Task)]
    rk = lambda r: lex.keyword_of(r, "role")                                    # noqa: E731
    for t in tasks:
        req, adm, adm_from = set(), None, None
        for c in [t] + sorted(onto.ancestors(t), key=lambda a: (len(onto.ancestors(a)) * -1, str(a))):
            for kind, fs in onto.restrictions(c, DUL.isTaskOf):
                if kind == "some":
                    req |= set(fs)
                elif adm is None and fs != [DUL.Role]:                          # DUL: Task only isTaskOf Role (any)
                    adm, adm_from = set(fs), c
        if not req and adm is None:
            continue
        rows[t] = dict(keyword=lex.keyword_of(t, "type"), required=sorted(rk(r) for r in req),
                       admissible=sorted(rk(r) for r in (adm or set())), closure_from=adm_from,
                       subtasks=[short(x) for x in onto.g.objects(t, CCRAM.hasSubTask)],
                       telos=onto.ann(t, CCRAM.telosState),
                       parents=sorted(short(p) for p in onto._sup.get(t, ()) ))
    return rows


# ---------------------------------------------------------------------------------------------------- linter
def G_show(x):
    return "(" + " ".join(G_show(y) for y in x) + ")" if isinstance(x, list) else str(x)


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, where, msg):
        self.items.append((level, where, msg))

    def counts(self):
        return collections.Counter(i[0] for i in self.items)


VAR = re.compile(r"^\?[\w-]+$")
# positions whose arguments are conditions (state predicates): the predicate symbols found there must become ontology
# relations / state classes (the extension backlog); elsewhere list heads are DSL slots, not predicates
COND_KEYS = {":telos", ":pre", ":eff", ":succ", ":monitor", "achieve", "maintain", "prevent", "protect", "goal",
             "terminal", "until", ":when", ":guard", "wait-for", "equate", ":until", "monitor"}
COMPARATORS = {">=", "<=", "=", "<", ">", "*", "+", "-"}
LITERAL_HEADS = {"label", "capacity"}          # node attributes carried as data (attribute k v :status ...)


class Linter:
    def __init__(self, onto, lex):
        self.o, self.lex = onto, lex
        self.gram = grammar(onto, lex)
        self.task_by_kw = {r["keyword"]: t for t, r in self.gram.items()}
        self.used = collections.Counter()
        self.unresolved_pred = collections.Counter()

    def lint_text(self, text, name="?"):
        rep = Report()
        forms = parse(text)
        for form in forms:
            if isinstance(form, list) and form:
                self.top(form, rep, name)
        self.failure_flow(forms, rep, name)
        return rep

    # -- failures (Q2): who can signal what, and is it caught (D6 has-fallback, checked statically)
    def fclass(self, k):
        cs = self.lex.resolve("type", k)
        return cs[0] if cs and self.o.is_a(cs[0], CCRAM.FailureDescription) else None

    def failure_flow(self, forms, rep, name):
        acts, plans, fails, signals = {}, {}, {}, collections.defaultdict(set)
        for f in forms:
            if not (isinstance(f, list) and len(f) > 1):
                continue
            body = {c[0]: c[1:] for c in f[2:] if isinstance(c, list) and c and isinstance(c[0], str)}
            if f[0] == "def-action-schema":
                acts[f[1]] = body
            elif f[0] == "def-plan-schema":
                plans[f[1]] = {c[0]: c[1:] for c in f[3:] if isinstance(c, list) and c and isinstance(c[0], str)}
            elif f[0] == "def-failure":
                fails[f[1]] = body
            elif f[0] == "def-microtheory":
                for m in body.get(":modes", []):
                    if isinstance(m, list) and ":signals" in m:
                        signals[("microtheory", f[1])].add(m[m.index(":signals") + 1])
        where0 = f"{name}:failures"
        for k, b in fails.items():
            c = self.fclass(k)
            if c is None:
                rep.add("ERROR", where0, f"def-failure '{k}' is not a failure class of the ontology")
                continue
            for p_ in b.get(":specializes", []):
                pc = self.fclass(p_)
                if pc is None or not self.o.is_a(c, pc):
                    rep.add("META", where0, f"failure '{k}' specializes '{p_}' but the ontology does not entail it")
            for sb in b.get(":signalled-by", []):
                if isinstance(sb, list) and len(sb) > 1:
                    signals[(sb[0], sb[1])].add(k)
        self.signals = signals

        def action_failures(t):
            out = set()
            a = acts.get(t, {})
            for e in a.get(":failures", []):
                if isinstance(e, list) and e:
                    out.add(e[0])
            out |= signals.get(("action", t), set())
            for c in a.get(":causal", []):
                if isinstance(c, list) and c and c[0] == ":microtheory":
                    out |= signals.get(("microtheory", c[1]), set())
            return out

        def caught(fk, handlers):
            c = self.fclass(fk)
            return any(c is not None and h is not None and self.o.is_a(c, h) for hs in handlers for h in hs)

        def recoverable(fk):
            c = self.fclass(fk)
            vals = [str(v) for x in ([c] + sorted(self.o.ancestors(c), key=str)) if c is not None
                    for v in self.o.g.objects(x, CCRAM.recoverable)]
            return not vals or vals[0].lower() not in ("false", "0")

        prohibited = [c for c in self.o.classes if self.o.is_a(c, CCRAM.ProhibitedAction) and c != CCRAM.ProhibitedAction]
        memo = {}

        def plan_failures(pn, stack=()):
            """Concrete failures a plan lets out (computed), with the report entries for its own body."""
            if pn in memo:
                return memo[pn]
            if pn in stack or pn not in plans:
                return set()
            pb = plans[pn]
            where = f"{name}:def-plan-schema {pn}"
            esc = [self.fclass(e) for e in pb.get(":escapes", [])]
            found = {}

            def walk(x, handlers):
                if not isinstance(x, list) or not x:
                    return
                h = x[0]
                if h == "with-failure-handling" and len(x) > 2:
                    hs = []
                    for cl in x[1]:
                        if isinstance(cl, list) and cl:
                            hc = self.fclass(cl[0])
                            if hc is None:
                                rep.add("ERROR", where, f"handler for '{cl[0]}', which is not a failure class")
                            elif not recoverable(cl[0]):
                                rep.add("ERROR", where, f"handler for '{cl[0]}': a closing event must be prevented by "
                                                        f"the gate, not handled after the fact")
                            hs.append(hc)
                            for y in cl[2:]:
                                walk(y, handlers)               # handler bodies: only outer handlers apply
                    for y in x[2:]:
                        walk(y, handlers + [hs])
                    return
                srcs = []
                if h == "perform" and len(x) > 1 and self.is_designator(x[1]) and x[1][1] == "action":
                    t = next((c[1] for c in x[1][2:] if isinstance(c, list) and c and c[0] == "type"), None)
                    srcs = [(fk, f"(type {t})") for fk in action_failures(t)]
                elif h == "perform-plan" and len(x) > 1:
                    srcs = [(fk, f"plan {x[1]}") for fk in plan_failures(x[1], stack + (pn,))]
                else:
                    for y in x[1:]:
                        walk(y, handlers)
                    return
                for fk, src in srcs:
                    st_ = found.setdefault((fk, src), [])
                    st_.append(caught(fk, handlers))
            for y in pb.get(":body", []):
                walk(y, [])
            out = set()
            for (fk, src), oks in found.items():
                c = self.fclass(fk)
                if not recoverable(fk):
                    task = src[6:-1] if src.startswith("(type ") else None
                    tc = self.task_by_kw.get(task)
                    guard = [short(p_) for p_ in prohibited
                             if tc is not None and any(tc in self.o.g.objects(r, OWL.someValuesFrom)
                                                       for r in self.o.g.subjects(OWL.onProperty, DUL.executesTask)
                                                       if (None, None, r) in self.o.g)]
                    if task and tc is not None and guard:
                        rep.add("INFO", where, f"{fk} from {src}: closing event, prevented by the gate ({', '.join(guard)})")
                    continue                                # only actions the axiom names can enter it
                if all(oks):
                    rep.add("INFO", where, f"{fk} from {src}: handled")
                    continue
                out.add(fk)
                if any(c is not None and e is not None and self.o.is_a(c, e) for e in esc):
                    rep.add("INFO", where, f"{fk} from {src}: escapes to the caller (declared)")
                else:
                    rep.add("META", where, f"{fk} from {src} is neither handled nor declared in :escapes "
                                           f"(D6 has-fallback)")
            memo[pn] = out
            return out

        for pn in plans:
            plan_failures(pn)
        self.plan_calls(forms, rep, name)

    def plan_calls(self, forms, rep, name):
        """perform-plan arguments bind positionally to the callee's parameters: each argument's type (a caller
        parameter's type, or a designator's noun) must be subsumed by the parameter's type (ontology)."""
        params = {f[1]: f[2] for f in forms if isinstance(f, list) and len(f) > 2 and f[0] == "def-plan-schema"}

        def walk(x, caller, cparams):
            if not isinstance(x, list) or not x:
                return
            if x[0] == "perform-plan" and len(x) > 1:
                callee = params.get(x[1])
                where = f"{name}:def-plan-schema {caller}"
                if callee is None:
                    rep.add("ERROR", where, f"perform-plan {x[1]}: no such plan schema")
                    return
                if len(x) - 2 > len(callee):
                    rep.add("ERROR", where, f"perform-plan {x[1]}: {len(x) - 2} arguments, it takes {len(callee)}")
                for (pn, ptype), a in zip(callee, x[2:]):
                    if isinstance(a, str) and a.startswith("?"):
                        atype = cparams.get(a[1:])
                    elif isinstance(a, list) and len(a) > 1 and a[0] in self.lex.determiners:
                        atype = a[1]
                    else:
                        atype = None
                    if atype is None:
                        rep.add("ERROR", where, f"perform-plan {x[1]}: argument {G_show(a)} for {pn} has no known type")
                        continue
                    ta, tp = self.lex.resolve("type", atype), self.lex.resolve("type", ptype)
                    if ta and tp and not self.o.is_a(ta[0], tp[0]) and atype != ptype:
                        rep.add("ERROR", where, f"perform-plan {x[1]}: argument {G_show(a)} ({atype}) bound to "
                                                f"parameter {pn} ({ptype}) -- positional mismatch?")
                if len(x) - 2 < len(callee):
                    rep.add("INFO", where, f"perform-plan {x[1]}: {', '.join(p for p, _ in callee[len(x) - 2:])} "
                                           f"left to the climb")
                return
            for y in x:
                walk(y, caller, cparams)
        for f in forms:
            if isinstance(f, list) and len(f) > 2 and f[0] == "def-plan-schema":
                walk(f[3:], f[1], {p: t for p, t in f[2]})

    # -- helpers
    def is_designator(self, f):
        return isinstance(f, list) and len(f) >= 2 and isinstance(f[0], str) and f[0] in self.lex.determiners and \
            not (f[0] in ("each", "every") and VAR.match(str(f[1])))      # (each ?x D G): quantified goal (D10)

    def term(self, pos, k, rep, where):
        cs = self.lex.resolve(pos, k)
        if cs:
            self.used[(pos, k)] += 1
            return cs[0]
        sug = self.lex.suggest(pos, k)
        rep.add("ERROR", where, f"{pos} keyword '{k}' denotes no ontology term" + (f" (close: {', '.join(sug)})" if sug else ""))
        return None

    # -- forms
    def top(self, f, rep, name):
        head = f[0]
        if head == ":tag":
            self.tree(f, rep, f"{name}:{f[1]}")
            return
        if head not in self.lex.construct:
            rep.add("ERROR", name, f"top-level form '{head}' is not a definition form of the language")
            return
        where = f"{name}:{head} {f[1] if len(f) > 1 and isinstance(f[1], str) else ''}".strip()
        if head == "def-action-schema":
            self.action_schema(f, rep, where)
        elif head == "def-plan-schema":
            self.plan_schema(f, rep, where)
        elif head == "def-category-lattice":
            self.lattice(f, rep, where)
        else:
            self.walk(f[1:], rep, where)

    def tree(self, f, rep, where):
        """(:tag NAME (node (is-a K) ... (parts ...)))"""
        if len(f) < 3 or not isinstance(f[2], list):
            return
        for sub in f[2][1:] if f[2] and f[2][0] == "node" else []:
            if isinstance(sub, list) and sub:
                if sub[0] == "is-a" and len(sub) > 1:
                    self.term("type", sub[1], rep, where)
                elif sub[0] == "parts":
                    for p in sub[1:]:
                        if isinstance(p, list) and p and p[0] == ":tag":
                            self.tree(p, rep, f"{where}/{p[1]}")
                elif sub[0] == "attribute" and len(sub) > 1 and sub[1] not in LITERAL_HEADS:
                    self.term("rel", sub[1], rep, where)

    def action_schema(self, f, rep, where):
        name = f[1]
        t = self.task_by_kw.get(name)
        if t is None:
            tc = self.term("type", name, rep, where)
            if tc is not None and not self.o.is_a(tc, DUL.Task):
                rep.add("ERROR", where, f"schema '{name}' names {short(tc)}, which is not a task")
            elif tc is not None:
                rep.add("WARN", where, f"task {short(tc)} has no role axioms (isTaskOf) -- the grammar cannot check its designators")
            return
        self.used[("type", name)] += 1
        row = self.gram[t]
        for clause in f[2:]:
            if not isinstance(clause, list) or not clause:
                continue
            if clause[0] == ":specializes":
                for p in clause[1:]:
                    pc = self.term("type", p, rep, where)
                    if pc is not None and not self.o.is_a(t, pc):
                        rep.add("META", where, f"library says '{name}' specializes '{p}', the ontology does not entail "
                                               f"{short(t)} SubClassOf {short(pc)}")
            elif clause[0] == ":roles":
                keys = []
                for r in clause[1:]:
                    if isinstance(r, list) and r:
                        keys.append(r[0])
                        if r[0] not in row["admissible"]:
                            rep.add("ERROR", where, f"role '{r[0]}' is not admissible for {short(t)} "
                                                    f"(admits {', '.join(row['admissible'])})")
                        for v in r[1:]:
                            self.walk([v], rep, where)
                for q in row["required"]:
                    if q not in keys:
                        rep.add("META", where, f"ontology requires role '{q}' for {short(t)}; the schema has no slot for it")
            else:
                self.walk(clause[1:], rep, where)

    def plan_schema(self, f, rep, where):
        if len(f) > 2 and isinstance(f[2], list):
            for p in f[2]:
                if isinstance(p, list) and len(p) == 2:
                    self.term("type", p[1], rep, where)
        self.walk(f[3:], rep, where)

    def lattice(self, f, rep, where):
        for e in f[2:]:
            if not isinstance(e, list) or not e:
                continue
            t = self.term("type", e[0], rep, where)
            if t is None:
                continue
            for c in e[1:]:
                if isinstance(c, list) and c and c[0] == ":specializes":
                    for p in c[1:]:
                        pc = self.term("type", p, rep, where)
                        if pc is not None and not self.o.is_a(t, pc):
                            rep.add("META", where, f"lattice: '{e[0]}' specializes '{p}' but the ontology does not entail it")
                if isinstance(c, list) and c and c[0] == ":sub":
                    onto_sub = {local(x) for x in self.o.g.objects(t, CCRAM.hasSubTask)}
                    for s in c[1:]:
                        sc = self.term("type", s, rep, where)
                        if sc is not None and local(sc) not in onto_sub:
                            rep.add("META", where, f"lattice: sub-task '{s}' of '{e[0]}' is not recorded in the ontology")

    def walk(self, xs, rep, where, cond=False):
        for x in xs:
            if not isinstance(x, list) or not x:
                continue
            h = x[0]
            if isinstance(h, list):
                self.walk(x, rep, where, cond=cond)
                continue
            if h in ("each", "every") and len(x) > 3 and VAR.match(str(x[1])):   # D10 quantified goal
                if self.is_designator(x[2]):
                    self.designator(x[2], rep, where)
                self.walk(x[3:], rep, where, cond=cond)
            elif self.is_designator(x):
                self.designator(x, rep, where)
            elif h == "perform":
                d = x[1] if len(x) > 1 else None
                if not (self.is_designator(d) and d[1] == "action"):
                    rep.add("ERROR", where, "perform needs an action designator")
                else:
                    self.designator(d, rep, where)
            elif h in COND_KEYS:
                self.walk(x[1:], rep, where, cond=True)
            elif h in self.lex.construct or h in ("type",):
                self.walk(x[1:], rep, where, cond=cond)
            elif cond and isinstance(h, str) and not VAR.match(h) and not h.startswith(":") and h not in COMPARATORS:
                if self.lex.resolve("rel", h) or self.lex.resolve("type", h):
                    self.used[("rel", h)] += 1
                else:
                    self.unresolved_pred[h] += 1
                self.walk(x[1:], rep, where, cond=True)
            else:
                self.walk(x[1:], rep, where, cond=cond)

    def designator(self, d, rep, where):
        det, noun, rest = d[0], d[1], d[2:]
        if det == "its":
            if not self.lex.resolve("role", noun):
                rep.add("ERROR", where, f"(its {noun}): '{noun}' is not a role keyword")
            return
        if noun == "action":
            tkw = next((c[1] for c in rest if isinstance(c, list) and c and c[0] == "type"), None)
            t = self.task_by_kw.get(tkw)
            if t is None:
                tc = self.term("type", tkw, rep, where) if tkw else None
                if tc is not None and not self.o.is_a(tc, DUL.Task):
                    rep.add("ERROR", where, f"action type '{tkw}' is {short(tc)}, not a task")
                elif tc is not None:
                    rep.add("WARN", where, f"action type '{tkw}' has no role axioms")
                return
            self.used[("type", tkw)] += 1
            row = self.gram[t]
            keys = []
            for c in rest:
                if not isinstance(c, list) or not c or c[0] == "type":
                    continue
                keys.append(c[0])
                if not self.lex.resolve("role", c[0]):
                    self.term("role", c[0], rep, where)
                elif c[0] not in row["admissible"]:
                    rep.add("ERROR", where, f"(an action (type {tkw}) ({c[0]} ..)): role not admissible "
                                            f"(admits {', '.join(row['admissible'])})")
                else:
                    self.used[("role", c[0])] += 1
                self.walk(c[1:], rep, where)
            miss = [q for q in row["required"] if q not in keys]
            if miss:
                rep.add("INFO", where, f"(type {tkw}): required role(s) {', '.join(miss)} left to the climb")
            return
        if noun in self.lex.head:
            pass
        elif isinstance(noun, str):
            self.term("type", noun, rep, where)
        for c in rest:
            if not isinstance(c, list) or not c:
                continue
            if c[0] == "type":
                self.term("type", c[1], rep, where)
            elif c[0] == ":tag":
                continue
            else:
                if not self.lex.resolve("rel", c[0]):
                    self.term("rel", c[0], rep, where)
                else:
                    self.used[("rel", c[0])] += 1
                self.walk(c[1:], rep, where)


# ---------------------------------------------------------------------------------------------------- DL translation
def to_dl(d, lex, gram=None, tags=None):
    """Designator -> DL class expression (Manchester-like string).
    a/an/some -> concept; the/tagged -> nominal {individual}; its -> belonging place."""
    if isinstance(d, str):
        if VAR.match(d):
            return f"{{{d}}}"
        return f"{{{d}}}"
    if not isinstance(d, list) or not d:
        return "Thing"
    if d[0] == "tagged":
        return "{" + "/".join(reversed([str(x) for x in d[1:]])) + "}"
    if d[0] == "its":
        r = lex.resolve("role", d[1])
        return f"(PhysicalPlace and isBelongingPlaceOf value <object>)  # its {d[1]} ({short(r[0]) if r else '?'})"
    det, noun, rest = d[0], d[1], d[2:]
    parts = []
    if noun == "action":
        parts.append("dul:Action")
        for c in rest:
            if c[0] == "type":
                t = lex.resolve("type", c[1])
                parts.append(f"(dul:executesTask some {short(t[0]) if t else '?' + c[1]})")
            else:
                r = lex.resolve("role", c[0])
                filler = to_dl(c[1], lex) if len(c) > 1 else "Thing"
                parts.append(f"(dul:hasParticipant some ({filler} and (dul:isClassifiedBy some "
                             f"{short(r[0]) if r else '?' + c[0]})))")
    else:
        base = lex.head.get(noun)
        if base is not None:
            k = next((c[1] for c in rest if isinstance(c, list) and c and c[0] == "type"), None)
            t = lex.resolve("type", k) if k else []
            parts.append(short(t[0]) if t else "dul:PhysicalObject")
        else:
            t = lex.resolve("type", noun)
            parts.append(short(t[0]) if t else f"?{noun}")
        for c in rest:
            if not isinstance(c, list) or not c or c[0] == "type":
                continue
            if c[0] in (":tag", "tag"):
                return "{" + str(c[1]) + "}"
            p = lex.resolve("rel", c[0])
            v = c[1] if len(c) > 1 else None
            pv = to_dl(v, lex) if isinstance(v, list) else (f"{{{v}}}" if isinstance(v, str) and VAR.match(v) else json.dumps(v))
            parts.append(f"({short(p[0]) if p else '?' + c[0]} some {pv})" if isinstance(v, list) or VAR.match(str(v))
                         else f"({short(p[0]) if p else '?' + c[0]} value {pv})")
    expr = " and ".join(parts)
    return expr if det in ("a", "an", "some", "each", "every") else f"the-one({expr})"


# ---------------------------------------------------------------------------------------------------- CLI
def main(argv):
    onto = Ontology()
    lex = Lexicon(onto)
    cmd = argv[0] if argv else "lexicon"
    if cmd == "lexicon":
        print(f"ontology: {len(onto.classes)} classes, {len(onto.props)} properties")
        print(f"lexicon: {len(lex.type)} type, {len(lex.role)} role, {len(lex.rel)} relation keywords, "
              f"{len(lex.construct)} constructs, {len(lex.head)} designator kinds")
        print(f"collisions ({len(lex.collisions)}):")
        for c in lex.collisions:
            print("  ", c)
    elif cmd == "grammar":
        rows = grammar(onto, lex)
        out = ["# Action designator grammar (generated from the ontology -- do not edit)", "",
               "Generated by `tools/ccram_lang.py grammar` from DUL + SOMA + ccram-lang + ccram-actions + booth. "
               "Required roles: `Task SubClassOf isTaskOf some R`; admissible roles: `Task SubClassOf isTaskOf only (...)`.",
               "", "| keyword | task | specializes | required roles | admissible roles | sub-tasks | telos |",
               "|---|---|---|---|---|---|---|"]
        for t, r in sorted(rows.items(), key=lambda kv: kv[1]["keyword"]):
            out.append(f"| `{r['keyword']}` | {short(t)} | {', '.join(r['parents'])} | {', '.join(r['required'])} | "
                       f"{', '.join(r['admissible'])} | {', '.join(r['subtasks'])} | {', '.join(r['telos'])} |")
        open(os.path.join(ONTO, "grammar.md"), "w").write("\n".join(out) + "\n")
        print("\n".join(out))
    elif cmd == "lint":
        lin = Linter(onto, lex)
        tot = collections.Counter()
        for path in argv[1:]:
            rep = lin.lint_text(open(path).read(), os.path.basename(path))
            for lvl, where, msg in rep.items:
                print(f"{lvl:5s} {where}: {msg}")
            tot.update(rep.counts())
        used = collections.Counter(p for p, _ in lin.used)
        print(f"\nsummary: {dict(tot)}; resolved keyword uses by position: {dict(used)}")
        print(f"condition predicates not (yet) in the ontology ({len(lin.unresolved_pred)}): "
              f"{', '.join(k for k, _ in lin.unresolved_pred.most_common())}")
    elif cmd == "dl":
        for s in argv[1:]:
            print(to_dl(parse(s)[0], lex))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
