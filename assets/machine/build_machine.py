"""Floss machine asset: a Gold Medal Econo Floss 3017-style cotton candy machine (generic lettering, no brand).

Frame: origin on the support surface at the centre of the feet footprint; +y towards the controls (operator side),
z up, metres. Dimensions from site/params.py (statuses there); photo-scaled parts follow the export manual photos
(GM_MAN_EXP p5/p20/p22) with the floss band diameter as scale bar. Part prims under /Machine:
  Cabinet (feet, cabinet, louvres, front panel, labels), Controls (MotorMasterSwitch, HeatSwitch, HeatControlKnob),
  LockHandles, BellHousing, SpinnerHead (slip rings, band with slots, cap, floaters), Pan, Stabilizer, Bubble.
Writes assets/machine/usd/floss_machine.usda and data/asset_envelopes.json (measured envelopes for site/checks.py).

Run: $E assets/machine/build_machine.py
"""

import math
import os
import sys

import numpy as np
from pxr import Sdf, Usd, UsdGeom

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "site"))
import params as Pm  # noqa: E402
import provenance  # noqa: E402
from assets.common.decals import text_png  # noqa: E402
from assets.common.kit import Kit, new_asset, sdt  # noqa: E402

g = Pm.get
OUT = os.path.join(ROOT, "assets", "machine", "usd", "floss_machine.usda")
TEX = os.path.join(ROOT, "assets", "machine", "usd", "textures")

FEET = g("m_feet_height")
CW, CD, CH = g("m_cabinet_width"), g("m_cabinet_depth"), g("m_cabinet_height")
CAB_TOP = FEET + CH
RIM = g("m_overall_height")                     # pan rim = overall height with pan (SOURCED)
PAN_H = g("pan_height")
PAN_BOTTOM = RIM - PAN_H                         # == CAB_TOP by construction of m_cabinet_height (DERIVED)
R_IN, R_OUT, WALL = g("pan_inner_diameter") / 2, g("pan_outer_diameter") / 2, g("pan_wall_t")
BELL_R, BELL_H = g("m_bell_diameter") / 2, g("m_bell_height")
HEAD_R, BAND_H, CAP_H = g("head_band_diameter") / 2, g("head_band_height"), g("head_cap_height")
SLIP_H = 0.028                                   # ILLUSTRATIVE: slip-ring column between bell and head (photo p22)
HEAD_BASE = CAB_TOP + BELL_H + SLIP_H + 0.008    # lower head plate on top of the slip rings
BAND_C = HEAD_BASE + BAND_H / 2                  # band centre = the hot zone used by the heat-clearance check


def partial_lathe(k, mat, profile, a0, a1, seg=48):
    """Surface of revolution about z over the angle range [a0, a1] (rad); profile [(r, z)] bottom -> top."""
    pr = np.asarray(profile, float)
    th = np.linspace(a0, a1, seg + 1)
    P, N, T = [], [], []
    tang = np.gradient(pr, axis=0)
    for i, (r, z) in enumerate(pr):
        tr, tz = tang[i]
        nr, nz = tz, -tr
        ln = math.hypot(nr, nz) or 1.0
        for t in th:
            P.append((r * math.cos(t), r * math.sin(t), z))
            N.append((nr / ln * math.cos(t), nr / ln * math.sin(t), nz / ln))
    m = len(th)
    for i in range(len(pr) - 1):
        for j in range(m - 1):
            a, b, c, d = i * m + j, i * m + j + 1, (i + 1) * m + j, (i + 1) * m + j + 1
            T += [(a, b, d), (a, d, c)]
    k.add(mat, np.array(P), np.array(N), np.array(T))


def cabinet(k):
    for sx in (-1, 1):
        for sy in (-1, 1):
            k.cyl("RubberBlack", (sx * (CW / 2 - 0.035), sy * (CD / 2 - 0.035), 0.0),
                  (sx * (CW / 2 - 0.035), sy * (CD / 2 - 0.035), FEET), 0.014)
    k.rbox("StainlessBrushed", (0, 0, FEET + CH / 2), (CW, CD, CH), r=0.006)
    # side louvres (photo p20: horizontal slots on the side walls)
    for sx in (-1, 1):
        for i in range(5):
            z = FEET + 0.05 + 0.022 * i
            k.box("KnobBlack", (sx * (CW / 2 + 0.0004), 0.02, z), (0.001, 0.15, 0.006))
    k.collide((0, 0, FEET + CH / 2), (CW, CD, CH), name="Cabinet")
    # blue front panel with generic lettering (ANALOGUE of the manual photos; no brand)
    y = CD / 2 + 0.0015
    k.box("PanelBlue", (0, y, FEET + CH * 0.52), (CW * 0.94, 0.003, CH * 0.86))
    png = text_png(os.path.join(TEX, "panel_title.png"), ["COTTON CANDY"], size=(1024, 160),
                   bg=(14, 41, 133, 255), fg=(255, 255, 255, 255))
    k.decal(png, (0.035, y + 0.0012, FEET + CH * 0.86), (0, 1, 0), (0, 0, 1), 0.24, 0.0375)
    png = text_png(os.path.join(TEX, "panel_labels.png"),
                   [("MOTOR   HEAT        HEAT ADJUSTMENT", 1.0, (255, 255, 255, 255))], size=(1024, 96),
                   bg=(14, 41, 133, 255))
    k.decal(png, (-0.02, y + 0.0012, FEET + CH * 0.20), (0, 1, 0), (0, 0, 1), 0.30, 0.028)
    warn = text_png(os.path.join(TEX, "panel_warning.png"),
                    [("WARNING", 1.2, (200, 20, 20, 255)), "Floss head rotates at high speed.",
                     "Keep hands and face clear. Wear eye protection."],
                    size=(512, 384), bg=(245, 245, 240, 255), bold=False)
    k.decal(warn, (CW * 0.33, y + 0.0012, FEET + CH * 0.50), (0, 1, 0), (0, 0, 1), 0.085, 0.064)


def controls(k):
    y = CD / 2 + 0.003
    zc = FEET + CH * 0.50
    for name, dz in (("MotorMasterSwitch", 0.03), ("HeatSwitch", -0.03)):
        with k.at((-CW * 0.33, y, zc + dz)):
            k.rbox("KnobBlack", (0, 0.003, 0), (0.036, 0.006, 0.052), r=0.003)
            k.rbox("RockerGreenLit", (0, 0.010, 0), (0.026, 0.010, 0.040), r=0.003)
            k.frame(name, (0, 0.015, 0))
    with k.at((-0.04, y, zc)):
        k.disk("DialPink", (0, 0.0006, 0), 0.052, normal=(0, 1, 0), r_in=0.034, seg=48)
        k.cyl("KnobBlack", (0, 0, 0), (0, 0.022, 0), 0.026, seg=36, r_edge=0.003)
        k.cyl("KnobBlack", (0, 0.022, 0), (0, 0.030, 0), 0.020, seg=36, r_edge=0.002)
        k.box("ScreenWhite", (0, 0.0305, 0.012), (0.003, 0.001, 0.012))       # pointer mark
        k.frame("HeatControlKnob", (0, 0.03, 0))


def lock_handles(k):
    for sx, name in ((-1, "LockNGoHandleLeft"), (1, "LockNGoHandleRight")):
        x = sx * (CW / 2 + 0.012)
        with k.at((x, 0.04, FEET + CH * 0.55)):
            k.cyl("KnobBlack", (-sx * 0.012, 0, 0), (sx * 0.012, 0, 0), 0.022)            # star hub (simplified)
            k.rbox("LeverRed", (sx * 0.018, -0.07, 0), (0.012, 0.14, 0.024), r=0.004)     # UNLOCKED: lever forward
            k.frame(name, (sx * 0.018, 0, 0))
        k.collide((x + sx * 0.012, -0.03, FEET + CH * 0.55), (0.04, 0.16, 0.05), name=name)


def bell_and_head(kb, kh):
    kb.cyl("AluSpun", (0, 0, CAB_TOP), (0, 0, CAB_TOP + BELL_H), BELL_R, seg=48)
    kb.disk("AluSpun", (0, 0, CAB_TOP + BELL_H), BELL_R, seg=48)
    z = CAB_TOP + BELL_H
    # slip rings (brass) with phenolic spacers (photo p22, items 20-23)
    kh.cyl("KnobBlack", (0, 0, z), (0, 0, z + SLIP_H), 0.028, seg=32)
    for zz in (z + 0.004, z + 0.016):
        kh.cyl("Brass", (0, 0, zz), (0, 0, zz + 0.008), 0.042, seg=40, r_edge=0.001)
    kh.cyl("HeadCastGrey", (0, 0, z + SLIP_H), (0, 0, HEAD_BASE), 0.074, seg=48, r_edge=0.002)
    # floss band with slanted slots (36 slots, 35 deg, 3 mm; ANALOGUE photo count)
    kh.cyl("HeadCastGrey", (0, 0, HEAD_BASE), (0, 0, HEAD_BASE + BAND_H), HEAD_R, seg=72)
    n, ang = int(g("head_slot_count")), math.radians(g("head_slot_angle"))
    for i in range(n):
        t = 2 * math.pi * i / n
        with kh.at((HEAD_R * math.cos(t), HEAD_R * math.sin(t), BAND_C), R=np.array(
                [[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1]])):
            Rs = np.array([[1, 0, 0], [0, math.cos(ang), -math.sin(ang)], [0, math.sin(ang), math.cos(ang)]])
            with kh.at((0, 0, 0), R=Rs):
                kh.box("KnobBlack", (0.0004, 0, 0), (0.0012, g("head_slot_width"), BAND_H * 0.75))
    # conical spinner cap with the sugar inlet on top
    top = HEAD_BASE + BAND_H
    kh.lathe("HeadCastGrey", [(HEAD_R * 0.98, top), (HEAD_R * 0.80, top + 0.012), (0.045, top + CAP_H * 0.7),
                              (g("head_cap_top_diameter") / 2, top + CAP_H * 0.85),
                              (g("head_cap_top_diameter") / 2, top + CAP_H)], seg=64)
    kh.disk("KnobBlack", (0, 0, top + CAP_H * 0.8), g("head_cap_top_diameter") / 2 * 0.95, seg=32)   # inlet shadow
    # two leather floaters on screws at the cap edge
    for t in (0.0, math.pi):
        c, s = math.cos(t), math.sin(t)
        with kh.at((HEAD_R * 0.86 * c, HEAD_R * 0.86 * s, top + 0.008), yaw=math.degrees(t)):
            kh.box("LeatherTan", (0.024, 0, 0.002), (0.040, 0.016, 0.003))
            kh.cyl("StainlessSatin", (0, 0, 0), (0, 0, 0.008), 0.004)
    kh.frame("BandCentre", (0, 0, BAND_C))


def pan(kp, ks):
    t = WALL
    hole = BELL_R + 0.012
    prof = [(hole, PAN_BOTTOM + t), (R_IN - 0.02, PAN_BOTTOM + t), (R_IN, PAN_BOTTOM + 0.02), (R_IN, RIM - 0.006),
            (R_IN + 0.002, RIM - 0.001), (R_OUT, RIM - 0.001), (R_OUT, RIM - 0.008), (R_IN + t, RIM - 0.012),
            (R_IN + t, PAN_BOTTOM + 0.02), (R_IN - 0.02, PAN_BOTTOM), (hole, PAN_BOTTOM)]
    kp.lathe("AluSpun", prof, seg=96, smooth=False)
    kp.collide((0, 0, PAN_BOTTOM + 0.005), (2 * R_OUT, 2 * R_OUT, 0.01), name="PanFloor")
    # floss stabilizer: white plastic screening hung from rim clips, air gap to the wall
    rs = R_IN - g("stabilizer_gap")
    ks.lathe("ScreenWhite", [(rs, RIM - g("stabilizer_height")), (rs, RIM - 0.004)], seg=96, smooth=False)
    for i in range(int(g("stabilizer_clips"))):
        a = 2 * math.pi * i / g("stabilizer_clips")
        with ks.at((R_IN * math.cos(a), R_IN * math.sin(a), RIM - 0.012), yaw=math.degrees(a)):
            ks.box("KnobBlack", (0, 0, 0), (0.03, 0.012, 0.03))


def bubble(kb):
    """Clear PE dome on the rim, with a front cut-out towards the operator (+y)."""
    h = g("bubble_height")
    gap = math.radians(g("bubble_opening_angle"))
    prof = [(R_OUT, RIM), (R_OUT * 0.99, RIM + 0.25 * h), (R_OUT * 0.92, RIM + 0.6 * h), (R_OUT * 0.75, RIM + 0.85 * h),
            (R_OUT * 0.45, RIM + 0.98 * h), (0.02, RIM + h)]
    partial_lathe(kb, "BubbleClearPE", prof, math.pi / 2 + gap / 2, math.pi / 2 - gap / 2 + 2 * math.pi, seg=96)


def build():
    st, root = new_asset(OUT, "Machine", "Generated by assets/machine/build_machine.py - edit the script, not this file.")
    parts = {}
    for name, fn in (("Cabinet", cabinet), ("Controls", controls), ("LockHandles", lock_handles)):
        k = Kit()
        fn(k)
        k.write(st, f"{root}/{name}")
        parts[name] = k
    kb, kh = Kit(), Kit()
    bell_and_head(kb, kh)
    kb.write(st, f"{root}/BellHousing")
    kh.write(st, f"{root}/SpinnerHead")
    kp, ks = Kit(), Kit()
    pan(kp, ks)
    kp.write(st, f"{root}/Pan")
    ks.write(st, f"{root}/Stabilizer")
    kd = Kit()
    bubble(kd)
    kd.write(st, f"{root}/Bubble")
    p = st.GetPrimAtPath(root)
    sdt(p, assetId="FlossMachine", canonicalName="cotton candy machine (Econo Floss 3017-type, 230 V)",
        reference="Gold Medal Econo Floss 3017 export / Neumaerker Econo Floss 00-51551 (inferred identity)",
        status="SOURCED overall dims; ANALOGUE photo-scaled parts; ILLUSTRATIVE slip-ring column",
        frame="origin floor centre of the feet; +y controls; z up; m")
    for part, cls in (("Controls/MotorMasterSwitch", "RockerSwitch"), ("Controls/HeatSwitch", "RockerSwitch"),
                      ("Controls/HeatControlKnob", "ControlKnob"), ("SpinnerHead", "SpinnerHead"),
                      ("Pan", "FlossPan"), ("Stabilizer", "FlossStabilizer"), ("Bubble", "FlossBubble"),
                      ("LockHandles/LockNGoHandleLeft", "LockHandle"), ("LockHandles/LockNGoHandleRight", "LockHandle")):
        sdt(st.GetPrimAtPath(f"{root}/{part}"), semanticAnnotation=cls)
    st.GetPrimAtPath(f"{root}/SpinnerHead").CreateAttribute("state:rpm", Sdf.ValueTypeNames.Double,
                                                            custom=True).Set(0.0)
    st.Save()
    return st


def envelopes(st):
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render"])

    def rng(paths):
        r = None
        for p in paths:
            b = bc.ComputeWorldBound(st.GetPrimAtPath(p)).ComputeAlignedRange()
            r = b if r is None else r.UnionWith(b)
        return [round(v, 4) for v in r.GetMin()], [round(v, 4) for v in r.GetMax()]

    lo, hi = rng(["/Machine/Cabinet", "/Machine/Controls", "/Machine/BellHousing", "/Machine/SpinnerHead"])
    cab_lo, cab_hi = rng(["/Machine/Cabinet"])
    plo, phi = rng(["/Machine/Pan"])
    hlo, hhi = rng(["/Machine/SpinnerHead"])
    data = dict(
        machine=dict(lo=[cab_lo[0], cab_lo[1], 0.0], hi=[cab_hi[0], cab_hi[1], phi[2]],
                     note="cabinet footprint (feet + housing), height to the pan rim"),
        pan=dict(lo=plo, hi=phi),
        head=dict(centre=[0.0, 0.0, round(BAND_C, 4)], radius=round(HEAD_R, 4),
                  swept_radius=round((hhi[0] - hlo[0]) / 2, 4),
                  note="hot zone = floss band (radius as built); swept_radius incl. the unheated leather floaters"),
        all_parts=dict(lo=lo, hi=hi),
    )
    out = provenance.write("asset_envelopes", data, [os.path.abspath(__file__), os.path.join(ROOT, "site", "params.py")])
    print("envelopes ->", os.path.relpath(out, ROOT), data["machine"], data["pan"], data["head"])


if __name__ == "__main__":
    stage = build()
    envelopes(stage)
    print("wrote", os.path.relpath(OUT, ROOT))
