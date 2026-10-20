"""Load the generated cotton candy production ontology (OWL functional syntax, the axiom forms that
cram/cotton_candy/ontology/owl.py writes) into owlready2 and check it with HermiT: consistency and inferred types.

Run: ~/Documents/LabAutomationTwin/env_cad/bin/python ontology/reason.py   (exit 1 if inconsistent or unparsed axioms)
"""

import os
import re
import sys
import types

import owlready2 as o

HERE = os.path.dirname(os.path.abspath(__file__))
OFN = os.path.join(HERE, "build", "cotton_candy_production.ofn")
OWL = os.path.join(HERE, "build", "cotton_candy_production.owl")


def main():
    onto = o.get_ontology("https://aicor.ai/twins/cotton-candy")
    lines = [l.strip() for l in open(OFN) if l.strip().startswith(("Declaration", "SubClassOf", "ClassAssertion",
                                                                     "ObjectProperty", "DataProperty", "Transitive",
                                                                     "AnnotationAssertion"))]
    name = lambda t: t[1:] if t.startswith(":") else t
    classes, objprops, dataprops, inds, skipped = {}, {}, {}, {}, []
    with onto:
        for l in lines:
            m = re.match(r"Declaration\((Class|ObjectProperty|DataProperty|NamedIndividual)\((:\S+)\)\)", l)
            if m:
                kind, n = m.group(1), name(m.group(2))
                if kind == "Class":
                    classes[n] = types.new_class(n, (o.Thing,))
                elif kind == "ObjectProperty":
                    objprops[n] = types.new_class(n, (o.ObjectProperty,))
                elif kind == "DataProperty":
                    dataprops[n] = types.new_class(n, (o.DataProperty,))
                continue
        for l in lines:   # individuals before any assertion that links them
            if m := re.match(r"ClassAssertion\((:\S+) (:\S+)\)", l):
                c, i = name(m.group(1)), name(m.group(2))
                inds[i] = inds.get(i) or classes[c](i)
                if not isinstance(inds[i], classes[c]):
                    inds[i].is_a.append(classes[c])
        for l in lines:
            if l.startswith("Declaration"):
                continue
            if m := re.match(r"SubClassOf\((:\S+) (:\S+)\)", l):
                a, b = classes[name(m.group(1))], classes[name(m.group(2))]
                if o.Thing in a.is_a:
                    a.is_a.remove(o.Thing)
                a.is_a.append(b)
            elif l.startswith("ClassAssertion"):
                pass
            elif m := re.match(r"Object(PropertyDomain|PropertyRange)\((:\S+) (:\S+)\)", l):
                p, c = objprops[name(m.group(2))], classes[name(m.group(3))]
                (p.domain if m.group(1) == "PropertyDomain" else p.range).append(c)
            elif m := re.match(r"TransitiveObjectProperty\((:\S+)\)", l):
                objprops[name(m.group(1))].is_a.append(o.TransitiveProperty)
            elif m := re.match(r"ObjectPropertyAssertion\((:\S+) (:\S+) (:\S+)\)", l):
                getattr(inds[name(m.group(2))], name(m.group(1))).append(inds[name(m.group(3))])
            elif m := re.match(r'DataPropertyAssertion\((:\S+) (:\S+) "(.*)"(\^\^xsd:(\w+))?\)$', l):
                value, typ = m.group(3), m.group(5)
                value = value == "true" if typ == "boolean" else float(value) if typ == "decimal" else value
                getattr(inds[name(m.group(2))], name(m.group(1))).append(value)
            elif l.startswith("AnnotationAssertion"):
                pass
            else:
                skipped.append(l)
    onto.save(file=OWL, format="rdfxml")
    print(f"loaded {len(classes)} classes, {len(objprops)} object / {len(dataprops)} data properties, "
          f"{len(inds)} individuals; unparsed axioms: {len(skipped)}")
    for l in skipped[:5]:
        print("  unparsed:", l[:120])
    with onto:
        o.sync_reasoner(infer_property_values=True, debug=0)
    inconsistent = list(o.default_world.inconsistent_classes())
    print("HermiT: consistent;", "unsatisfiable classes:", [c.name for c in inconsistent] or "none")
    step = onto.search_one(iri="*step_Start_the_machine")
    print("example: step 'Start the machine' categories:", [c.name for c in step.hasCategory],
          "| inferred types:", sorted(c.name for c in step.INDIRECT_is_a if hasattr(c, "name"))[:6])
    sys.exit(1 if skipped or inconsistent else 0)


if __name__ == "__main__":
    try:
        main()
    except o.OwlReadyInconsistentOntologyError as error:
        print("HermiT: INCONSISTENT", error)
        sys.exit(1)
