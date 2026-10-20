# Resources for the Cotton Candy Booth Twin

An inventory of the material available before the build. Nothing listed here is modified by this project.

Labels:
- **REAL**: a primary source or a measurement.
- **PUBLIC**: a published source.
- **SYNTHETIC**: invented or LLM-made upstream material.

## Own and upstream material

`~/ResearchSpace` contains nothing on cotton candy, fairground booths or food stalls (grep for zuckerwatte, cotton candy and candy floss, 2026-10-20). The twin is built **only from public sources**.

| Resource | Path / URL | Provenance | Use in the twin |
|---|---|---|---|
| Gold Medal Econo Floss 3017 export manual (2021), with photos and parts lists | SOURCES `GM_MAN_EXP` (local copy in the session scratchpad, not redistributed) | PUBLIC (manufacturer) | machine structure, controls, spinner head parts, procedures, photo-scaled dimensions |
| Gold Medal 1997 manual, shop page, patents US4872821, US5766643, US7300269 | SOURCES | PUBLIC | rpm, overall dimensions, head principle |
| Neumärker, Bartscher, GGM and Paragon data | SOURCES | PUBLIC (some secondary) | cross-checks and ranges |
| Food science: Labuza 2004, Roe 2005, Marano 2016, Bandi 2020 | SOURCES | PUBLIC (peer-reviewed / arXiv) | Tg, humidity collapse, fibre diameter, temperatures, rpm |
| Booth makers and rental listings (markthuetten.de, Steinhauer, rentals) | SOURCES | PUBLIC (product pages) | hut footprint, panels, counter depth, heights |
| Regulation: EU 852/2004, LMZDV §5, EU 1333/2008 Annex V, MBO §76, municipal leaflets | SOURCES | PUBLIC (law and authority leaflets) | hand-wash station, labels, extinguisher, heat clearance, RCD |
| Poly Haven HDRs | ~/Documents/CuxhavenSiteTwin/assets/sky (CC0) | PUBLIC | lighting (copied, with attribution) |

## Reusable machinery

| What | Path | How it is reused |
|---|---|---|
| mesh kit | ~/Documents/LabAutomationTwin/assets/common/meshkit.py | loaded by file path (assets/common/kit.py) |
| material library builder | ~/Documents/LabAutomationTwin/assets/materials/build_materials.py | extended by assets/materials/build_materials.py |
| CadQuery->USD helpers | ~/Documents/LabAutomationTwin/assets/common/twin_cad.py | loaded by file path for the articulated machine |

## Missing (drives the GAP / ILLUSTRATIVE entries)

- Spinner head height, slot geometry and sugar capacity. Neither the manuals nor the patents give them; they are scaled from photos.
- Head speed at 50 Hz.
- Bubble (dome) dimensions.
- Counter height of 2×2 market huts; only retail proxies exist.
- Any sourced design of a pink "Zuckerwatte" livery.
- A measured size of a finished fairground portion. The floss density in popular sources is inconsistent with the size seen in photos.
- Critical relative humidity of the sucrose glass at 20 °C, which is only bracketed between 11 % and 33 % RH.
