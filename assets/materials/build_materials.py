"""Twin material library: the LabAutomationTwin library (reused, unchanged) plus industrial / port materials.

Writes assets/materials/twin_materials.usda (/Looks/<Name>) and assets/materials/textures/*.png. Builders bind through
assets/common/kit.py (meshkit pointed at this library).

Run: ~/Documents/LabAutomationTwin/env_cad/bin/python assets/materials/build_materials.py
"""

import importlib.util
import os

import numpy as np
from pxr import Gf, Usd, UsdGeom

HERE = os.path.dirname(os.path.abspath(__file__))
LAT = os.path.expanduser("~/Documents/LabAutomationTwin")
spec = importlib.util.spec_from_file_location("lab_mats", os.path.join(LAT, "assets", "materials", "build_materials.py"))
LM = importlib.util.module_from_spec(spec)
spec.loader.exec_module(LM)
LM.TEX = os.path.join(HERE, "textures")          # write the reused textures here, never into the lab twin
OUT = os.path.join(HERE, "twin_materials.usda")

TILE_M = dict(LM.TILE_M)
TILE_M.update({"Paving": 2.0, "SpruceOiled": 1.2, "SprucePaintedPink": 1.2, "SprucePaintedWhite": 1.2,
               "CladdingWhite": 2.0, "CladdingGrey": 2.0, "Asphalt": 6.0, "HallFloor": 8.0, "Grass": 8.0,
               "QuayConcrete": 6.0, "RoofMembrane": 6.0})

PBR = {  # OmniPBR: (diffuse, roughness, metallic, extra)
    "SteelPaintGrey": ((0.60, 0.62, 0.64), 0.50, 0.0, {}),        # structural steel, light grey
    "SteelPaintWhite": ((0.82, 0.83, 0.84), 0.45, 0.0, {}),
    "SteelPaintDark": ((0.16, 0.17, 0.18), 0.50, 0.0, {}),
    "CraneYellow": ((0.93, 0.68, 0.04), 0.40, 0.0, {}),
    "SafetyYellow": ((0.95, 0.75, 0.05), 0.45, 0.0, {}),
    "PaintOrange": ((0.88, 0.36, 0.05), 0.42, 0.0, {}),
    "PaintBlue": ((0.07, 0.22, 0.48), 0.42, 0.0, {}),
    "RailingRed": ((0.75, 0.07, 0.05), 0.45, 0.0, {}),
    "CastPrimerGrey": ((0.34, 0.36, 0.38), 0.62, 0.0, {}),        # castings in primer
    "MachinedSteel": ((0.70, 0.70, 0.70), 0.25, 1.0, {}),
    "NacelleWhite": ((0.86, 0.87, 0.88), 0.35, 0.0, {}),          # GFRP canopy / painted housings
    "GeneratorGrey": ((0.72, 0.74, 0.76), 0.38, 0.0, {}),
    "MagnetDark": ((0.12, 0.12, 0.13), 0.30, 0.6, {}),
    "CopperWinding": ((0.72, 0.40, 0.22), 0.30, 1.0, {}),
    "CabinetGrey": ((0.80, 0.80, 0.78), 0.40, 0.0, {}),
    "WalkwayGreen": ((0.13, 0.36, 0.22), 0.55, 0.0, {}),          # walkway paint (photos, vbdoiz23)
    "LineYellow": ((0.93, 0.74, 0.05), 0.50, 0.0, {}),
    "LineWhite": ((0.90, 0.90, 0.88), 0.50, 0.0, {}),
    "Water": ((0.06, 0.13, 0.15), 0.05, 0.0, {}),
    "HullBlue": ((0.07, 0.15, 0.30), 0.45, 0.0, {}),
    "HullRed": ((0.50, 0.08, 0.06), 0.55, 0.0, {}),
    "ShipWhite": ((0.88, 0.88, 0.86), 0.45, 0.0, {}),
    "BrickRed": ((0.48, 0.22, 0.17), 0.80, 0.0, {}),
    "OfficeFacade": ((0.70, 0.71, 0.72), 0.50, 0.0, {}),
    "Tarpaulin": ((0.92, 0.92, 0.90), 0.75, 0.0, {}),
    "HighBay": ((0.95, 0.95, 0.95), 0.5, 0.0, {"emissive": ((1.0, 0.97, 0.92), 6000.0)}),
    # people, vehicles (process animation, operational site)
    "Skin": ((0.72, 0.52, 0.42), 0.55, 0.0, {}),
    "WorkwearNavy": ((0.06, 0.09, 0.18), 0.80, 0.0, {}),
    "HiVisYellow": ((0.86, 0.95, 0.10), 0.60, 0.0, {}),
    "HiVisOrange": ((0.98, 0.42, 0.05), 0.60, 0.0, {}),
    "Reflective": ((0.85, 0.86, 0.86), 0.20, 0.5, {}),
    "HelmetWhite": ((0.93, 0.93, 0.91), 0.25, 0.0, {}),
    "BootBlack": ((0.05, 0.05, 0.05), 0.60, 0.0, {}),
    "VehicleRed": ((0.62, 0.05, 0.05), 0.30, 0.0, {}),
    "VehicleGreen": ((0.09, 0.32, 0.18), 0.35, 0.0, {}),
    "TruckWhite": ((0.90, 0.91, 0.92), 0.25, 0.0, {}),
    "Tire": ((0.03, 0.03, 0.03), 0.85, 0.0, {}),
    "SteelRope": ((0.45, 0.45, 0.46), 0.35, 0.9, {}),
    "SlingRed": ((0.75, 0.10, 0.08), 0.70, 0.0, {}),
    "SlingGreen": ((0.15, 0.55, 0.20), 0.70, 0.0, {}),
    # offshore: installation vessel (reference/wtiv photos), foundations, towers, blades (ILLUSTRATIVE colours)
    "HullGreen": ((0.16, 0.48, 0.03), 0.40, 0.0, {}),
    "HullBlack": ((0.025, 0.025, 0.028), 0.55, 0.0, {}),
    "LegDark": ((0.07, 0.08, 0.09), 0.45, 0.3, {}),
    "TowerGrey": ((0.66, 0.67, 0.66), 0.35, 0.0, {}),            # RAL 7035-like offshore tower coating
    "TPYellow": ((0.80, 0.55, 0.02), 0.45, 0.0, {}),             # transition piece (RAL 1023-like)
    "BladeWhite": ((0.80, 0.80, 0.78), 0.25, 0.0, {}),
    "MonopileGrey": ((0.20, 0.21, 0.22), 0.55, 0.2, {}),
    # ---- cotton candy booth (ILLUSTRATIVE colours from the Gold Medal manual photos and fair stands)
    "PanelBlue": ((0.05, 0.16, 0.52), 0.35, 0.0, {}),             # machine front label
    "DialPink": ((0.85, 0.12, 0.42), 0.40, 0.0, {}),
    "KnobBlack": ((0.03, 0.03, 0.03), 0.35, 0.0, {}),
    "RockerGreenLit": ((0.15, 0.70, 0.25), 0.30, 0.0, {"emissive": ((0.2, 1.0, 0.3), 80.0)}),
    "LeverRed": ((0.78, 0.05, 0.04), 0.35, 0.0, {}),
    "HeadCastGrey": ((0.18, 0.19, 0.20), 0.55, 0.3, {}),          # anodized / coated spinner head
    "LeatherTan": ((0.62, 0.38, 0.22), 0.65, 0.0, {}),
    "Brass": ((0.78, 0.60, 0.30), 0.30, 1.0, {}),
    "AluSpun": ((0.80, 0.81, 0.83), 0.22, 1.0, {}),
    "ScreenWhite": ((0.92, 0.92, 0.90), 0.60, 0.0, {}),
    "FlossPink": ((0.98, 0.62, 0.80), 0.95, 0.0, {"emissive": ((1.0, 0.75, 0.88), 2.0)}),
    "FlossBlue": ((0.55, 0.78, 0.98), 0.95, 0.0, {"emissive": ((0.7, 0.85, 1.0), 2.0)}),
    "FlossWhite": ((0.96, 0.96, 0.95), 0.95, 0.0, {}),
    "SugarPink": ((0.96, 0.55, 0.72), 0.80, 0.0, {}),
    "SugarBlue": ((0.40, 0.62, 0.95), 0.80, 0.0, {}),
    "SugarWhite": ((0.93, 0.93, 0.92), 0.80, 0.0, {}),
    "PineStick": ((0.86, 0.74, 0.55), 0.70, 0.0, {}),
    "GlossRed": ((0.72, 0.03, 0.03), 0.20, 0.0, {}),               # extinguisher body
    "BulbWarm": ((1.0, 0.85, 0.55), 0.40, 0.0, {"emissive": ((1.0, 0.78, 0.45), 30000.0)}),
    "LedWarm": ((1.0, 0.92, 0.80), 0.40, 0.0, {"emissive": ((1.0, 0.90, 0.75), 8000.0)}),
    "SignPink": ((1.0, 0.45, 0.70), 0.40, 0.0, {"emissive": ((1.0, 0.40, 0.70), 3000.0)}),
    "CanisterBlue": ((0.15, 0.35, 0.75), 0.45, 0.0, {}),
    "TubLid": ((0.90, 0.90, 0.88), 0.45, 0.0, {}),
    "CartonWhite": ((0.93, 0.92, 0.89), 0.65, 0.0, {}),            # coated paperboard gable-top carton
    "SpongeYellow": ((0.92, 0.78, 0.25), 0.90, 0.0, {}),
    "ScourGreen": ((0.15, 0.45, 0.20), 0.85, 0.0, {}),
    "PoleDark": ((0.10, 0.11, 0.12), 0.45, 0.4, {}),
    "TarpRed": ((0.70, 0.08, 0.08), 0.75, 0.0, {}),
    "TarpStripeWhite": ((0.92, 0.92, 0.90), 0.75, 0.0, {}),
    "BagFilm": ((0.97, 0.82, 0.90), 0.15, 0.0, {}),
}
TEXTURED = {  # (albedo png, roughness, metallic)
    "CladdingWhite": ("cladding_white.png", 0.42, 0.2),
    "CladdingGrey": ("cladding_grey.png", 0.45, 0.2),
    "Asphalt": ("asphalt.png", 0.85, 0.0),
    "HallFloor": ("hall_floor.png", 0.40, 0.0),
    "Grass": ("grass.png", 0.95, 0.0),
    "QuayConcrete": ("quay_concrete.png", 0.85, 0.0),
    "RoofMembrane": ("roof.png", 0.75, 0.0),
    "Paving": ("paving.png", 0.80, 0.0),
    "SpruceOiled": ("spruce_oiled.png", 0.45, 0.0),
    "SprucePaintedPink": ("spruce_pink.png", 0.55, 0.0),
    "SprucePaintedWhite": ("spruce_white.png", 0.55, 0.0),
}


def make_site_textures():
    rng = np.random.default_rng(7)
    n = 512
    yy, xx = np.mgrid[0:n, 0:n]
    # trapezoidal sheet: 4 ribs per 2 m tile (u = horizontal), shading from the rib slopes
    ph = (xx / n * 4) % 1.0
    shade = np.where(ph < 0.12, 0.84, np.where(ph < 0.2, 1.04, np.where(ph < 0.62, 1.0, np.where(ph < 0.7, 0.9, 1.0))))
    for name, base in (("cladding_white.png", (0.86, 0.87, 0.88)), ("cladding_grey.png", (0.46, 0.48, 0.51))):
        g = shade * (1 + 0.01 * LM._tileable_lowfreq(rng, n, 8))
        LM._save(name, (np.stack([g * base[0], g * base[1], g * base[2]], -1)) ** (1 / 2.2))
    a = 0.13 + 0.02 * LM._tileable_lowfreq(rng, n, 12) + 0.025 * rng.normal(size=(n, n))
    LM._save("asphalt.png", np.clip(np.stack([a, a, a * 1.02], -1), 0, 1) ** (1 / 2.2))
    f = 0.70 + 0.03 * LM._tileable_lowfreq(rng, n, 6) + 0.012 * rng.normal(size=(n, n))
    f[:, :2] = 0.55                                          # saw-cut joints every 8 m tile edge
    f[:2, :] = 0.55
    LM._save("hall_floor.png", np.stack([f * 0.98, f, f * 1.01], -1) ** (1 / 2.2))
    g = 0.5 + 0.08 * LM._tileable_lowfreq(rng, n, 10) + 0.05 * rng.normal(size=(n, n))
    LM._save("grass.png", np.clip(np.stack([0.24 * g, 0.30 * g, 0.15 * g], -1) * 1.7, 0, 1))
    q = 0.40 + 0.04 * LM._tileable_lowfreq(rng, n, 10) + 0.025 * rng.normal(size=(n, n))
    q[:, :3] = 0.30
    q[:3, :] = 0.30
    LM._save("quay_concrete.png", np.stack([q, q, q * 0.98], -1) ** (1 / 2.2))
    r = 0.56 + 0.02 * LM._tileable_lowfreq(rng, n, 6) + 0.01 * rng.normal(size=(n, n))
    r[:, ::64] = 0.48
    LM._save("roof.png", np.stack([r, r, r * 1.01], -1) ** (1 / 2.2))
    # concrete pavers 20 x 10 cm in running bond, 2 m tile (ILLUSTRATIVE)
    p = 0.42 + 0.03 * LM._tileable_lowfreq(rng, n, 10) + 0.03 * rng.normal(size=(n, n))
    cell_y = (yy / n * 20).astype(int)
    shift = (cell_y % 2) * 0.5
    xc = (xx / n * 10 + shift) % 1.0
    yc = (yy / n * 20) % 1.0
    tone = 0.9 + 0.2 * np.random.default_rng(3).random((20, 11))[cell_y, ((xx / n * 10 + shift).astype(int)) % 11]
    p = p * tone
    p[(xc < 0.03) | (yc < 0.06)] = 0.18
    LM._save("paving.png", np.clip(np.stack([p * 1.0, p * 0.98, p * 0.95], -1), 0, 1) ** (1 / 2.2))
    # spruce 3-ply panel: grain along u, boards 10 cm wide, 1.2 m tile
    grain = 0.5 + 0.5 * np.sin(xx / n * 1.2 * 2 * np.pi * 9 + 3.0 * LM._tileable_lowfreq(rng, n, 6))
    board = np.random.default_rng(5).random(12)[(yy / n * 12).astype(int)]
    w = 0.80 + 0.06 * grain + 0.05 * board + 0.02 * rng.normal(size=(n, n))
    LM._save("spruce_oiled.png", np.clip(np.stack([w * 0.86, w * 0.66, w * 0.42], -1), 0, 1))
    for name, col in (("spruce_pink.png", (0.96, 0.62, 0.78)), ("spruce_white.png", (0.95, 0.94, 0.91))):
        v = 0.975 + 0.012 * grain + 0.006 * board          # paint hides most of the grain
        LM._save(name, np.clip(np.stack([v * col[0], v * col[1], v * col[2]], -1), 0, 1))


def hashed(name):
    """Copy textures/<name> to textures/<stem>_<sha1[:8]>.png and return that name.

    Isaac Sim / RTX caches textures by path: a texture regenerated under the same file name keeps showing stale
    (even foreign) content. A content-hashed name gives every new content a new path.
    """
    import hashlib
    import shutil
    src = os.path.join(LM.TEX, name)
    with open(src, "rb") as f:
        h = hashlib.sha1(f.read()).hexdigest()[:8]
    stem, ext = os.path.splitext(name)
    out = f"{stem}_{h}{ext}"
    if not os.path.exists(os.path.join(LM.TEX, out)):
        shutil.copy(src, os.path.join(LM.TEX, out))
    return out


def define_site(stage):
    names = []
    F, C3, B = LM.F, LM.C3, LM.B
    for name, (diff, rough, metal, extra) in PBR.items():
        mat, sh = LM._shader(stage, f"/Looks/{name}", "OmniPBR")
        LM._set(sh, "diffuse_color_constant", C3, Gf.Vec3f(*diff))
        LM._set(sh, "reflection_roughness_constant", F, rough)
        LM._set(sh, "metallic_constant", F, metal)
        if "emissive" in extra:
            col, inten = extra["emissive"]
            LM._set(sh, "enable_emission", B, True)
            LM._set(sh, "emissive_color", C3, Gf.Vec3f(*col))
            LM._set(sh, "emissive_intensity", F, inten)
        names.append(name)
    for name, (alb, rough, metal) in TEXTURED.items():
        mat, sh = LM._shader(stage, f"/Looks/{name}", "OmniPBR")
        LM._set(sh, "diffuse_texture", LM.A, LM.tex(hashed(alb)))
        LM._set(sh, "reflection_roughness_constant", F, rough)
        LM._set(sh, "metallic_constant", F, metal)
        names.append(name)
    # clear thin-walled polyethylene floss bubble (PolystyreneClear of the lab library is a solid, mirror-like glass)
    mat, sh = LM._shader(stage, "/Looks/BubbleClearPE", "OmniGlass")
    LM._set(sh, "glass_color", C3, Gf.Vec3f(0.97, 0.98, 1.0))
    LM._set(sh, "glass_ior", F, 1.04)
    LM._set(sh, "thin_walled", B, True)
    LM._set(sh, "frosting_roughness", F, 0.0)
    names.append("BubbleClearPE")
    return names


def main():
    LM.make_textures()
    make_site_textures()
    if os.path.exists(OUT):
        os.remove(OUT)
    stage = Usd.Stage.CreateNew(OUT)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    stage.SetMetadata("comment", "Generated by assets/materials/build_materials.py - edit the script, not this file.")
    names = LM.define(stage) + define_site(stage)
    stage.SetDefaultPrim(stage.GetPrimAtPath("/Looks"))
    stage.GetRootLayer().Save()
    print(f"wrote {OUT}: {len(names)} materials")


if __name__ == "__main__":
    main()
