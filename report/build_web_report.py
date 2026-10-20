"""Generate the shareable web version of the Cotton Candy Booth Twin report: report/web/index.html + report/web/img/.

Generated: edit this script, not the outputs. It reads the same inputs as report/build_report.py (register, layout,
data/*.json refused when stale, the JUnit report, the ontology reasoning log, the renders) and reuses its loaders.

Run: ~/Documents/LabAutomationTwin/env_cad/bin/python report/build_web_report.py
"""

import html
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections import Counter, OrderedDict

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("build_report", os.path.join(HERE, "build_report.py"))
BR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BR)
R, PR, LY, PV = BR.R, BR.PR, BR.LY, BR.PV
WEB = R("report", "web")
IMG = os.path.join(WEB, "img")

e = lambda s: html.escape(str(s), quote=True)  # noqa: E731


def image(src, name, width=1600, quality=82):
    """Copy a render or figure into report/web/img as a compressed web image; returns its published path."""
    path = R(src)
    if not os.path.exists(path):
        raise SystemExit(f"missing figure {src}")
    im = Image.open(path)
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    if src.startswith("renders/booth"):
        out = f"img/{name}.jpg"
        im.convert("RGB").save(os.path.join(WEB, out), quality=quality, optimize=True, progressive=True)
    else:
        out = f"img/{name}.png"
        im.save(os.path.join(WEB, out), optimize=True)
    return out


def fmt(v, u=""):
    return BR.fmt(v, u)


def table(head, rows, cls=""):
    """rows: lists of already-escaped HTML cells."""
    th = "".join(f"<th>{h}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def code(s):
    return "<code>" + e(s) + "</code>"


def figure(src, caption, cls=""):
    return f'<figure class="{cls}"><img src="{src}" alt="{e(caption)}" loading="lazy"><figcaption>{caption}</figcaption></figure>'


def status_chip(s):
    return f'<span class="st st-{e(s.lower())}">{e(s)}</span>'


def main():
    os.makedirs(IMG, exist_ok=True)
    reg, g = PR.P, PR.get
    cnt = PR.status_counts()
    n_reg = len(reg)
    sections = BR.register_sections()
    checks = PV.load_fresh("checks")
    PV.load_fresh("asset_envelopes")
    PV.load_fresh("robot_envelope")
    cram = PV.load_fresh("cram_results")
    tests = BR.junit()
    stage = BR.stage_stats()
    reasoning = open(R("data", "ontology_reasoning.txt"), encoding="utf-8").read().splitlines()
    m = re.search(r"loaded (\d+) classes, (\d+) object / (\d+) data properties, (\d+) individuals", reasoning[0])
    consistent = any("HermiT: consistent" in l for l in reasoning)
    git = subprocess.run(["git", "-C", R(), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()

    img = {k: image(f"renders/booth/{k}.png", k) for k in
           ("establishing", "customer_view", "operator_view", "machine_hero", "machine_controls", "ingredients", "top_cut")}
    for k in ("booth_plan", "booth_elevation", "checks_summary", "register_status"):
        img[k] = image(f"renders/plans/{k}.png", k, width=1800)

    n_checks, n_failed = len(checks["results"]), len(checks["failed"])
    delivered = [s for s in cram["scenarios"] if s["outcome"] == "delivered"]
    sourced = cnt["SOURCED"] + cnt["STANDARD"] + cnt["SOURCED-VERIFY"]
    P = []
    w = P.append

    # ------------------------------------------------------------------ head
    w(f"""<title>Cotton Candy Booth Twin</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=IBM+Plex+Mono:wght@400;600&display=swap">
<style>
/* Layout: a report column (~70ch) with full-bleed render bands; tables scroll inside their own frames. */
:root {{
  --bg: #fbf7f9; --paper: #ffffff; --ink: #24161f; --muted: #6e5b67; --line: #eadde5;
  --pink: #c2185b; --pink-soft: #fde4ef; --night: #1d2340; --night-soft: #e6e8f3;
  --ok: #2c7a4b; --warn: #a35a00; --bad: #b42318;
  --f-display: "Bricolage Grotesque", "Segoe UI", system-ui, sans-serif;
  --f-body: "Source Serif 4", Georgia, "Times New Roman", serif;
  --f-mono: "IBM Plex Mono", ui-monospace, Menlo, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #15111a; --paper: #1e1824; --ink: #f2e9ef; --muted: #ab97a5; --line: #362c3a;
  --pink: #f06ba0; --pink-soft: #3b1b2b; --night: #aab4ea; --night-soft: #222842;
  --ok: #86d3a2; --warn: #f0b35c; --bad: #ff8b7b; color-scheme: dark }} }}
:root[data-theme="dark"] {{
  --bg: #15111a; --paper: #1e1824; --ink: #f2e9ef; --muted: #ab97a5; --line: #362c3a;
  --pink: #f06ba0; --pink-soft: #3b1b2b; --night: #aab4ea; --night-soft: #222842;
  --ok: #86d3a2; --warn: #f0b35c; --bad: #ff8b7b; color-scheme: dark }}
* {{ box-sizing: border-box; }}
body {{ background: var(--bg); color: var(--ink); font: 400 17px/1.62 var(--f-body); }}
.wrap {{ max-width: 1120px; margin: 0 auto; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }}
.col {{ max-width: 72ch; }}
h1, h2, h3 {{ font-family: var(--f-display); line-height: 1.12; text-wrap: balance; margin: 0; }}
h1 {{ font-size: clamp(2.2rem, 5.5vw, 3.8rem); font-weight: 800; letter-spacing: -0.02em; }}
h2 {{ font-size: clamp(1.6rem, 3vw, 2.1rem); font-weight: 700; }}
h3 {{ font-size: 1.2rem; font-weight: 700; margin-top: 8px; }}
p, ul {{ margin: 0; }}
ul {{ padding-left: 1.2em; display: grid; gap: 6px; }}
a {{ color: var(--pink); }}
code {{ font: 0.82em var(--f-mono); background: var(--pink-soft); padding: 1px 5px; border-radius: 4px; overflow-wrap: anywhere; }}
.eyebrow {{ font: 600 0.74rem/1 var(--f-mono); letter-spacing: 0.1em; text-transform: uppercase; color: var(--pink); }}
header.hero {{ display: grid; gap: 22px; padding-block: 40px 28px; }}
.hero img {{ width: 100%; border-radius: 10px; display: block; }}
.lede {{ font-size: 1.2rem; color: var(--muted); max-width: 62ch; }}
.meta {{ font: 0.8rem var(--f-mono); color: var(--muted); display: flex; flex-wrap: wrap; gap: 6px 18px; }}
.facts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0; border-block: 1px solid var(--line); }}
.facts div {{ padding: 16px 14px; border-right: 1px solid var(--line); }}
.facts div:last-child {{ border-right: 0; }}
.facts b {{ display: block; font: 700 1.7rem/1.1 var(--f-display); font-variant-numeric: tabular-nums; }}
.facts span {{ font-size: 0.86rem; color: var(--muted); }}
nav.toc {{ display: flex; flex-wrap: wrap; gap: 8px; padding-block: 18px; }}
nav.toc a {{ font: 500 0.82rem var(--f-mono); text-decoration: none; color: var(--ink); border: 1px solid var(--line); border-radius: 999px; padding: 4px 12px; background: var(--paper); }}
nav.toc a:hover, nav.toc a:focus-visible {{ border-color: var(--pink); outline: none; }}
main {{ display: grid; gap: 72px; padding-block: 36px 80px; }}
section {{ display: grid; gap: 18px; min-width: 0; scroll-margin-top: 16px; }}
figure {{ margin: 0; display: grid; gap: 6px; min-width: 0; }}
figure img {{ width: 100%; max-width: 100%; border-radius: 8px; display: block; }}
figure.plot img {{ background: #fff; padding: 8px; border: 1px solid var(--line); }}
figcaption {{ font-size: 0.86rem; color: var(--muted); }}
.duo {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
@media (max-width: 760px) {{ .duo {{ grid-template-columns: 1fr; }} .facts div {{ border-right: 0; border-bottom: 1px solid var(--line); }} }}
.tw {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; background: var(--paper); }}
table {{ border-collapse: collapse; width: 100%; font: 0.86rem/1.45 var(--f-body); font-variant-numeric: tabular-nums; }}
th, td {{ text-align: left; vertical-align: top; padding: 8px 10px; border-bottom: 1px solid var(--line); }}
th {{ font: 600 0.7rem var(--f-mono); text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); white-space: nowrap; background: var(--paper); position: sticky; top: 0; }}
tbody tr:last-child td {{ border-bottom: 0; }}
td code {{ font-size: 0.8em; }}
.st {{ font: 600 0.68rem var(--f-mono); padding: 1px 6px; border-radius: 4px; white-space: nowrap; background: var(--night-soft); color: var(--night); }}
.st-sourced, .st-standard {{ background: color-mix(in srgb, var(--ok) 16%, transparent); color: var(--ok); }}
.st-illustrative, .st-calibrated {{ background: color-mix(in srgb, var(--warn) 16%, transparent); color: var(--warn); }}
.pass {{ color: var(--ok); font: 600 0.8rem var(--f-mono); }} .fail {{ color: var(--bad); font: 600 0.8rem var(--f-mono); }}
.trace {{ font: 0.78rem var(--f-mono); }}
.trace span {{ background: var(--pink-soft); color: var(--pink); padding: 1px 6px; border-radius: 4px; margin-right: 4px; white-space: nowrap; display: inline-block; margin-bottom: 3px; }}
pre {{ margin: 0; overflow-x: auto; background: var(--paper); border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; font: 0.78rem/1.5 var(--f-mono); }}
.callout {{ border-left: 3px solid var(--pink); background: var(--pink-soft); padding: 12px 16px; border-radius: 0 8px 8px 0; max-width: 72ch; }}
details {{ border: 1px solid var(--line); border-radius: 8px; background: var(--paper); }}
details > summary {{ cursor: pointer; padding: 12px 16px; font: 600 0.9rem var(--f-display); }}
details > summary:focus-visible {{ outline: 2px solid var(--pink); outline-offset: 2px; }}
details[open] > summary {{ border-bottom: 1px solid var(--line); }}
details .tw {{ border: 0; border-radius: 0; max-height: 70vh; }}
.filters {{ display: flex; flex-wrap: wrap; gap: 6px; padding: 12px 16px; border-bottom: 1px solid var(--line); }}
.filters button {{ font: 600 0.72rem var(--f-mono); border: 1px solid var(--line); background: var(--bg); color: var(--ink); border-radius: 999px; padding: 4px 10px; cursor: pointer; }}
.filters button[aria-pressed="true"] {{ background: var(--pink); border-color: var(--pink); color: var(--paper); }}
.filters button:focus-visible {{ outline: 2px solid var(--night); outline-offset: 2px; }}
.sources {{ font-size: 0.82rem; display: grid; gap: 6px; padding: 14px 16px; }}
.sources div {{ overflow-wrap: anywhere; }}
footer {{ border-top: 1px solid var(--line); padding-block: 20px 40px; color: var(--muted); font-size: 0.85rem; }}
@media (prefers-reduced-motion: no-preference) {{ html {{ scroll-behavior: smooth; }} }}
</style>
""")

    # ------------------------------------------------------------------ hero
    w('<div class="wrap">')
    w(f"""<header class="hero">
  <div class="eyebrow">Semantic digital twin · CottonCandyTwin · commit {e(git)}</div>
  <h1>A cotton candy booth that a robot can run</h1>
  <p class="lede">A German fairground Zuckerwatte booth, its floss machine and ingredients, rebuilt from public
  sources as an Isaac Sim twin, with a PR2 operator whose CRAM plans are grounded in the booth's semantics.</p>
  <img src="{img['establishing']}" alt="The pink cotton candy booth on an evening fairground square, path traced in Isaac Sim">
  <div class="meta"><span>20 October 2026</span><span>Design study, not a real booth</span><span>Every number carries a status and a source</span></div>
</header>
<div class="facts">
  <div><b>{fmt(g('booth_width'))} × {fmt(g('booth_depth'))} m</b><span>booth, eave {fmt(g('booth_eave_height'))} m</span></div>
  <div><b>{n_reg}</b><span>register entries, {round(100 * sourced / n_reg)} % sourced</span></div>
  <div><b>{n_checks - n_failed}/{n_checks}</b><span>layout and robot-fit checks pass</span></div>
  <div><b>{len(delivered)}/{len(cram['scenarios'])}</b><span>plan start states delivered, rest refused</span></div>
  <div><b>{len(cram['questions'])}</b><span>competency questions answered live</span></div>
  <div><b>{tests['passed']}/{tests['total']}</b><span>CRAM tests pass</span></div>
</div>
<nav class="toc" aria-label="Sections">
  <a href="#summary">Summary</a><a href="#booth">Booth</a><a href="#machine">Machine</a><a href="#ingredients">Ingredients</a>
  <a href="#checks">Checks</a><a href="#cram">Robot in CRAM</a><a href="#plan">Generalized plan</a>
  <a href="#ontology">Ontology</a><a href="#quality">Data quality</a><a href="#limits">Limitations</a><a href="#register">Register</a>
</nav>
<main>""")

    # ------------------------------------------------------------------ summary
    w(f"""<section id="summary" class="col">
<div class="eyebrow">1 · Summary</div><h2>What was built</h2>
<p>The request was a typical 2 × 2 m cotton candy booth from a German fair, with the details of the machine and the
ingredients. It became a manipulation scenario: a PR2 fills and starts the machine, spins and wraps portions, hands
them to the customer, shuts the machine down and cleans it. The twin has four layers, each generated from the repository:</p>
<ul>
<li><b>Register and layout.</b> {n_reg} parameters, each with a status and a source; one layout model that the checks,
figures, USD stage and robot world all read. {n_checks - n_failed}/{n_checks} checks pass.</li>
<li><b>Isaac Sim stage.</b> The booth, the machine and the fairground square{f", {stage['prims']} prims, {stage['sdt']} with semantic identity" if stage else ""}, path traced.</li>
<li><b>CRAM robot agent.</b> {len(cram['steps'])} top-level action designators built from {cram['counts']['categories']}
manipulation action categories, and a generalized plan that makes the ordered candy and hands it over from any state.</li>
<li><b>Ontology.</b> Generated from the scene graph and linked to its semantic annotations: {m.group(1)} classes,
{m.group(4)} individuals, HermiT {'consistent' if consistent else 'inconsistent'}; {len(cram['questions'])} competency
questions answered in the cramera viewer.</li>
</ul>
<div class="callout"><b>Main limitations.</b> The robot runs kinematically with collision avoidance off, because the PR2's
collision buffers are larger than the clearances of a human-scale machine. Sugar and floss are a process model, not
particle physics. And the booth had to grow from 2 × 2 m to {fmt(g('booth_width'))} × {fmt(g('booth_depth'))} m for the robot to fit.</div>
</section>""")

    # ------------------------------------------------------------------ booth
    def reg_rows(keys):
        return [[code(k), e(fmt(reg[k][0], reg[k][1])), status_chip(reg[k][2]), e(reg[k][4])] for k in keys]

    w(f"""<section id="booth">
<div class="col"><div class="eyebrow">2 · The reconstruction</div><h2>The booth</h2></div>
<div class="duo">{figure(img['customer_view'], "The customer's view through the open sales flap.")}
{figure(img['operator_view'], "Inside: towards the machine table, the counter and the opening.")}</div>
<p class="col">A wooden market hut of {fmt(g('booth_width'))} × {fmt(g('booth_depth'))} m, eave {fmt(g('booth_eave_height'))} m,
ridge {fmt(g('booth_ridge_height'))} m. The sales flap is {fmt(g('booth_flap_width'))} m wide and {fmt(g('booth_flap_height'))} m
high and opens outwards by {fmt(g('booth_flap_open_angle'))}° above the {fmt(g('booth_counter_height'))} m counter. The machine
stands in the left front corner on a {fmt(g('machine_table_height'))} m table, set back {LY.HEAT_SETBACK:.3f} m from both walls
so the heating band keeps the required {fmt(g('reg_heat_clearance'))} m from the wooden walls. Hand-wash station, fire
extinguisher, RCD distributor and the colour and allergen labels are placed as the regulations require.</p>
{figure(img['booth_plan'], "Plan view from <code>site/layout.py</code>: items, heat keep-out circle, the PR2 at its three stations, handover point, operator free floor.", "plot")}
<div class="duo">{figure(img['booth_elevation'], "Front elevation and side section: opening, counter, eave, pan rim against elbow height, flap edge above the customers.", "plot")}
{figure(img['top_cut'], "Cut view with the roof hidden: the layout as built in USD.")}</div>
{table(["Key", "Value", "Status", "Note"], reg_rows([k for k in ("booth_width", "booth_depth", "booth_eave_height", "booth_counter_height", "booth_flap_width", "booth_flap_open_angle", "machine_table_height", "reg_heat_clearance", "reg_fire_extinguisher_kg", "reg_handwash_required") if k in reg]))}
</section>""")

    # ------------------------------------------------------------------ machine
    machine_keys = ["m_power_230", "m_heater_power", "m_motor_power", "m_mass", "pan_outer_diameter", "bubble_opening_angle",
                    "head_band_diameter", "head_rpm", "head_sugar_capacity", "op_master_to_heat_delay", "op_warmup",
                    "op_output_rate"]
    w(f"""<section id="machine">
<div class="col"><h2>The floss machine</h2></div>
<div class="duo">{figure(img['machine_hero'], "Bubble, pan with clips, spinner head.")}
{figure(img['machine_controls'], "Heat dial, rocker switches and side lever, hidden from above by the pan.")}</div>
<p class="col">The reference machine is the Gold Medal Econo Floss 3017 export model (230 V), sold in Germany as
Neumärker Econo Floss 00-51551. Its 28-page manual was read in full; photo-scaled dimensions use the sourced floss
band diameter as the scale bar. The controls are operated in the manual's order: motor first, heat
{fmt(g('op_master_to_heat_delay'))} s later, full heat to warm up, then operating heat. The head holds
{fmt(1000 * g('head_sugar_capacity'))} g of sugar, calibrated to the manual's output of {fmt(g('op_output_rate'))} portions
per minute.</p>
{table(["Key", "Value", "Status", "Note"], reg_rows(machine_keys))}
</section>""")

    # ------------------------------------------------------------------ ingredients
    flav = [[e(f["label"]), e(", ".join(f["ingredients"]))] for f in cram["flavours"]]
    mats = [[e(x.get("name", "")), e(x.get("e_number") or "–"), e(x.get("allergen") or "–"),
             "yes" if x.get("requires_warning") else "–"] for x in cram["materials"]]
    w(f"""<section id="ingredients">
<div class="col"><h2>Sugar and ingredients</h2></div>
{figure(img['ingredients'], "The Flossugar carton with its pour spout, the sponge, the sticks in their quiver.")}
<div class="duo">{table(["Flavour", "Ingredients"], flav)}{table(["Material", "E number", "Allergen", "Warning"], mats)}</div>
<p class="col">Only the raspberry carton is in the booth. Allura Red (E129) requires the warning
<i>“kann Aktivität und Aufmerksamkeit bei Kindern beeinträchtigen”</i>, and the lactose carrier of the colour sugar is a
milk allergen; both labels are part of check C9.</p>
</section>""")

    # ------------------------------------------------------------------ checks
    rows = []
    for c in checks["results"]:
        detail = ", ".join(f"{k}={v}" for k, v in c.items() if k not in ("test", "passed"))
        rows.append([e(c["test"]), '<span class="pass">pass</span>' if c["passed"] else '<span class="fail">FAIL</span>',
                     f'<span class="trace">{e(detail[:140])}</span>'])
    w(f"""<section id="checks">
<div class="col"><div class="eyebrow">3 · Checks</div><h2>{n_checks - n_failed} of {n_checks} checks pass</h2>
<p><code>site/checks.py</code> checks the layout against measured envelopes and sourced limits, and exits non-zero on a failure.</p></div>
{table(["Check", "Result", "Measured"], rows)}
{figure(img['checks_summary'], "Margin of every numeric check to its limit.", "plot")}
<div class="col"><h3>What failed, and how it was fixed</h3>
<ul>
<li><b>The robot did not fit the requested 2 × 2 m booth.</b> The PR2 base with its collision buffers does not fit
between the machine table and the back wall of a 2.0 m deep hut. With the user the booth became a 3.0 × 2.6 m rental
hut, and the assets and stage were rebuilt from the layout.</li>
<li><b>The sales flap was too small and closed.</b> It now spans {fmt(g('booth_flap_width'))} m, swings out by
{fmt(g('booth_flap_open_angle'))}°, and check C7b keeps its edge above 2.00 m over the customers' paving.</li>
<li><b>Stale results.</b> The check results still came from the 2 × 2 m layout when the report was first assembled.
Result files now carry input hashes, and the report refuses stale ones.</li>
</ul>
<h3>Checks to read with care</h3>
<ul>
<li>C4 (heating band to combustibles) holds by construction, with 2 mm to spare: the layout places the machine at the clearance.</li>
<li>C11 uses the calibrated head capacity: it confirms the calibration, it does not validate the head.</li>
<li>C6 (operator free floor) does not subtract the parked robot.</li>
</ul></div>
</section>""")

    # ------------------------------------------------------------------ cram
    cats = [[e(c["name"]), e(c["parent"]), e(c["defined_in"])] for c in cram["categories"]]
    steps = [[str(s["order"]), e(s["name"]), code(s["designator"]),
              '<span class="trace">' + "".join(f"<span>{e(x)}</span>" for x in s["categories"]) + "</span>",
              e(s["performed_by"])] for s in cram["steps"]]
    shift = [[e(r["step"]), f"{r['time_s']:.0f}", e(r["phase"]), f"{r['sugar_in_head_g']:.0f}", f"{r['floss_in_pan_g']:.0f}",
              str(r["portions_served"])] for r in cram["shift"]]
    w(f"""<section id="cram">
<div class="col"><div class="eyebrow">4 · The robot agent in CRAM</div><h2>A shift as manipulation categories</h2>
<p>The package <code>cram/cotton_candy</code> runs on the CRAM stack (coraplex plans, semantic digital twin worlds,
krrood EQL queries, the cramera viewer). The robot's world is built from the twin's layout with semantic annotations for
every part the robot uses. The machine is a process model: phases, sugar in the head, floss in the pan, and a belief
store with one record per ordered candy.</p></div>
<div class="duo">{table(["Category", "Parent", "Defined in"], cats)}
<div class="col"><p>Every robot action belongs to one of these categories. Each is a designator class with its own motion
pattern: Pressing Button holds the base and pushes along the switch normal, Pouring Into tilts the carton about its
spout over the head. Categories marked <i>proposed</i> are new beside the CRAM L2 action-category module.</p></div></div>
{table(["#", "Step", "Designator", "Categories, in plan order", "By"], steps)}
<p class="col">Unlocking the transport handles is staff work: they sit under the pan, out of the PR2's reach.
The full shift, executed kinematically, with the machine state after each step:</p>
{table(["After", "Process time (s)", "Phase", "Sugar in head (g)", "Floss in pan (g)", "Served"], shift)}
</section>""")

    # ------------------------------------------------------------------ plan
    rows = [[str(r["index"]), code(r["tag"]), e(r["kernel"]), "until delivered" if r["protects"] else ""] for r in cram["plan_rows"]]
    scen = []
    for s in cram["scenarios"]:
        tr = '<span class="trace">' + "".join(f"<span>{e(t)}</span>" for t in s.get("trace", [])) + "</span>" if s.get("trace") else "–"
        out = f'<span class="pass">{e(s["outcome"])}</span>' if s["outcome"] == "delivered" else f'<span class="fail">{e(s["outcome"])}</span>'
        scen.append([e(s["scenario"]), tr, out])
    d_lisp, row_lisp, loop_lisp = BR.lisp_excerpt()
    w(f"""<section id="plan">
<div class="col"><h2>A generalized plan: make the candy and hand it over</h2>
<p>Instead of a fixed sequence, the plan achieves one goal, <i>the customer the candy is for holds it</i>, from whatever
state the candy, the robot and the booth are in. It follows Beetz's concurrent reactive plans, STRIPS triangle tables
with PLANEX execution, Schoppers' universal plans and Firby's RAPs. It names its objects through entity designators that
are matched against the belief state in every cycle: <i>the candy</i> is the one open order; <i>its stick</i> is the
stick it is on, else the empty stick in hand, else a free stick in the quiver; <i>the sugar for it</i> is a carton whose
contents include every ingredient; <i>its customer</i> is whoever ordered it.</p></div>
{table(["#", "Sub-goal", "Kernel: the rest of the plan works from here when", "Protects"], rows)}
{table(["Starting state", "Sub-goals executed", "Outcome"], scen)}
<p class="col">The plan only runs what the state still needs. An order with no matching sugar is refused as
unachievable, and two open orders make <i>the candy</i> ambiguous, so the designator fails rather than guess.</p>
<div class="col"><h3>The plan in RPL/CRAM notation</h3>
<p><code>cram/plans/make-and-hand-over.lisp</code> renders the plan as a Lisp plan in the entity designator language.
It is notation for reading; a test keeps its sub-goals, order and protections equal to the executable Python plan.</p></div>
<details><summary>Entity designators</summary><pre>{e(d_lisp)}</pre></details>
<details><summary>One row of the triangle table</summary><pre>{e(row_lisp)}</pre></details>
<details><summary>The top-level loop</summary><pre>{e(loop_lisp)}</pre></details>
<div class="callout"><b>Running it from a browser.</b> cramera shows and queries plans but cannot start them, so the demo
serves a control page for orders, changes to the booth, projection and execution. Driving the plan from changed states
found a bug the fixed tests missed: a stick put back to free the gripper was not re-attached to the quiver, so a later
order was wrongly unachievable. It is fixed.</div>
</section>""")

    # ------------------------------------------------------------------ ontology
    c = cram["counts"]
    cq = []
    for q, en in zip(cram["questions"], BR.CQ_EN):
        ans = q["answer"][:3]
        txt = "; ".join(", ".join(a) if isinstance(a, list) else a for a in ans)
        if q["rows"] > 3:
            txt += f" (+{q['rows'] - 3} more)"
        cq.append([e(q["competence"]), f"{e(en)}<br><i style='color:var(--muted)'>{e(q['question'])}</i>", e(txt[:240])])
    w(f"""<section id="ontology">
<div class="col"><div class="eyebrow">5 · Semantic twin</div><h2>An ontology the viewer can be asked</h2>
<p>The production ontology is generated from the robot world's scene graph, the register and the process:
{c['steps']} production steps, {c['artefacts']} artefacts each linked to its semantic annotation, {c['materials']} materials,
{c['hazards']} hazards with {c['measures']} safety measures, {c['regulations']} regulations, {c['categories']} categories and all
{c['register']} register entries with their evidence status. HermiT finds it {'consistent' if consistent else 'inconsistent'}
({m.group(1)} classes, {m.group(4)} individuals). The competency questions are asked in German, as operators would;
answers were computed on the live world after one candy was delivered and a second ordered.</p></div>
{table(["Competence", "Question", "Answer (excerpt)"], cq)}
</section>""")

    # ------------------------------------------------------------------ quality
    by_section = OrderedDict()
    for k, v in reg.items():
        by_section.setdefault(sections[k], Counter())[v[2]] += 1
    statuses = [s for s, _ in cnt.most_common()]
    rows = [[e(n), str(sum(sc.values()))] + [str(sc.get(s, "")) for s in statuses] for n, sc in by_section.items()]
    w(f"""<section id="quality">
<div class="col"><div class="eyebrow">6 · Data quality</div><h2>How good the numbers are</h2></div>
{figure(img['register_status'], "Register entries by evidence status.", "plot")}
{table(["Input set", "n"] + [e(s) for s in statuses], rows)}
<ul class="col">
<li><b>Calibrated, not validated:</b> the head capacity is fitted to the manual's output, so checks that use it confirm the calibration.</li>
<li><b>Independent:</b> clearance, reach, headroom, electrical and robot-fit checks compare measured or sourced values with sourced limits.</li>
<li><b>Illustrative:</b> {cnt['ILLUSTRATIVE']} entries are design choices of this reconstruction; competency question 13 lists them live.</li>
</ul>
</section>""")

    # ------------------------------------------------------------------ limitations
    head, rows = BR.md_tables(R("docs", "REVIEW_FINDINGS.md"))[0]
    md = lambda s: re.sub(r"`([^`]+)`", r"<code>\1</code>", e(s))  # noqa: E731
    fixed = sum(r[4].startswith("fixed") for r in rows)
    w(f"""<section id="limits">
<div class="col"><div class="eyebrow">7 · Limitations</div><h2>{len(rows)} review findings, {fixed} fixed</h2>
<p>A hostile self-review before calling the twin done.</p></div>
{table(["#", "Area", "Finding", "Status"], [[r[0], md(r[1]), md(r[2]), md(r[4])] for r in rows])}
<div class="col"><h3>Next steps</h3><ul>
<li>Run the robot with collision avoidance: allowances that reach the execution environment, or a robot with smaller buffers.</li>
<li>Make the plan's protections concurrent monitors and protect pouring and handing over, as the Lisp plan describes.</li>
<li>Model the leftover floss and its disposal; model floss as fibres for the gathering motion.</li>
<li>Move the machine 5 cm from the walls so C4 has a real margin; subtract the robot in C6.</li>
<li>Physics episodes in Isaac Sim for the carton pour and the handover.</li>
</ul></div>
</section>""")

    # ------------------------------------------------------------------ register
    rrows = "".join(f'<tr data-st="{e(s)}"><td>{code(k)}</td><td>{e(fmt(v, u))}</td><td>{status_chip(s)}</td>'
                    f"<td>{code(src)}</td><td>{e(note)}</td></tr>" for k, (v, u, s, src, note) in reg.items())
    used = sorted({x.strip() for v in reg.values() for x in v[3].split(";")})
    src_html = "".join(f"<div>{code(k)} {e(PR.SOURCES[k])}</div>" for k in used)
    buttons = '<button type="button" aria-pressed="true" data-f="">all</button>' + "".join(
        f'<button type="button" aria-pressed="false" data-f="{e(s)}">{e(s.lower())} ({n})</button>' for s, n in cnt.most_common())
    w(f"""<section id="register">
<div class="col"><div class="eyebrow">Appendix</div><h2>The parameter register</h2>
<p>All {n_reg} entries of <code>site/params.py</code> and their sources. Filter by status.</p></div>
<details open><summary>Register ({n_reg} entries)</summary>
<div class="filters" id="filters">{buttons}</div>
<div class="tw"><table><thead><tr><th>Key</th><th>Value</th><th>Status</th><th>Source</th><th>Note</th></tr></thead><tbody id="reg">{rrows}</tbody></table></div>
</details>
<details><summary>Sources ({len(used)})</summary><div class="sources">{src_html}</div></details>
</section>
</main>
<footer>Generated from the CottonCandyTwin repository (commit {e(git)}) by <code>report/build_web_report.py</code>;
the PDF report is <code>report/cotton_candy_twin.pdf</code>. Renders: Isaac Sim 6.2, path traced, 1024 samples per pixel.</footer>
</div>
<script>
const rows = [...document.querySelectorAll("#reg tr")];
document.getElementById("filters").addEventListener("click", ev => {{
  const b = ev.target.closest("button"); if (!b) return;
  document.querySelectorAll("#filters button").forEach(x => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
  rows.forEach(r => r.hidden = !!b.dataset.f && r.dataset.st !== b.dataset.f);
}});
</script>
""")
    with open(os.path.join(WEB, "index.html"), "w", encoding="utf-8") as f:
        f.write("<!-- generated by report/build_web_report.py - edit the script, not this file -->\n" + "".join(P))
    size = sum(os.path.getsize(os.path.join(IMG, x)) for x in os.listdir(IMG))
    print(f"wrote {WEB}/index.html ({os.path.getsize(os.path.join(WEB, 'index.html')) // 1024} KB) + {len(os.listdir(IMG))} images ({size // 1024} KB)")


if __name__ == "__main__":
    main()
