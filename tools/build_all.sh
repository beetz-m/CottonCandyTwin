#!/usr/bin/env bash
# Rebuild everything in dependency order. Must match the report appendix "Files and rebuild".
set -euo pipefail
cd "$(dirname "$0")/.."
E=~/Documents/LabAutomationTwin/env_cad/bin/python
I=~/Documents/LabAutomationTwin/env_isaacsim/bin/python
export OMNI_KIT_ACCEPT_EULA=YES

$E site/params.py                                   # register audit (exit 1 on a missing source key)
$E assets/materials/build_materials.py
$E assets/machine/build_machine.py                  # also writes data/asset_envelopes.json (MEASURED)
$E assets/booth/build_booth.py
cram/run.sh python -m cotton_candy.robot_envelope   # data/robot_envelope.json (PR2, MEASURED)
$E site/checks.py                                   # data/checks.json (exit 1 on a failed check)
$E site/plan_figures.py                             # renders/plans/*.png
$E scenes/build_scene.py                            # scenes/cotton_candy_booth.usda
cram/run.sh python -m cotton_candy.ontology.owl     # ontology/build/cotton_candy_production.ofn
$E ontology/reason.py | tee data/ontology_reasoning.txt   # HermiT consistency (exit 1 if inconsistent)
cram/run.sh pytest cram/tests --junitxml=test_reports/cram_pytest.xml
cram/run.sh python cram/export_results.py           # data/cram_results.json (shift, plan scenarios, CQ answers)
$I scripts/render_report_views.py                   # renders/booth/*.png, headless path tracing (one GPU job at a time)
$E report/build_report.py                           # report/cotton_candy_twin.pdf
