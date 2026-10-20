"""Compose the cotton candy booth stage: paving, booth, floss machine, fairground context and evening lighting.

Writes scenes/cotton_candy_booth.usda (relative references only; /World is the default prim; Z up; m). Frame = booth
frame B of site/layout.py. Context (string lights, neighbour stalls) and the lighting are ILLUSTRATIVE.

Run: $E scenes/build_scene.py
"""

import math
import os
import sys

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "site"))
import layout as L  # noqa: E402
import params as Pm  # noqa: E402
from assets.common.kit import Kit, sdt  # noqa: E402

g = Pm.get
OUT = os.path.join(ROOT, "scenes", "cotton_candy_booth.usda")


def xf(stage, path, ref=None, pos=(0, 0, 0), yaw=0.0, inst=False):
    x = UsdGeom.Xform.Define(stage, path)
    if ref:
        x.GetPrim().GetReferences().AddReference(ref)
        x.GetPrim().SetInstanceable(inst)
    x.AddTranslateOp().Set(Gf.Vec3d(*map(float, pos)))
    if yaw:
        x.AddRotateZOp().Set(float(yaw))
    return x


def state(prim, **kv):
    for k, v in kv.items():
        prim.CreateAttribute(f"state:{k}", Sdf.ValueTypeNames.String, custom=True).Set(v)


def context(st):
    """Paving, two light poles with a string of bulbs, two neighbour stalls (ILLUSTRATIVE)."""
    k = Kit()
    k.quad("Paving", (0, -1.0, 0.0), (0, 0, 1), (0, 1, 0), 60.0, 60.0, uv=(0, 0, 60.0 / 2.0 * 2.0, 60.0 / 2.0 * 2.0))  # meshkit divides UVs by TILE_M (2 m)
    poles = [(-2.6, -2.6), (2.6, -2.6)]
    for x, y in poles:
        k.cyl("PoleDark", (x, y, 0.0), (x, y, 3.4), 0.05)
        k.cyl("PoleDark", (x, y, 0.0), (x, y, 0.05), 0.25)
    anchors = [(-2.6, -2.6, 3.3), (-1.0, -1.25, 2.25), (1.0, -1.25, 2.25), (2.6, -2.6, 3.3)]
    bulbs = []
    for (x0, y0, z0), (x1, y1, z1) in zip(anchors[:-1], anchors[1:]):
        n = 7
        for i in range(n + 1):
            t = i / n
            sag = 0.25 * math.sin(math.pi * t)
            p = (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, z0 + (z1 - z0) * t - sag)
            if i < n:
                q = (x0 + (x1 - x0) * (t + 1 / n), y0 + (y1 - y0) * (t + 1 / n),
                     z0 + (z1 - z0) * (t + 1 / n) - 0.25 * math.sin(math.pi * (t + 1 / n)))
                k.cyl("KnobBlack", p, q, 0.003, seg=6)
            k.sphere("BulbWarm", (p[0], p[1], p[2] - 0.05), 0.03, seg=12)
            bulbs.append((p[0], p[1], p[2] - 0.05))
    # neighbour stalls: striped tarp roof on four poles, a counter (ILLUSTRATIVE, background)
    for cx in (-4.2, 4.2):
        for dx in (-1.4, 1.4):
            for dy in (-1.1, 1.1):
                k.cyl("StainlessSatin", (cx + dx, 0.6 + dy, 0), (cx + dx, 0.6 + dy, 2.3), 0.025)
        for i in range(8):
            mat = "TarpRed" if i % 2 == 0 else "TarpStripeWhite"
            k.box(mat, (cx - 1.5 + (i + 0.5) * 3.0 / 8, 0.6, 2.35), (3.0 / 8, 2.5, 0.02))
        k.box("TarpRed", (cx, -0.62, 2.2), (3.0, 0.02, 0.28))
        k.box("SprucePaintedWhite", (cx, -0.35, 0.5), (2.8, 0.5, 1.0))
    k.write(st, "/World/Context")
    return bulbs


def lights(st, bulbs):
    UsdGeom.Xform.Define(st, "/World/Lights")
    dome = UsdLux.DomeLight.Define(st, "/World/Lights/DuskSky")
    dome.CreateTextureFileAttr("../assets/sky/sky_nosun.hdr")
    dome.CreateIntensityAttr(220.0)
    dome.CreateColorAttr(Gf.Vec3f(0.55, 0.62, 0.95))
    sun = UsdLux.DistantLight.Define(st, "/World/Lights/LowSun")
    sun.CreateIntensityAttr(600.0)
    sun.CreateAngleAttr(0.53)
    sun.CreateColorAttr(Gf.Vec3f(1.0, 0.62, 0.38))
    x = UsdGeom.Xformable(sun)
    x.AddRotateZOp().Set(220.0)
    x.AddRotateXOp().Set(82.0)                      # ~8 deg above the horizon, from the south-west
    inside = UsdLux.RectLight.Define(st, "/World/Lights/BoothLED")
    inside.CreateWidthAttr(1.8)
    inside.CreateHeightAttr(0.06)
    inside.CreateIntensityAttr(9000.0)
    inside.CreateColorAttr(Gf.Vec3f(1.0, 0.88, 0.72))
    UsdGeom.Xformable(inside).AddTranslateOp().Set(Gf.Vec3d(0, -0.85, L.EAVE_Z - 0.05))
    spot = UsdLux.SphereLight.Define(st, "/World/Lights/MachineSpot")
    spot.CreateRadiusAttr(0.04)
    spot.CreateIntensityAttr(25000.0)
    spot.CreateColorAttr(Gf.Vec3f(1.0, 0.9, 0.8))
    UsdGeom.Xformable(spot).AddTranslateOp().Set(Gf.Vec3d(L.MACHINE_XY[0], L.MACHINE_XY[1] + 0.2, L.EAVE_Z - 0.15))
    for name, pos, col, inten in (("FairFloodLeft", (-2.2, -3.6, 3.2), (1.0, 0.80, 0.60), 2.5e5),
                                  ("FairFloodRight", (2.6, -3.2, 3.0), (1.0, 0.70, 0.75), 2.0e5)):
        f = UsdLux.SphereLight.Define(st, f"/World/Lights/{name}")       # light of the neighbouring rides/stalls
        f.CreateRadiusAttr(0.25)
        f.CreateIntensityAttr(inten)
        f.CreateColorAttr(Gf.Vec3f(*col))
        UsdGeom.Xformable(f).AddTranslateOp().Set(Gf.Vec3d(*pos))
    for i, p in enumerate(bulbs[::3]):
        b = UsdLux.SphereLight.Define(st, f"/World/Lights/Bulb{i:02d}")
        b.CreateRadiusAttr(0.03)
        b.CreateIntensityAttr(9000.0)
        b.CreateColorAttr(Gf.Vec3f(1.0, 0.75, 0.45))
        UsdGeom.Xformable(b).AddTranslateOp().Set(Gf.Vec3d(*p))


def build():
    if os.path.exists(OUT):
        os.remove(OUT)
    st = Usd.Stage.CreateNew(OUT)
    UsdGeom.SetStageUpAxis(st, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(st, 1.0)
    st.SetMetadata("comment", "Generated by scenes/build_scene.py - research twin, edit the builders, not this file.")
    world = UsdGeom.Xform.Define(st, "/World")
    st.SetDefaultPrim(world.GetPrim())
    sdt(world.GetPrim(), twin="Cotton Candy Booth Twin",
        disclaimer="Generic fairground booth reconstructed from public sources; machine modelled on a commercial "
                   "floss machine, no brand. See site/params.py for the status of every number.",
        frame="booth frame B: origin on the paving at the booth centre, +y sales front -> back wall, z up, m")
    bulbs = context(st)
    booth = xf(st, "/World/Booth", "../assets/booth/usd/booth.usda")
    sdt(booth.GetPrim(), semanticAnnotation="CottonCandyBooth", footprintM2=g("booth_width") * g("booth_depth"))
    state(booth.GetPrim(), flap="open", lighting="on")
    mx, my = L.MACHINE_XY
    machine = xf(st, "/World/Booth/Machine", "../assets/machine/usd/floss_machine.usda", (mx, my, L.TABLE_Z),
                 yaw=L.MACHINE_YAW)
    sdt(machine.GetPrim(), semanticAnnotation="CottonCandyMachine", placement="site/layout.py MACHINE_XY on TABLE_Z")
    state(machine.GetPrim(), machine_phase="off", motor_switch="off", heat_switch="off", lock_handles="unlocked")
    lights(st, bulbs)
    st.Save()
    print("wrote", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    build()
