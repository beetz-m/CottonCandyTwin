"""Report stills of the booth, with views computed from the layout model (site/layout.py).

  OMNI_KIT_ACCEPT_EULA=YES ~/Documents/LabAutomationTwin/env_isaacsim/bin/python scripts/render_report_views.py [view ...]
  python3 scripts/render_report_views.py --gui [view ...]    # preview through the running Isaac GUI (isc.py, 8226)

Finals: headless, 1920x1200, path tracing 16 spp x 64 subframes (render_lib.configure(16, 64)); close the GUI first
(one GPU job). The GUI mode keeps the viewport's own resolution: raising a path-traced GUI viewport to 1920x1200 on
the 8 GB RTX 3070 ended in ERROR_DEVICE_LOST (2026-10-20).

Output: renders/booth/<view>.png. Views starting with 'cut_' or named 'top_cut' hide the roof (session layer only).
The GUI mode uses its own camera /World/Cameras/ReportView and gives the viewport back to the camera it had.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "site"))
import layout as L  # noqa: E402

OUT = os.path.join(ROOT, "renders", "booth")
RES = (1920, 1200)
ROOFS = ["/World/Booth/Roof"]
ISC = os.path.expanduser("~/.claude/skills/isaac-twin/scripts/isc.py")

F = L.FLOOR_Z
MX, MY = L.MACHINE_XY
EYE = 1.62   # customer eye height above the paving


def views():
    """name: (eye, target, focal_mm) in the booth frame B."""
    return {
        "establishing": ((-2.3, L.Y0 - 5.6, EYE + 0.15), (0.0, 0.0, F + 1.30), 22),
        "customer_view": ((0.35, L.Y0 - 1.25, EYE), (-0.35, 0.25, L.COUNTER_Z + 0.15), 16),
        "operator_view": ((1.15, L.Y1 - 0.24, F + 1.70), (-0.30, L.Y0 + 0.09, L.COUNTER_Z - 0.05), 18),   # door leaf out of frame
        "machine_hero": ((MX + 0.75, MY + 0.95, L.M_TOP_Z + 0.42), (MX, MY, L.HEAD_Z + 0.05), 26),
        "machine_controls": ((MX + 0.30, MY + 0.95, L.TABLE_Z + 0.32), (MX, MY + 0.10, L.TABLE_Z + 0.12), 30),
        "ingredients": ((L.TABLE_X1 + 0.55, L.TABLE_Y1 + 0.65, F + 1.45), (L.X0 + 0.45, L.TABLE_Y1 - 0.25, L.TABLE_Z + 0.12), 17),
        "top_cut": ((0.35, L.Y1 + 1.9, F + 4.8), (-0.15, -0.25, F + 0.45), 15),   # from behind: flap and sign do not hide the interior
    }


GUI_SHOT = """
import omni.kit.app, omni.usd
from pxr import Gf, UsdGeom
from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
st = omni.usd.get_context().get_stage()
vp = get_active_viewport()
before_cam = vp.camera_path
st.SetEditTarget(st.GetSessionLayer())
for p in {roofs!r}:
    prim = st.GetPrimAtPath(p)
    if prim:
        UsdGeom.Imageable(prim).GetVisibilityAttr().Set("invisible" if {cut!r} else "inherited")
cam = UsdGeom.Camera.Define(st, "/World/Cameras/ReportView")
cam.CreateFocalLengthAttr().Set({focal})
cam.CreateHorizontalApertureAttr().Set(36.0)
cam.CreateVerticalApertureAttr().Set(36.0 * vp.resolution[1] / vp.resolution[0])
cam.CreateClippingRangeAttr().Set(Gf.Vec2f(0.03, 8000.0))
cam.CreateFStopAttr().Set(0.0)
m = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*{eye!r}), Gf.Vec3d(*{target!r}), Gf.Vec3d(0, 0, 1)).GetInverse()
x = UsdGeom.Xformable(cam); x.ClearXformOpOrder(); x.AddTransformOp().Set(m)
vp.camera_path = "/World/Cameras/ReportView"
for _ in range({wait}):
    await omni.kit.app.get_app().next_update_async()
h = capture_viewport_to_file(vp, {out!r})
await h.wait_for_result(completion_frames=30)
for p in {roofs!r}:
    prim = st.GetPrimAtPath(p)
    if prim:
        UsdGeom.Imageable(prim).GetVisibilityAttr().Set("inherited")
vp.camera_path = before_cam
st.SetEditTarget(st.GetRootLayer())
print("saved", {out!r}, "camera back to", before_cam)
"""


def gui(only, wait=int(os.environ.get("REPORT_WAIT", "700"))):
    os.makedirs(OUT, exist_ok=True)
    for name, (eye, target, focal) in views().items():
        if only and name not in only:
            continue
        code = GUI_SHOT.format(roofs=ROOFS, cut=name.startswith("cut_") or name == "top_cut", focal=focal,
                               eye=tuple(eye), target=tuple(target), res=RES, wait=wait,
                               out=os.path.join(OUT, f"{name}.png"))
        subprocess.run([sys.executable, ISC, "-"], input=code, text=True, check=True, timeout=1800)


def headless(only):
    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True, "renderer": "PathTracing", "width": RES[0], "height": RES[1]})
    import omni.usd
    from pxr import UsdGeom
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import render_lib as RL
    sub = RL.configure(16, 64)
    omni.usd.get_context().open_stage(os.path.join(ROOT, "scenes", "cotton_candy_booth.usda"))
    for _ in range(30):
        app.update()
    stage = omni.usd.get_context().get_stage()
    stage.SetEditTarget(stage.GetSessionLayer())
    cam = RL.Camera(stage, RES, sub)
    for name, (eye, target, focal) in views().items():
        if only and name not in only:
            continue
        for p in ROOFS:
            UsdGeom.Imageable(stage.GetPrimAtPath(p)).GetVisibilityAttr().Set(
                "invisible" if name.startswith("cut_") or name == "top_cut" else "inherited")
        cam.shot(os.path.join(OUT, f"{name}.png"), eye, target, focal)
    os._exit(0)


if __name__ == "__main__":
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--print" in sys.argv:
        print(json.dumps(views(), indent=1))
    elif "--gui" in sys.argv:
        gui(only)
    else:
        headless(only)
