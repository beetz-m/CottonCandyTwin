"""Path-traced stills of the composed twin from named views (one GPU job at a time).

  OMNI_KIT_ACCEPT_EULA=YES ~/Documents/LabAutomationTwin/env_isaacsim/bin/python scripts/render_views.py \
      [--quick] [--stage=twin.usda] [--out=renders/site] [view ...]

Views whose name starts with 'cut_' hide the ROOFS prims (render-only, session layer; the stage file is untouched).
Compute VIEWS from layout constants, never from hand-typed coordinates that can drift from the layout.
"""

import os
import sys

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
QUICK = "--quick" in sys.argv
ONLY = [a for a in sys.argv[1:] if not a.startswith("--")]
OPT = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, OPT.get("out", "renders/site"))
RES = (1280, 800) if QUICK else (1920, 1200)

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True, "renderer": "PathTracing", "width": RES[0], "height": RES[1]})

import omni.usd  # noqa: E402
from pxr import UsdGeom  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "site"))
import render_lib as RL  # noqa: E402
# import layout as L      # derive the views from the layout model

SUB = RL.configure(*((8, 24) if QUICK else (16, 64)))
omni.usd.get_context().open_stage(os.path.join(ROOT, "scenes", OPT.get("stage", "twin.usda")))
for _ in range(30):
    app.update()
stage = omni.usd.get_context().get_stage()
stage.SetEditTarget(stage.GetSessionLayer())
ROOFS = []  # e.g. ["/World/Site/Hall/Visual/RoofMembrane"]


def roof(visible):
    for p in ROOFS:
        prim = stage.GetPrimAtPath(p)
        if prim:
            UsdGeom.Imageable(prim).GetVisibilityAttr().Set("inherited" if visible else "invisible")


VIEWS = {  # name: (eye, target, focal_mm)
    "overview": ((60, -80, 45), (0, 0, 0), 24),
}

cam = RL.Camera(stage, RES, SUB)
for name, (eye, tgt, focal) in VIEWS.items():
    if ONLY and name not in ONLY:
        continue
    roof(not name.startswith("cut_"))
    cam.shot(os.path.join(OUT, f"{name}{'_quick' if QUICK else ''}.png"), eye, tgt, focal)
roof(True)
sys.stdout.flush()
os._exit(0)
