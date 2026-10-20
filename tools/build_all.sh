#!/usr/bin/env bash
# Rebuild everything in dependency order. Must match the report appendix "Files and rebuild".
set -euo pipefail
cd "$(dirname "$0")/.."
E=~/Documents/LabAutomationTwin/env_cad/bin/python
I=~/Documents/LabAutomationTwin/env_isaacsim/bin/python
export OMNI_KIT_ACCEPT_EULA=YES

$E site/params.py
$E assets/materials/build_materials.py
# $E assets/<family>/build_<family>.py ...
# $E site/<checks>.py ...
# $E scenes/build_scene.py
# $E site/plan_figures.py
# $I scripts/render_site.py --quick        # one GPU job at a time
# $E report/build_report.py
