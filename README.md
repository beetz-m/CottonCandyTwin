# Cotton Candy Booth Twin

Fictional / design study - not a real facility. Isaac Sim 6.2 semantic digital twin (scale: cell).

Every number has a status (SOURCED, SOURCED-VERIFY, STANDARD, DERIVED, PROXY, OSM, ANALOGUE, MEASURED, CALIBRATED,
ILLUSTRATIVE, GAP) in `site/params.py`. Builders are the source of truth: generated USD, figures and JSON are never
edited by hand and are not committed.

| Path | What |
|---|---|
| `RESOURCES.md` | inventory of own / upstream material (real vs synthetic), what is missing |
| `site/params.py` | parameter register + sources |
| `site/layout.py` | layout / structure model (pure Python; single source of placements) |
| `assets/<family>/build_*.py` | asset builders -> `assets/<family>/usd/` |
| `assets/materials/build_materials.py` | shared MDL material library |
| `scenes/build_scene.py` | composed stage with `sdt:` semantics and `state:` attributes |
| `twin/` | runtime controllers |
| `scripts/` | Isaac renders, tests, episodes |
| `tools/build_all.sh` | rebuild everything in dependency order |
| `data/` | check and model results (JSON with provenance) |
| `report/build_report.py` | generated LaTeX report |
| `docs/REVIEW_FINDINGS.md` | critical self-review |

## Environments

    E=~/Documents/LabAutomationTwin/env_cad/bin/python        # builders, checks, report
    I=~/Documents/LabAutomationTwin/env_isaacsim/bin/python   # Isaac Sim 6.2 (OMNI_KIT_ACCEPT_EULA=YES)

One Isaac GPU job at a time (RTX 3070, 8 GB).

## Rebuild

    tools/build_all.sh

## Decisions

- 2026-10-20: project started.
