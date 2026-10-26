"""Reasoning over the language's meaning (D9): the booth tree as an ABox, designators as individuals / class
expressions, HermiT (full OWL 2 DL) classifies.

  1. attributive designators by instance retrieval: (a graspable), (a container) -- answered from axioms
     (dispositions of the booth classes), not from lists in code
  2. a candidate action from its designator, classified against the floss machine's closing event:
     (an action (type pouring-into) (destination (tagged spinner-head machine))) is a ccram:ProhibitedAction
     exactly when the machine's device state lies in a turned-on region (modes spinning .. running-empty)

    .venv_onto/bin/python tools/ccram_reason.py            -> ontology/reasoning_demo.json
Open world: "not classified prohibited" means "not provably prohibited", not "provably safe" (that needs the closed
machine state, e.g. a functional hasRegion plus disjoint regions, which the module provides for on/off).
"""
import json
import os
import sys
import tempfile
import time

import rdflib
from rdflib.namespace import OWL, RDF

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ccram_lang as CL  # noqa: E402

CC = rdflib.Namespace("https://aicor.knowledge/cotton-candy#")
IND = rdflib.Namespace("https://aicor.knowledge/cotton-candy/booth/")


def booth_abox(g, lex, forms):
    """Individuals for the tagged booth tree: type from is-a, dul:isPartOf from the tree."""
    tt = CL.parse  # noqa: F841
    names = {}

    def walk(f, parent_path):
        if not (isinstance(f, list) and len(f) == 3 and f[0] == ":tag"):
            return
        path = parent_path + [f[1]]
        iri = IND["/".join(path)]
        names["/".join(path)] = iri
        g.add((iri, RDF.type, OWL.NamedIndividual))
        node = f[2]
        for sub in node[1:] if isinstance(node, list) and node and node[0] == "node" else []:
            if isinstance(sub, list) and sub and sub[0] == "is-a":
                t = lex.resolve("type", sub[1])
                if t:
                    g.add((iri, RDF.type, t[0]))
            if isinstance(sub, list) and sub and sub[0] == "parts":
                for p in sub[1:]:
                    walk(p, path)
                    if isinstance(p, list) and len(p) == 3:
                        g.add((IND["/".join(path + [p[1]])], CL.DUL.isPartOf, iri))
    for f in forms:
        walk(f, [])
    return names


def scenario(base, lex, forms, mode_cls):
    g = rdflib.Graph()
    for t in base:
        g.add(t)
    names = booth_abox(g, lex, forms)
    m = names["booth/machine"]
    q, r = IND["booth/machine/device-state"], IND["booth/machine/mode"]
    g.add((q, RDF.type, CL.SOMA.DeviceState))
    g.add((m, CL.DUL.hasQuality, q))
    g.add((q, CL.DUL.hasRegion, r))
    g.add((r, RDF.type, mode_cls))
    # the candidate action, from its designator (D9 reading): Action, executes a PouringInto task, the spinner head
    # participates classified as Destination
    d = CL.parse("(an action (type pouring-into) (object (the sugar-carton)) (destination (tagged spinner-head machine)))")[0]
    act, task, dest = IND["candidate/pour-1"], IND["candidate/pour-1/task"], IND["candidate/pour-1/destination-role"]
    g.add((act, RDF.type, CL.DUL.Action))
    g.add((task, RDF.type, lex.resolve("type", "pouring-into")[0]))
    g.add((act, CL.DUL.executesTask, task))
    head = names["booth/machine/spinner-head"]
    g.add((act, CL.DUL.hasParticipant, head))
    g.add((dest, RDF.type, lex.resolve("role", "destination")[0]))
    g.add((head, CL.DUL.isClassifiedBy, dest))
    return g, names, CL.to_dl(d, lex)


def extract_module(g, seeds):
    """Upward module: every axiom (subject-centred triples, with their blank-node structure) about a seed term,
    closed over the named terms those axioms mention. Annotations are left out. Full DUL + SOMA realization does not
    finish in 40 min with HermiT; the booth questions only need the terms reachable from the booth and ccram modules.
    Approximation: axioms in which a seed occurs only on the right-hand side of another term's axiom are kept only if
    that term is itself reachable."""
    keep_p = {RDF.type, rdflib.RDFS.subClassOf, OWL.equivalentClass, rdflib.RDFS.subPropertyOf, OWL.inverseOf,
              rdflib.RDFS.domain, rdflib.RDFS.range, OWL.disjointWith, OWL.propertyChainAxiom, OWL.onProperty,
              OWL.someValuesFrom, OWL.allValuesFrom, OWL.hasValue, OWL.intersectionOf, OWL.unionOf,
              OWL.complementOf, OWL.oneOf, RDF.first, RDF.rest, OWL.minQualifiedCardinality,
              OWL.maxQualifiedCardinality, OWL.qualifiedCardinality, OWL.onClass, OWL.minCardinality,
              OWL.maxCardinality, OWL.cardinality, OWL.onDataRange}
    m = rdflib.Graph()
    done, todo = set(), list(seeds)
    while todo:
        t = todo.pop()
        if t in done:
            continue
        done.add(t)
        stack = [t]
        while stack:
            s_ = stack.pop()
            for p_, o in g.predicate_objects(s_):
                if p_ not in keep_p:
                    continue
                m.add((s_, p_, o))
                if isinstance(o, rdflib.BNode):
                    stack.append(o)
                elif isinstance(o, rdflib.URIRef) and o not in done and not str(o).startswith(str(OWL)) and \
                        not str(o).startswith(str(RDF)) and not str(o).startswith("http://www.w3.org/2001/XMLSchema"):
                    todo.append(o)
    return m, len(done)


DROPPED = []          # axioms removed so that HermiT accepts the stack (OWL 2 DL global restrictions), reported


def reason(g):
    """HermiT over the merged graph. SOMA violates OWL 2 DL global restrictions (non-simple properties declared
    asymmetric / irreflexive / used in cardinalities); each offending characteristic is removed, logged in DROPPED and
    the reasoner rerun."""
    import re as _re
    import owlready2 as O
    for s, p, o in list(g.triples((None, OWL.imports, None))):          # everything is merged: no web imports
        g.remove((s, p, o))
    for _ in range(40):
        tmp = tempfile.NamedTemporaryFile(suffix=".owl", delete=False)
        g.serialize(tmp.name, format="xml")
        world = O.World()
        onto = world.get_ontology("file://" + tmp.name).load()
        t0 = time.time()
        try:
            with onto:
                O.sync_reasoner_hermit([onto], infer_property_values=False, debug=0)
            return world, time.time() - t0
        except O.OwlReadyJavaError as e:
            m = _re.search(r"Non-simple property '<([^>]+)>' or its inverse appears in (\w+)", str(e))
            if not m:
                raise
            prop, where = rdflib.URIRef(m.group(1)), m.group(2)
            kinds = {"asymmetric": OWL.AsymmetricProperty, "irreflexive": OWL.IrreflexiveProperty}
            k = next((v for key, v in kinds.items() if key in str(e)), None)
            if k is not None and (prop, RDF.type, k) in g:
                g.remove((prop, RDF.type, k))
                DROPPED.append(f"{CL.short(prop)} {CL.local(k)}")
                continue
            raise
    raise RuntimeError("too many DL violations")


def instances(world, iri):
    c = world[str(iri)]
    return sorted(str(i.iri).split("booth/")[-1] for i in c.instances()) if c is not None else []


def main():
    onto = CL.Ontology()
    lex = CL.Lexicon(onto)
    forms = CL.parse(open(os.path.join(CL.HERE, "booth.lisp")).read())
    full = CL.load_graph(usd=False)                      # USD module out: undefined custom datatypes (see load_graph)
    mods = rdflib.Graph()
    for mname in CL.MODULES:
        mods.parse(os.path.join(CL.ONTO, mname), format="turtle")
    seeds = {t for t in set(mods.subjects()) | set(mods.objects()) if isinstance(t, rdflib.URIRef)}
    seeds |= {CL.DUL.Action, CL.DUL.executesTask, CL.DUL.hasParticipant, CL.DUL.isClassifiedBy, CL.DUL.isPartOf,
              CL.DUL.hasQuality, CL.DUL.hasRegion, CL.SOMA.DeviceState}
    for mname in CL.MODULES:                                # the modules' own axioms in full (annotations included)
        pass
    module, n_terms = extract_module(full, seeds)
    for t in mods:
        module.add(t)
    print(f"module: {len(module)} triples over {n_terms} terms (full stack {len(full)} triples)")
    base = list(module)
    out = {}
    for label, mode in (("producing", CC.Producing), ("off", CC.Off)):
        g, names, dl = scenario(base, lex, forms, mode)
        world, dt = reason(g)
        act = world[str(IND["candidate/pour-1"])]
        cls = sorted(str(c.iri).split("#")[-1] for c in act.INDIRECT_is_a if hasattr(c, "iri"))
        out[label] = dict(
            mode=CL.short(mode), hermit_s=round(dt, 1), designator_dl=dl,
            candidate_classified_as=cls,
            prohibited="ProhibitedAction" in cls,
            running_machine=instances(world, CC.RunningMachine),
            graspable=instances(world, CL.CCRAM.Graspable),
            container=instances(world, CL.CCRAM.ContainerObject),
            customer_defined=str(CC.Customer))
        print("dropped so far:", sorted(set(DROPPED)))
        print(label, json.dumps({k: v for k, v in out[label].items() if k != "designator_dl"}, indent=1))
    out["designator"] = "(an action (type pouring-into) (object (the sugar-carton)) (destination (tagged spinner-head machine)))"
    out["designator_dl"] = out["producing"]["designator_dl"]
    out["dropped_for_dl"] = sorted(set(DROPPED))
    out["module_triples"] = len(base)
    out["note"] = ("HermiT over the upward module of the booth + ccram terms in DUL + SOMA (no USD) + booth ABox; open world: 'not prohibited' = not provably "
                   "prohibited")
    json.dump(out, open(os.path.join(CL.ONTO, "reasoning_demo.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
