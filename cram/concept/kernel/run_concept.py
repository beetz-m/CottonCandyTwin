"""Run a plan schema of booth.lisp on the CRAM booth through ccram (the generic kernel + concept/adapter.py).

    cram/run.sh python cram/concept/kernel/run_concept.py [plan]                    # headless (no viewer)
    cram/run.sh cramera-live cram/concept/kernel/run_concept.py [plan]             # watch it in cramera
Env: CONCEPT_PLAN, CONCEPT_SCENARIO, COTTON_CANDY_HOLD=1, CONCEPT_WORKBENCH=1 (serve the workbench page after the plan).
The same as  ~/Documents/ConceptualCRAM/bin/ccram run cram/concept --plan P --scenario S [--workbench] [--hold].
(kernel/booth_kernel.py is the pre-ccram kernel, kept for reference only.)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.expanduser("~/Documents/ConceptualCRAM"))
from ccram.activity import load  # noqa: E402
from ccram.session import run  # noqa: E402

if __name__ == "__main__":
    act = load(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    plan = os.environ.get("CONCEPT_PLAN", sys.argv[1] if len(sys.argv) > 1 else act.default_plan)
    run(act, plan=plan, scenario=os.environ.get("CONCEPT_SCENARIO", ""),
        workbench=os.environ.get("CONCEPT_WORKBENCH", "0") == "1", hold=os.environ.get("COTTON_CANDY_HOLD", "0") == "1")
