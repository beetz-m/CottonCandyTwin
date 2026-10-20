"""Generate the Cotton Candy Booth Twin report (LaTeX -> PDF) from the repository.

Generated: never edit report/cotton_candy_twin.tex by hand - edit this script. Every number comes from the register
(site/params.py), the layout (site/layout.py), result JSON with provenance (data/*.json, refused when stale), the
CRAM test report (test_reports/cram_pytest.xml), the ontology reasoning log and the renders.

Run: ~/Documents/LabAutomationTwin/env_cad/bin/python report/build_report.py   (exit 1 on a missing figure or stale data)
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "report", "cotton_candy_twin.tex")
R = lambda *p: os.path.join(ROOT, *p)  # noqa: E731
WARNINGS = []


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, R("site"))
PR = load_module("params", R("site", "params.py"))
LY = load_module("layout", R("site", "layout.py"))
PV = load_module("provenance", R("site", "provenance.py"))


# %% LaTeX helpers (after CuxhavenSiteTwin/report/build_report.py)


def esc(s):
    s = (str(s).replace("\\", r"\textbackslash{}").replace("_", r"\_").replace("&", r"\&").replace("%", r"\%")
         .replace("#", r"\#").replace("$", r"\$").replace("{", r"\{").replace("}", r"\}")
         .replace("~", r"\textasciitilde{}").replace("^", r"\^{}"))
    return s.replace("->", r"$\to$").replace(">=", r"$\geq$").replace("<=", r"$\leq$")


def tt(s):
    return r"\texttt{" + esc(s) + "}"


def fig(path, caption, height=r"0.42\textheight", pos="htbp"):
    if not os.path.exists(R(path)):
        WARNINGS.append(f"missing figure {path}")
        return f"% missing figure {path}\n"
    return (f"\\begin{{figure}}[{pos}]\\centering\\includegraphics[width=\\linewidth,height={height},keepaspectratio]"
            f"{{{R(path)}}}\\caption{{{caption}}}\\end{{figure}}\n")


def figrow(items, caption, height=r"0.22\textheight"):
    for p, _ in items:
        if not os.path.exists(R(p)):
            WARNINGS.append(f"missing figure {p}")
    items = [(p, s) for p, s in items if os.path.exists(R(p))]
    if not items:
        return ""
    w = f"{0.98 / len(items) - 0.01:.3f}\\linewidth"
    cells = [f"\\begin{{minipage}}[t]{{{w}}}\\centering\\includegraphics[width=\\linewidth,height={height},"
             f"keepaspectratio]{{{R(p)}}}\\\\[-1pt]{{\\scriptsize {sub}}}\\end{{minipage}}" for p, sub in items]
    return "\\begin{figure}[htbp]\\centering" + "\\hfill".join(cells) + f"\\caption{{{caption}}}\\end{{figure}}\n"


def table(cols, head, rows, caption, size="footnotesize", long=False):
    """``rows`` are already-escaped LaTeX cells."""
    body = " \\\\\n".join(" & ".join(str(c) for c in r) for r in rows)
    head = " & ".join(r"\textbf{" + h + "}" for h in head)
    if long:   # longtable has no X columns: give them the width the fixed columns leave
        fixed = sum(float(m) for m in re.findall(r"\{([0-9.]+)\\linewidth\}", "".join(cols)))
        n_x = cols.count("X")
        width = max(0.18, (0.97 - fixed - 0.06 * sum(c in "lrc" for c in cols)) / max(n_x, 1))
        cols = [c if c != "X" else f"L{{{width:.2f}\\linewidth}}" for c in cols]
        return (f"{{\\{size}\\begin{{longtable}}{{@{{}}{''.join(cols)}@{{}}}}\\caption{{{caption}}}\\\\\\toprule "
                f"{head} \\\\\\midrule\\endfirsthead\\toprule {head} \\\\\\midrule\\endhead\n{body} \\\\\\bottomrule"
                f"\\end{{longtable}}}}\n")
    return (f"\\begin{{table}}[htbp]\\centering\\{size}\\caption{{{caption}}}\n\\begin{{tabularx}}{{\\linewidth}}"
            f"{{@{{}}{''.join(cols)}@{{}}}}\\toprule {head} \\\\\\midrule\n{body} \\\\\\bottomrule"
            f"\\end{{tabularx}}\\end{{table}}\n")


def code(text, title=None):
    t = f"\\noindent{{\\small\\sffamily\\bfseries {esc(title)}}}\\par\\vspace{{2pt}}" if title else ""
    return (t + "\\begin{Verbatim}[fontsize=\\scriptsize,frame=lines,framesep=2mm,breaklines]\n" + text.rstrip()
            + "\n\\end{Verbatim}\n")


def bullets(items):
    return "\\begin{itemize}\n" + "\n".join(f"\\item {i}" for i in items) + "\n\\end{itemize}\n"


def md_inline(s):
    """Markdown cell -> LaTeX: escape, then `code` and **bold**."""
    parts = re.split(r"(`[^`]+`)", s.strip())
    out = []
    for p in parts:
        if p.startswith("`") and p.endswith("`"):
            out.append(tt(p[1:-1]))
        else:
            out.append(re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", esc(p)))
    return "".join(out)


def md_tables(path):
    """All pipe tables of a Markdown file: [(header, rows)]."""
    tables, cur = [], None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cur is None:
                cur = (cells, [])
            elif not all(re.fullmatch(r":?-+:?", c) for c in cells):
                cur[1].append(cells)
        elif cur is not None:
            tables.append(cur)
            cur = None
    if cur is not None:
        tables.append(cur)
    return tables


def fmt(v, unit=""):
    if v is None:
        return "--"
    if isinstance(v, float):
        v = f"{v:.4g}"
    if isinstance(v, (list, tuple)):
        v = " x ".join(f"{x:.4g}" if isinstance(x, float) else str(x) for x in v)
    return f"{v} {unit}".strip() if unit not in ("-", "") else str(v)


def pct(part, whole):
    return f"{100 * part / whole:.0f}\\,\\%" if whole else "--"


# %% inputs


def register_sections():
    """key -> section name, from the ``# ---- name`` headers inside the register dict."""
    sections, current, inside = {}, "other", False
    for line in open(R("site", "params.py"), encoding="utf-8"):
        if line.startswith("P = {"):
            inside = True
            continue
        if not inside:
            continue
        if m := re.match(r"\s+# -{8,} (.+)$", line):
            current = m.group(1).strip()
        elif m := re.match(r'\s+"(\w+)":\s*\(', line):
            sections[m.group(1)] = current
        if line.startswith("}"):
            break
    missing = [k for k in PR.P if k not in sections]
    if missing:
        raise SystemExit(f"register keys without a section: {missing}")
    return sections


def junit():
    path = R("test_reports", "cram_pytest.xml")
    if not os.path.exists(path):
        raise SystemExit("test_reports/cram_pytest.xml missing - run the CRAM tests (tools/build_all.sh)")
    root = ET.parse(path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    per_file = OrderedDict()
    for case in suite.iter("testcase"):
        f = case.get("classname", "").split(".")[-1] or "?"
        ok = case.find("failure") is None and case.find("error") is None and case.find("skipped") is None
        per_file.setdefault(f, [0, 0])
        per_file[f][0] += ok
        per_file[f][1] += 1
    total = int(suite.get("tests")); bad = int(suite.get("failures")) + int(suite.get("errors"))
    return {"total": total, "passed": total - bad - int(suite.get("skipped", 0)), "failed": bad,
            "time": float(suite.get("time")), "stamp": suite.get("timestamp", ""), "per_file": per_file,
            "fresh": os.path.getmtime(path)}


def stage_stats():
    try:
        from pxr import Usd, UsdGeom
    except ImportError:
        return None
    path = R("scenes", "cotton_candy_booth.usda")
    if not os.path.exists(path):
        return None
    st = Usd.Stage.Open(path)
    n = meshes = tris = 0
    sdt, example = [], None
    for p in Usd.PrimRange.Stage(st, Usd.TraverseInstanceProxies()):
        n += 1
        if p.IsA(UsdGeom.Mesh):
            meshes += 1
            c = UsdGeom.Mesh(p).GetFaceVertexCountsAttr().Get()
            tris += len(c) if c is not None else 0
        names = [a.GetName() for a in p.GetAttributes()]
        if any(a.startswith("sdt:") for a in names):
            sdt.append(p)
            if example is None and "FlossMachine" in p.GetName() or (example is None and "Machine" in p.GetName()
                                                                     and any(a.startswith("state:") for a in names)):
                example = p
    example = example or (sdt[0] if sdt else None)
    lines = []
    if example is not None:
        lines.append(f'def Xform "{example.GetName()}"   # {example.GetPath()}')
        for a in example.GetAttributes():
            if a.GetName().startswith(("sdt:", "state:")):
                v = a.Get()
                lines.append(f"    {a.GetTypeName()} {a.GetName()} = {v!r}"[:150])
    return dict(prims=n, meshes=meshes, tris=tris, sdt=len(sdt), example="\n".join(lines[:22]))


def lisp_excerpt():
    text = open(R("cram", "plans", "make-and-hand-over.lisp"), encoding="utf-8").read()
    designators = text[text.index("(def-entity-designator the-candy"):text.index("(def-entity-designator the-ingredients-of")]
    row = text[text.index("  (2 stick-in-hand"):text.index("  (3 candy-formed")]
    loop = text[text.index("(def-top-level-cram-function"):text.index(";;; Traces")].rstrip().rstrip(";-").rstrip()
    return designators.rstrip(), row.rstrip(), loop


# English glosses of the competency questions (the questions themselves are asked in German, as operators would).
CQ_EN = [
    "Which steps does a shift have, in which order, and who performs them?",
    "What must hold before sugar may be filled into the spinner head?",
    "Which steps contain Pressing Button?",
    "Which manipulation categories make up starting the machine?",
    "Which categories come from the CRAM L2 module, which are newly proposed?",
    "Which parts does starting the machine act on?",
    "Which semantic annotation stands for which ontology individual?",
    "Which parts belong to the floss machine?",
    "Which ingredients require a warning label, and what is their E number?",
    "Which allergens does the pink cotton candy contain?",
    "Which hazards exist, where do they come from, what mitigates them?",
    "Which regulation is satisfied by which object in the booth?",
    "Which values are only ILLUSTRATIVE (assumptions of this reconstruction)?",
    "At which humidity does cotton candy collapse, and how certain is that?",
    "Which combustible objects are currently nearer than 0.6 m to the heating band?",
    "How far is the cotton candy I am making, and what is it for?",
    "Which cotton candies have been handed over, and to whom?",
    "Which phase is the machine in, how much sugar is in the head, how many portions?",
]


# %% the document


def main():
    reg, sources = PR.P, PR.SOURCES
    cnt = PR.status_counts()
    n_reg = len(reg)
    sections = register_sections()
    checks = PV.load_fresh("checks")
    envelopes = PV.load_fresh("asset_envelopes")
    robot = PV.load_fresh("robot_envelope")
    cram = PV.load_fresh("cram_results")
    tests = junit()
    stage = stage_stats()
    reasoning = open(R("data", "ontology_reasoning.txt"), encoding="utf-8").read().strip().splitlines()
    git = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    g = PR.get
    n_checks, n_failed = len(checks["results"]), len(checks["failed"])
    if len(cram["questions"]) != len(CQ_EN):
        raise SystemExit("competency questions changed - update CQ_EN in report/build_report.py")
    m_reason = re.search(r"loaded (\d+) classes, (\d+) object / (\d+) data properties, (\d+) individuals", reasoning[0])
    consistent = any("HermiT: consistent" in l for l in reasoning)
    out = []
    w = out.append

    # ---------------------------------------------------------------- preamble and title page
    w(r"""\documentclass[10.5pt,a4paper]{article}
\usepackage[margin=2.2cm,headheight=14pt]{geometry}
\usepackage{fontspec,unicode-math}
\setmainfont{Libertinus Serif}\setsansfont{IBM Plex Sans}\setmonofont[Scale=0.84]{IBM Plex Mono}\setmathfont{Libertinus Math}
\usepackage{microtype,graphicx,booktabs,tabularx,longtable,xcolor,fvextra,caption,fancyhdr,titlesec,enumitem,array}
\usepackage[section]{placeins}
\usepackage{xurl}
\usepackage[colorlinks,linkcolor=magenta!55!black,urlcolor=magenta!55!black,citecolor=magenta!55!black]{hyperref}
\captionsetup{font=small,labelfont=bf}
\renewcommand{\tabularxcolumn}[1]{>{\raggedright\arraybackslash}p{#1}}
\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}
\setlength{\emergencystretch}{3em}\setlist{itemsep=2pt,topsep=3pt}
\titleformat{\section}{\sffamily\Large\bfseries\color{magenta!50!black}}{\thesection}{0.8em}{}
\titleformat{\subsection}{\sffamily\large\bfseries}{\thesubsection}{0.7em}{}
\titleformat{\paragraph}[runin]{\sffamily\bfseries}{}{}{}[.]
\pagestyle{fancy}\fancyhf{}\fancyhead[L]{\sffamily\footnotesize Cotton candy booth: a semantic digital twin with a robot operator}
\fancyhead[R]{\sffamily\footnotesize\nouppercase{\leftmark}}\fancyfoot[C]{\sffamily\footnotesize\thepage}
\renewcommand{\headrulewidth}{0.3pt}
\renewcommand{\floatpagefraction}{0.7}\renewcommand{\topfraction}{0.9}\renewcommand{\textfraction}{0.1}
\begin{document}
\begin{titlepage}\sffamily
""")
    hero = "renders/booth/establishing.png"
    if os.path.exists(R(hero)):
        w(f"\\noindent\\includegraphics[width=\\linewidth,height=0.42\\textheight,keepaspectratio]{{{R(hero)}}}\\par\\vspace{{0.8cm}}\n")
    else:
        WARNINGS.append(f"missing figure {hero}")
    w(r"""{\color{magenta!50!black}\rule{\linewidth}{1.2pt}}\par\vspace{0.4cm}
{\Huge\bfseries A cotton candy booth that a robot can run\par}\vspace{0.3cm}
{\Large A semantic digital twin of a German fairground Zuckerwatte booth, its floss machine and ingredients,
with CRAM plans for a PR2 operator\par}\vspace{0.3cm}
{\color{magenta!50!black}\rule{\linewidth}{1.2pt}}\par\vspace{0.6cm}
""")
    w(f"{{\\normalsize CottonCandyTwin, commit {tt(git)} \\hfill 20 October 2026\\par}}\\vfill\n")
    w(r"""{\small\rmfamily This is a design study, not a real booth. The machine is reconstructed from the public manual and
data of the Gold Medal Econo Floss 3017 export model; the booth, the ingredients and the regulations come from
public sources. Every number carries a status label (Section~\ref{sec:quality}). Generated by
\texttt{report/build\_report.py}; do not edit the \texttt{.tex}.\par}
\end{titlepage}
\tableofcontents\clearpage
""")

    # ---------------------------------------------------------------- 1 summary
    sourced = cnt["SOURCED"] + cnt["STANDARD"] + cnt["SOURCED-VERIFY"]
    plan_rows = cram["plan_rows"]
    delivered = [s for s in cram["scenarios"] if s["outcome"] == "delivered"]
    w(r"\section{Summary}" "\n")
    w(f"""This twin models a fairground cotton candy booth of {fmt(g('booth_width'))} $\\times$ {fmt(g('booth_depth'))} m
with a 230~V floss machine, its sugar, sticks and ingredients, and a PR2 robot that runs the booth: it fills and
starts the machine, spins and wraps portions, hands them to the customer, shuts the machine down and cleans it.
It has four layers, each generated from the repository:
""")
    w(bullets([
        f"\\textbf{{Register and layout.}} {n_reg} parameters with a status and a source "
        f"({pct(sourced, n_reg)} sourced, standard or sourced-verify; {pct(cnt['ILLUSTRATIVE'], n_reg)} illustrative). "
        f"The layout passes {n_checks - n_failed}/{n_checks} checks: clearances, reach, ergonomics, electrical load, "
        f"regulation items and robot fit.",
        f"\\textbf{{Isaac Sim stage.}} The booth, the machine and the fairground square as a USD stage"
        + (f" ({stage['prims']} prims, {stage['sdt']} with \\texttt{{sdt:}} semantics)" if stage else "")
        + ", rendered with path tracing.",
        f"\\textbf{{CRAM robot agent.}} {len(cram['steps'])} top-level action designators for the shift, each a "
        f"composition of {cram['counts']['categories']} manipulation action categories (Transporting, Pressing Button, "
        f"Turning, Pouring, Gathering, Wrapping, Handing Over, Wiping, Monitoring). A generalized plan over entity "
        f"designators makes the candy that is ordered and hands it to its customer from any state: "
        f"{len(delivered)} of {len(cram['scenarios'])} starting states end with the candy delivered, the other "
        f"{len(cram['scenarios']) - len(delivered)} are correctly refused.",
        f"\\textbf{{Ontology.}} A production ontology generated from the scene graph and linked to its semantic "
        f"annotations ({m_reason.group(1)} classes, {m_reason.group(4)} individuals, HermiT "
        f"{'consistent' if consistent else 'INCONSISTENT'}), with {len(cram['questions'])} competency questions "
        f"answered live in the cramera viewer.",
    ]))
    w(f"All {tests['total']} CRAM tests {'pass' if tests['failed'] == 0 else 'run; ' + str(tests['failed']) + ' FAIL'}. "
      "The three main limitations (Section~\\ref{sec:limits}):\n")
    w(bullets([
        "the robot runs kinematically with collision avoidance switched off, because the PR2's collision buffers are "
        "larger than the clearances of a human-scale machine;",
        "sugar, floss and the portion are a process model (masses and phases), not particle or fibre physics;",
        "the booth had to grow from the requested 2\\,$\\times$\\,2\\,m to "
        f"{fmt(g('booth_width'))}\\,$\\times$\\,{fmt(g('booth_depth'))}\\,m for the robot to fit.",
    ]))

    # ---------------------------------------------------------------- 2 purpose
    w(r"\section{Purpose and approach}" "\n")
    w(r"""The request was a typical 2\,$\times$\,2\,m cotton candy booth from a German fair (\emph{Zuckerwattebude}),
with the details of the machine and of the ingredients. It became a manipulation scenario: a robot operator whose
plans are grounded in a semantic model of the booth. The scale is a cell: one booth, one machine, one robot.

The method follows the isaac-twin workflow:
""")
    w(bullets([
        "\\textbf{Register first.} Every number lives in \\texttt{site/params.py} with a status, a source key and a "
        "note. Builders read the register and raise on a GAP.",
        "\\textbf{One layout model.} \\texttt{site/layout.py} places everything; checks, figures, the USD stage and "
        "the CRAM world all read it.",
        "\\textbf{Measure, don't type.} The machine envelope and the PR2 envelope used by the checks are measured "
        "from the built assets (\\texttt{data/asset\\_envelopes.json}, \\texttt{data/robot\\_envelope.json}).",
        "\\textbf{Fail loud.} Checks and the report exit non-zero; every result JSON carries the git hash and input "
        "hashes, and this report refuses stale results.",
    ]))
    w(r"\paragraph{Decisions taken with the user (2026-10-20)}" "\n")
    w(bullets([
        "Enlarge the booth for the robot (\\emph{Bude vergr\\\"o\\ss{}ern}) rather than use a smaller robot.",
        "Fill the head from a sugar carton with a pour spout (\\emph{Zuckerkarton mit Ausgie\\ss{}er}), as the "
        "Flossugar half-gallon carton has.",
        "Map the top-level designators to manipulation action categories first.",
        "Build the generalized plan after Beetz's concurrent reactive plans, Schoppers' universal plans, Firby's RAPs "
        "and STRIPS triangle tables, over entity designators matched against the belief state of the candy and the booth.",
        "Open the sales flap wide enough to see into the booth.",
    ]))

    # ---------------------------------------------------------------- 3 own material
    w(r"\section{What the available material provides}" "\n")
    w(r"""Nothing on cotton candy or food stalls existed in the user's material (\texttt{\textasciitilde/ResearchSpace});
the twin is built from public sources only. Reused machinery comes from the LabAutomation and Cuxhaven twins (by
file path, unmodified) and from the CRAM stack in \texttt{cognitive\_robot\_abstract\_machine} (read-only).
""")
    res = md_tables(R("RESOURCES.md"))
    for (head, rows), cap in zip(res, ["Own and public material used by the twin (RESOURCES.md).",
                                       "Reused machinery."]):
        cols = ["L{0.25\\linewidth}"] + ["X"] * (len(head) - 1)
        w(table(cols, [esc(h) for h in head], [[md_inline(c) for c in r] for r in rows], cap))
    w(r"\paragraph{Missing (drives the GAP and ILLUSTRATIVE entries)}" "\n")
    missing = open(R("RESOURCES.md"), encoding="utf-8").read().split("## Missing", 1)[1].split("\n## ")[0]
    w(bullets([md_inline(l[2:]) for l in missing.splitlines() if l.startswith("- ")]))

    # ---------------------------------------------------------------- 4 sources
    w(r"\section{What public sources tell}" "\n")
    w(r"""The reference machine is the Gold Medal Econo Floss 3017 export model (230~V), sold in Germany as
Neum\"arker Econo Floss 00-51551; its 28-page manual was read in full, including the photos, which give the
photo-scaled dimensions with the sourced floss band diameter as the scale bar. Key sourced facts:
""")
    key_facts = ["m_power_230", "m_heater_power", "m_motor_power", "m_mass", "m_overall_width", "m_overall_height",
                 "pan_outer_diameter", "head_band_diameter", "head_rpm", "op_master_to_heat_delay", "op_warmup",
                 "op_output_rate", "sucrose_melt", "sucrose_burn", "floss_stable_rh", "floss_collapse_rh",
                 "fibre_diameter", "portion_sugar", "price_portion", "reg_heat_clearance", "reg_fire_extinguisher_kg"]
    rows = []
    for k in key_facts:
        v, u, s, src, note = reg[k]
        rows.append([tt(k), esc(fmt(v, u)), esc(s), tt(src), esc(note)])
    w(table(["L{0.2\\linewidth}", "L{0.12\\linewidth}", "L{0.11\\linewidth}", "L{0.13\\linewidth}", "X"],
            ["Key", "Value", "Status", "Source", "Note"], rows, "Key facts from public sources (excerpt of the register)."))

    # ---------------------------------------------------------------- 5 reconstruction
    w(r"\section{The reconstruction}" "\n")
    w(figrow([("renders/booth/customer_view.png", "the customer's view through the open flap"),
              ("renders/booth/operator_view.png", "inside, towards the machine and the sales front")],
             "The booth on the fairground square (path traced in Isaac Sim 6.2)."))

    def section_table(names, caption):
        rows = []
        for k, (v, u, s, src, note) in reg.items():
            if sections[k] in names:
                rows.append([tt(k), esc(fmt(v, u)), esc(s), esc(note[:150] + ("…" if len(note) > 150 else ""))])
        return table(["L{0.22\\linewidth}", "L{0.14\\linewidth}", "L{0.12\\linewidth}", "X"],
                     ["Key", "Value", "Status", "Note"], rows, caption, size="scriptsize", long=True)

    booth_sections = [s for s in dict.fromkeys(sections.values()) if s.startswith("booth")]
    w(r"\subsection{The booth}" "\n")
    w(f"""A wooden market hut of {fmt(g('booth_width'))} $\\times$ {fmt(g('booth_depth'))} m, eave
{fmt(g('booth_eave_height'))} m, ridge {fmt(g('booth_ridge_height'))} m. The sales flap is
{fmt(g('booth_flap_width'))} m wide and {fmt(g('booth_flap_height'))} m high and opens outwards by
{fmt(g('booth_flap_open_angle'))}\\textdegree{{}} above the counter at {fmt(g('booth_counter_height'))} m. The
machine stands in the left front corner on a {fmt(g('machine_table_height'))} m table, set back
{LY.HEAT_SETBACK:.3f} m from both walls so that the heating band keeps {fmt(g('reg_heat_clearance'))} m from the
wooden walls. Hand-wash station, fire extinguisher, RCD distributor and the colour and allergen labels are placed as
the regulations require (check C9).
""")
    w(fig("renders/plans/booth_plan.png", "Plan view, generated from \\texttt{site/layout.py}: items, heat keep-out "
          "circle, PR2 at its three stations, handover point, operator free floor.", height=r"0.5\textheight"))
    w(fig("renders/plans/booth_elevation.png", "Front elevation and side section: opening, counter, eave, pan rim "
          "against elbow height, the flap edge above the customers, the PR2 envelope.", height=r"0.4\textheight"))
    w(fig("renders/booth/top_cut.png", "Cut view with the roof hidden: the layout as built in USD."))
    w(section_table(booth_sections, "Register: the booth and its regulation items."))

    w(r"\subsection{The floss machine}" "\n")
    w(f"""The machine is a {fmt(g('m_cabinet_width'))} m cabinet with a {fmt(g('pan_outer_diameter'))} m aluminium
pan, a stabilizer, a clear bubble dome with a {fmt(g('bubble_opening_angle'))}\\textdegree{{}} serving opening and a
spinner head of {fmt(g('head_band_diameter'))} m band diameter turning at {fmt(g('head_rpm'))} rpm. The controls on
the front are the motor master switch, the heat switch and the heat control knob, operated in the manual's order: motor
first, heat {fmt(g('op_master_to_heat_delay'))} s later, full heat to warm up for about {fmt(g('op_warmup'))} s, then
operating heat. The head holds {fmt(1000 * g('head_sugar_capacity'))} g of sugar (CALIBRATED to the manual's output of
{fmt(g('op_output_rate'))} portions per minute, see Section~\\ref{{sec:quality}}).
""")
    w(figrow([("renders/booth/machine_hero.png", "bubble, pan with clips, spinner head"),
              ("renders/booth/machine_controls.png", "heat dial, rocker switches, side lever")],
             "The floss machine (the pan's overhang hides the controls from above).", height=r"0.26\textheight"))
    w(section_table([s for s in dict.fromkeys(sections.values()) if s.startswith("machine")],
                    "Register: the floss machine."))

    w(r"\subsection{Sugar and ingredients}" "\n")
    flav_rows = [[esc(f["label"]), esc(", ".join(f["ingredients"]))] for f in cram["flavours"]]
    w(table(["L{0.2\\linewidth}", "X"], ["Flavour", "Ingredients (cotton\\_candy/recipes.py)"], flav_rows,
            "The floss sugars the booth may sell. Only the raspberry carton is in the booth."))
    mat_keys = [k for k in ("name", "e_number", "allergen", "requires_warning") if k in cram["materials"][0]]
    mat_rows = [[esc(m.get(k, "")) if m.get(k) not in (None, "") else "--" for k in mat_keys] for m in cram["materials"]]
    w(table(["L{0.38\\linewidth}"] + ["X"] * (len(mat_keys) - 1), [esc(k.replace("_", " ")) for k in mat_keys],
            mat_rows, "Materials in the ontology (ingredients and consumables)."))
    w(fig("renders/booth/ingredients.png", "The sugar carton with its pour spout, the sticks in their quiver and the "
          "work table."))
    w(section_table(["sugar / ingredients"], "Register: sugar, floss and portion."))

    w(r"\subsection{The robot operator}" "\n")
    links = robot.get("links", [])
    w(f"""The operator is a PR2. Its envelope is measured from the robot description
({len(links)} links in \\texttt{{data/robot\\_envelope.json}}) and the layout derives three robot stations from it:
\\emph{{machine}} (filling the carton, the controls), \\emph{{machine\\_close}} (pouring into the head, arms raised)
and \\emph{{serving}} (the handover at the counter). The handover point is at
({LY.HANDOVER_XYZ[0]:.2f}, {LY.HANDOVER_XYZ[1]:.2f}, {LY.HANDOVER_XYZ[2]:.2f}) m. Checks C14 and C15 verify that the
robot with its collision buffers ({fmt(g('robot_buffer_base_booth'))} m at the base in the booth) fits at every station.
""")

    # ---------------------------------------------------------------- 6 checks
    w(r"\section{Checks}\label{sec:checks}" "\n")
    w(f"""\\texttt{{site/checks.py}} runs {n_checks} checks on the layout model and the measured envelopes; they
write \\texttt{{data/checks.json}} (commit {tt(checks['_provenance']['git'])}) and exit non-zero on a failure.
""")
    rows = []
    for c in checks["results"]:
        detail = ", ".join(f"{k}={v}" for k, v in c.items() if k not in ("test", "passed"))
        rows.append([esc(c["test"]), "pass" if c["passed"] else "\\textbf{FAIL}", esc(detail[:120])])
    w(table(["L{0.42\\linewidth}", "l", "X"], ["Check", "Result", "Measured"], rows,
            f"Layout and robot-fit checks: {n_checks - n_failed}/{n_checks} pass.", size="scriptsize"))
    w(fig("renders/plans/checks_summary.png", "Margin of every numeric check to its limit.", height=r"0.35\textheight"))
    w(r"\paragraph{What failed, and how it was fixed}" "\n")
    w(bullets([
        "\\textbf{The robot did not fit the requested 2\\,$\\times$\\,2\\,m booth.} Check C14 failed: the PR2 base "
        "(0.67\\,m) with its collision buffers does not fit between the machine table and the back wall of a 2.0\\,m "
        "deep hut. With the user the booth was enlarged to a 3.0\\,$\\times$\\,2.6\\,m hut (a rental size), and the "
        "assets and the stage were rebuilt from the layout.",
        "\\textbf{The sales flap was too small and closed}, so nobody could see into the booth. The flap now spans "
        f"{fmt(g('booth_flap_width'))}\\,m, swings outwards by {fmt(g('booth_flap_open_angle'))}\\textdegree{{}}, and "
        "the new check C7b keeps its edge above 2.00\\,m over the customers' paving.",
        "\\textbf{Stale results.} \\texttt{data/checks.json} still came from the 2\\,$\\times$\\,2\\,m layout when "
        "this report was first assembled. Result files now carry input hashes, and this generator refuses them when "
        "an input changed.",
    ]))
    w(r"\paragraph{Checks to read with care}" "\n")
    w(bullets([
        "C4 (heating band to combustibles) holds by construction: the layout places the machine at exactly the "
        "clearance plus 2\\,mm, so C4 guards the layout but is not an independent finding.",
        "C11 (the head sustains a portion per fill) uses the CALIBRATED head capacity: a calibration, not a validation.",
        "C6 (operator free floor) does not subtract the parked robot, and C3a and C6 pass with large margins.",
        "C7b measures the flap edge above the paving where the customers stand; C7a measures headroom above the booth floor.",
    ]))

    # ---------------------------------------------------------------- 7 CRAM
    w(r"\section{The robot agent in CRAM}\label{sec:cram}" "\n")
    w(r"""The package \texttt{cram/cotton\_candy} runs on the CRAM stack (\texttt{coraplex} plans and designators,
\texttt{semantic\_digital\_twin} worlds, \texttt{krrood} EQL queries, the \texttt{cramera} viewer). The booth world
is built from the twin's layout, not from the USD stage: the same placements, with semantic annotations for every
part the robot uses (switches, knob, spinner head, pan, carton, quiver and sticks, sponge, handover zone, customer).
The machine's behaviour is a process model (\texttt{process.py}): phases off, heating, running empty and producing;
sugar in the head; floss in the pan; and a belief store with one record per ordered candy.
""")
    w(r"\subsection{Manipulation action categories}" "\n")
    w(r"""Every robot action in the booth belongs to one of the categories in Table~\ref{tab:categories}. Each category
is a designator class with its own motion pattern (e.g.\ Pressing Button holds the base and pushes the tool frame
along the switch normal; Pouring Into tilts the carton about its spout over the head) and is placed under a parent of
the CRAM L2 action-category module.
""")
    rows = [[esc(c["name"]), esc(c["parent"]), esc(c["defined_in"])] for c in cram["categories"]]
    w(table(["L{0.25\\linewidth}", "L{0.3\\linewidth}", "X"], ["Category", "Parent", "Defined in"], rows,
            "The manipulation action categories of the booth (from the ontology). \\emph{proposed} means a new "
            "category beside the CRAM L2 action-category module.\\label{tab:categories}"))
    w(r"\subsection{Top-level action designators}" "\n")
    w(r"""The shift follows the manual's procedures (pp.~5, 8--13). Each step is one top-level action designator, a
composition of categories bound to the booth's objects (Table~\ref{tab:designators}); its precondition and effect
come from the manual (Table~\ref{tab:preconditions}). Unlocking the transport handles is staff work: the handles sit
under the pan, out of the PR2's reach.
""")
    rows = [[str(s["order"]), esc(s["name"]), tt(s["designator"]), esc(" -- ".join(s["categories"])),
             esc(s["performed_by"])] for s in cram["steps"]]
    w(table(["r", "L{0.2\\linewidth}", "L{0.25\\linewidth}", "X", "l"], ["\\#", "Step", "Designator",
            "Manipulation categories (plan order)", "By"], rows,
            "The shift as top-level action designators, each a composition of categories.\\label{tab:designators}", size="scriptsize"))
    rows = [[esc(s["name"]), esc(s["precondition"]), esc(s["effect"])] for s in cram["steps"]]
    w(table(["L{0.2\\linewidth}", "X", "X"], ["Step", "Precondition", "Effect"], rows,
            "Preconditions and effects of the steps (from the manual).\\label{tab:preconditions}", size="scriptsize", long=True))
    w(r"\subsection{The shift, executed}" "\n")
    rows = [[esc(r["step"]), f"{r['time_s']:.0f}", esc(r["phase"]), f"{r['sugar_in_head_g']:.0f}",
             f"{r['floss_in_pan_g']:.0f}", str(r["portions_served"])] for r in cram["shift"]]
    w(table(["X", "r", "l", "r", "r", "r"], ["After", "process time (s)", "phase", "sugar in head (g)",
            "floss in pan (g)", "served"], rows,
            "The full shift executed kinematically on the PR2 (\\texttt{cram/export\\_results.py}); the machine "
            "state after each top-level designator."))
    w(r"""The machine is filled to 90\,\% of the head capacity, warms up while the robot waits on it (the Monitoring
category), and each sold portion takes about 24\,s of process time. The burn-out at shutdown spins the rest of the
sugar into the pan; that leftover floss is not removed by cleaning (Section~\ref{sec:limits}).
""")

    w(r"\subsection{A generalized plan: make the candy and hand it over}" "\n")
    w(r"""The top-level designators above run a fixed sequence. The generalized plan
(\texttt{universal\_plan.py}) instead achieves one goal, \emph{the customer the candy is for holds it}, from
whatever state the candy, the robot and the booth are in. It follows Beetz's concurrent reactive plans
(achieve with check-before-act, protections, failure handling), STRIPS triangle tables with PLANEX execution
(each sub-goal has a kernel: the condition under which the rest of the plan achieves the goal), Schoppers'
universal plans and Firby's RAPs (a success test and alternative methods per task).

The plan talks about its objects through entity designators, matched against the belief state (the candy belief
store and the booth's scene graph) in every cycle: \emph{the candy} is the one open order; \emph{the stick of the
candy} is the stick it is on, else the empty stick in hand, else a free stick in the quiver; \emph{the sugar for the
candy} is a carton whose contents include every ingredient; \emph{the customer of the candy} is the person who
ordered it.
""")
    rows = [[str(r["index"]), tt(r["tag"]), esc(r["kernel"]), "yes" if r["protects"] else ""] for r in plan_rows]
    w(table(["r", "L{0.2\\linewidth}", "X", "l"], ["\\#", "Sub-goal", "Kernel", "Protects"], rows,
            "The triangle table. In every cycle the plan runs the highest-numbered sub-goal whose kernel holds and "
            "whose goal does not."))
    rows = []
    for s in cram["scenarios"]:
        trace = " $\\to$ ".join(tt(t) for t in s.get("trace", [])) or "--"
        outcome = esc(s["outcome"]) if s["outcome"] == "delivered" else "\\textbf{" + esc(s["outcome"]) + "}"
        rows.append([esc(s["scenario"]), trace, outcome])
    w(table(["L{0.28\\linewidth}", "X", "L{0.18\\linewidth}"], ["Starting state", "Sub-goals executed", "Outcome"],
            rows, "The same plan started from different states (kinematic PR2)."))
    w(r"""The plan only runs the rows the state still needs: with the stick already in hand it starts at
\texttt{CANDY-FORMED}; with a wrapped candy in hand it only hands it over; a candy the belief says is wrapped but
whose stick is not in the robot's hand is counted as lost and made again. An order for a flavour with no matching
sugar in the booth is refused as unachievable, and two open orders make \emph{the candy} ambiguous, so the
designator fails rather than guess.
""")
    d_lisp, row_lisp, loop_lisp = lisp_excerpt()
    w(r"""\paragraph{The plan in RPL/CRAM notation} \texttt{cram/plans/make-and-hand-over.lisp} renders the plan as a
Lisp plan with the entity designator language (\texttt{the}/\texttt{a}/\texttt{each}/\texttt{some}). It is notation
for reading, not executed code; a test keeps its sub-goals, order and protections equal to the Python plan.
""")
    w(code(d_lisp, "Entity designators"))
    w(code(row_lisp, "One row of the triangle table"))
    w(code(loop_lisp, "The top-level loop"))
    w(r"""\paragraph{Running the plan from a browser} The cramera viewer shows and queries running plans but cannot
start them. In \texttt{COTTON\_CANDY\_PLAN=control} mode the demo serves a control page
(\texttt{http://127.0.0.1:8770}) where one places orders, changes the booth (the robot takes a stick or stops the
machine, the head runs dry, the belief loses the candy), projects which sub-goals would run, and lets the plan
achieve its goal while cramera shows it. Driving the plan from changed states found a bug the fixed test sequences
had missed: a stick put back to free the gripper was not re-attached to the quiver, so a later order was wrongly
unachievable.
""")
    w(r"\subsection{Tests}" "\n")
    rows = [[tt(f), f"{p}/{n}"] for f, (p, n) in tests["per_file"].items()]
    w(table(["X", "r"], ["Test module", "passed"], rows,
            f"CRAM tests: {tests['passed']}/{tests['total']} pass in {tests['time']:.0f}\\,s "
            f"(\\texttt{{test\\_reports/cram\\_pytest.xml}})."))

    # ---------------------------------------------------------------- 8 semantic twin
    w(r"\section{The twin as a semantic digital twin}" "\n")
    if stage:
        w(f"""The composed stage \\texttt{{scenes/cotton\\_candy\\_booth.usda}} has {stage['prims']} prims
({stage['meshes']} meshes); {stage['sdt']} carry \\texttt{{sdt:}} identity and provenance attributes, and moving
parts carry \\texttt{{state:}} runtime attributes. An example prim:
""")
        w(code(stage["example"] or "(no example prim)", "USD: sdt and state attributes"))
    c = cram["counts"]
    w(f"""\\paragraph{{The production ontology}} \\texttt{{cram/cotton\\_candy/ontology}} generates the ontology from the
CRAM world's scene graph, the register and the process: {c['steps']} production steps, {c['artefacts']} artefacts
(each linked to the semantic annotation it stands for), {c['materials']} materials, {c['hazards']} hazards with
{c['measures']} safety measures, {c['regulations']} regulations, {c['categories']} manipulation categories,
{c['qualities']} product qualities and all {c['register']} register entries with their evidence status. It is written
as OWL 2 functional syntax and checked with HermiT: {m_reason.group(1)} classes, {m_reason.group(2)} object and
{m_reason.group(3)} data properties, {m_reason.group(4)} individuals, {'consistent' if consistent else 'INCONSISTENT'}.
""")
    w(r"""\paragraph{Competency questions} The ontology and the live process are registered in cramera's query panel. The
questions are asked in German, as the booth's operators would; each is an EQL query, checked against hand-curated
gold answers in \texttt{tests/test\_competency\_questions.py}. Answers below were computed on the live world after
one candy was delivered and a second one ordered.
""")
    rows = []
    for q, en in zip(cram["questions"], CQ_EN):
        ans = q["answer"][:3]
        txt = "; ".join(", ".join(a) if isinstance(a, list) else a for a in ans)
        if q["rows"] > 3:
            txt += f" (+{q['rows'] - 3} more)"
        rows.append([esc(q["competence"]), esc(en) + "\\newline{\\itshape\\scriptsize " + esc(q["question"]) + "}",
                     esc(txt[:220])])
    w(table(["L{0.12\\linewidth}", "L{0.36\\linewidth}", "X"], ["Competence", "Question", "Answer (excerpt)"], rows,
            "The competency questions and their answers.", size="scriptsize", long=True))
    w(code(cram["questions"][15]["code"], "Example: the belief question as EQL"))

    # ---------------------------------------------------------------- 9 data quality
    w(r"\section{Data quality}\label{sec:quality}" "\n")
    w(fig("renders/plans/register_status.png", "Register entries by evidence status.", height=r"0.3\textheight"))
    by_section = OrderedDict()
    for k, v in reg.items():
        by_section.setdefault(sections[k], Counter())[v[2]] += 1
    statuses = [s for s, _ in cnt.most_common()]
    rows = []
    for name, sc in by_section.items():
        total = sum(sc.values())
        weakest = next((s for s in ("GAP", "ILLUSTRATIVE", "CALIBRATED", "ANALOGUE", "PROXY", "SOURCED-VERIFY",
                                    "DERIVED", "STANDARD", "SOURCED", "MEASURED") if sc.get(s)), "--")
        rows.append([esc(name), str(total)] + [str(sc.get(s, "")) for s in statuses] + [esc(weakest)])
    w(table(["L{0.24\\linewidth}", "r"] + ["r"] * len(statuses) + ["l"],
            ["Input set", "n"] + [esc(s[:8]) for s in statuses] + ["weakest"], rows,
            "Status mix per input set. By the weakest-input rule, a derived number is only as good as its weakest "
            "input.", size="scriptsize"))
    calibrated = [k for k, v in reg.items() if v[2] == "CALIBRATED"]
    w(bullets([
        f"\\textbf{{Calibrated, not validated:}} {', '.join(tt(k) for k in calibrated)}. It is fitted to the "
        "manual's output, so the checks and the shift timings that use it confirm the calibration; they do not "
        "validate the head geometry.",
        "\\textbf{Independent checks:} the clearance, reach, headroom, electrical and robot-fit checks compare "
        "measured or sourced values against sourced limits (standards, regulations, the manual).",
        f"\\textbf{{Illustrative:}} {cnt['ILLUSTRATIVE']} entries are design choices of this reconstruction (colours, "
        "bag sizes, the evening environment, ergonomic tolerances); competency question 13 lists them live.",
        "\\textbf{Disagreements} between sources are recorded in the notes, e.g. the rated power (1080~W Neum\\\"arker "
        "vs 1248~W Gold Medal shop) and the floss density in popular sources.",
    ]))

    # ---------------------------------------------------------------- 10 limitations
    w(r"\section{Limitations and next steps}\label{sec:limits}" "\n")
    head, rows = md_tables(R("docs", "REVIEW_FINDINGS.md"))[0]
    open_rows = [r for r in rows if not r[4].startswith("fixed")]
    fixed_rows = [r for r in rows if r[4].startswith("fixed")]
    w(f"A hostile self-review (\\texttt{{docs/REVIEW\\_FINDINGS.md}}) found {len(rows)} issues; {len(fixed_rows)} are "
      f"fixed, {len(open_rows)} remain open.\n")
    w(table(["r", "L{0.12\\linewidth}", "X", "L{0.18\\linewidth}"], ["\\#", "Area", "Finding", "Status"],
            [[r[0], md_inline(r[1]), md_inline(r[2]), md_inline(r[4])] for r in rows],
            "Review findings.", size="scriptsize", long=True))
    w(r"\paragraph{Next steps}" "\n")
    w(bullets([
        "Run the robot with collision avoidance: per-motion allowances that reach the execution environment, or a "
        "robot with smaller buffers.",
        "Make the protections concurrent fluent monitors and add evaporating protections for pouring and handing "
        "over, as the Lisp plan describes.",
        "Model the leftover floss and its disposal; model the floss as fibres for the gathering motion.",
        "Move the machine 5\\,cm away from the walls so that C4 has a real margin; subtract the robot in C6.",
        "Physics episodes in Isaac Sim (the carton pour, the handover) recorded as NEEM-style episodes.",
    ]))

    # ---------------------------------------------------------------- appendix
    w(r"\appendix" "\n")
    w(r"\section{The full register}" "\n")
    rows = [[tt(k), esc(fmt(v, u)), esc(s), tt(src), esc(note)] for k, (v, u, s, src, note) in reg.items()]
    w(table(["L{0.2\\linewidth}", "L{0.12\\linewidth}", "L{0.1\\linewidth}", "L{0.12\\linewidth}",
             "L{0.38\\linewidth}"], ["Key", "Value", "Status", "Source", "Note"], rows,
            f"All {n_reg} register entries (\\texttt{{site/params.py}}).", size="scriptsize", long=True))
    w(r"\section{Sources}" "\n")
    used = sorted({s.strip() for v in reg.values() for s in v[3].split(";")})
    w("{\\footnotesize\\begin{description}[style=nextline,leftmargin=0.6cm]\n"
      + "\n".join(f"\\item[{tt(k)}] {esc(sources[k])}" for k in used) + "\n\\end{description}}\n")
    w(r"\section{Files and rebuild}" "\n")
    w("The commands below are \\texttt{tools/build_all.sh}, in dependency order.\n".replace("_", "\\_"))
    w(code(open(R("tools", "build_all.sh"), encoding="utf-8").read()))
    w(r"\end{document}" "\n")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("% generated by report/build_report.py - edit the script, not this file\n" + "".join(out))
    if WARNINGS:
        print("\n".join("WARNING " + x for x in WARNINGS))
        sys.exit(1)
    r = subprocess.run(["latexmk", "-lualatex", "-interaction=nonstopmode", "-halt-on-error", "-cd", OUT],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:])
        sys.exit(1)
    print(f"wrote {OUT[:-4]}.pdf")


if __name__ == "__main__":
    main()
