"""Booth asset: the 2 x 2 m wooden Zuckerwatte booth with fit-out, built from the twin layout (site/layout.py).

Frame: the booth frame B of site/layout.py (origin on the paving at the booth centre, +y sales front -> back wall,
z up, m), so the asset is referenced at the origin. Parts under /Booth: Shell (walls, floor, pillars), Roof, Flap,
Counters, MachineTable, SideShelf, Equipment (hand-wash, extinguisher, power), Consumables (tubs, quiver + sticks,
GN tray + scoop, bags), Signs, Display (finished portions).
Statuses: dimensions from the register / layout (see there); colours, sign and decoration ILLUSTRATIVE.

Run: $E assets/booth/build_booth.py
"""

import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "site"))
import layout as L  # noqa: E402
import params as Pm  # noqa: E402
from assets.common.decals import text_png  # noqa: E402
from assets.common.kit import Kit, new_asset, sdt  # noqa: E402

g = Pm.get
OUT = os.path.join(ROOT, "assets", "booth", "usd", "booth.usda")
TEX = os.path.join(ROOT, "assets", "booth", "usd", "textures")
ITEMS = {it["name"]: it for it in L.items()}
W, D, T = g("booth_width"), g("booth_depth"), g("booth_wall_panel_t")
FZ = L.FLOOR_Z


def centre_size(name):
    it = ITEMS[name]
    lo, hi = np.array(it["lo"]), np.array(it["hi"])
    return (lo + hi) / 2, hi - lo


def rot_x(deg):
    a = math.radians(deg)
    return np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])


def shell(k):
    k.box("SpruceOiled", (0, 0, FZ / 2), (W, D, FZ))                                   # floor on skids
    gable = [(-D / 2, FZ), (D / 2, FZ), (D / 2, L.EAVE_Z), (0.0, L.RIDGE_Z), (-D / 2, L.EAVE_Z)]
    for x0, x1 in ((-W / 2, -W / 2 + T), (W / 2 - T, W / 2)):
        k.extrude("SprucePaintedWhite", gable, (x0, 0, 0), (x1, 0, 0), up=(0, 0, 1))
    # back wall with the operator door (door leaf open inward, ILLUSTRATIVE)
    door = ITEMS["DoorBack"]
    dx0, dx1, dz1 = door["lo"][0], door["hi"][0], door["hi"][2]
    yb = (D / 2 - T / 2)
    k.box("SprucePaintedWhite", ((-W / 2 + dx0) / 2, yb, (FZ + L.EAVE_Z) / 2), (dx0 + W / 2, T, L.EAVE_Z - FZ))
    k.box("SprucePaintedWhite", ((dx1 + W / 2) / 2, yb, (FZ + L.EAVE_Z) / 2), (W / 2 - dx1, T, L.EAVE_Z - FZ))
    k.box("SprucePaintedWhite", ((dx0 + dx1) / 2, yb, (dz1 + L.EAVE_Z) / 2), (dx1 - dx0, T, L.EAVE_Z - dz1))
    with k.at((dx0 + 0.01, yb - 0.01, FZ), yaw=-70):
        k.box("SprucePaintedWhite", ((dx1 - dx0) / 2, 0, (dz1 - FZ) / 2), (dx1 - dx0 - 0.02, 0.03, dz1 - FZ - 0.01))
    # front: below counter, header, pillars beside the sales opening, white trim around the opening
    for name in ("WallFrontBelowCounter", "WallFrontHeader"):
        c, s = centre_size(name)
        k.box("SprucePaintedPink", c, s)
    for xa, xb in ((-W / 2, L.FLAP_X[0]), (L.FLAP_X[1], W / 2)):
        k.box("SprucePaintedPink", ((xa + xb) / 2, -D / 2 + T / 2, (L.FLAP_Z[0] + L.FLAP_Z[1]) / 2),
              (xb - xa, T, L.FLAP_Z[1] - L.FLAP_Z[0]))
    y = -D / 2 - 0.006
    for z in (L.FLAP_Z[0], L.FLAP_Z[1]):
        k.box("SprucePaintedWhite", (0, y, z), (L.FLAP_X[1] - L.FLAP_X[0] + 0.12, 0.012, 0.05))
    for x in L.FLAP_X:
        k.box("SprucePaintedWhite", (x, y, (L.FLAP_Z[0] + L.FLAP_Z[1]) / 2), (0.05, 0.012, L.FLAP_Z[1] - L.FLAP_Z[0]))
    for x in (-W / 2 + 0.02, W / 2 - 0.02):                                           # corner posts
        for yy in (-D / 2 + 0.02, D / 2 - 0.02):
            k.box("SprucePaintedWhite", (x, yy, (FZ + L.EAVE_Z) / 2), (0.045, 0.045, L.EAVE_Z - FZ))
    k.collide((0, 0, FZ / 2), (W, D, FZ), name="Floor")


def roof(k):
    ov = g("booth_roof_overhang")
    ov_front = 0.05      # ILLUSTRATIVE deviation: the raised sales flap is the front awning, so the front eave only
    #                      overhangs the header (the register's 0.25 m applies to the back and the sides)
    rise, half = L.RIDGE_Z - L.EAVE_Z, D / 2
    pitch = math.degrees(math.atan2(rise, half))
    for sign, o in ((-1, ov_front), (1, ov)):
        run = math.hypot(half + o, rise * (half + o) / half)
        R = rot_x(sign * pitch)
        with k.at((0, sign * (half + o) / 2, L.RIDGE_Z - rise * (half + o) / half / 2 + 0.03), R=R):
            k.box("SprucePaintedPink", (0, 0, 0), (W + 2 * ov, run, 0.03))
            for i in range(9):                                                         # white stripes (tarp look)
                xs = -W / 2 - ov + (i + 0.5) * (W + 2 * ov) / 9
                if i % 2:
                    k.box("TarpStripeWhite", (xs, 0, 0.0155), ((W + 2 * ov) / 9, run, 0.001))
    k.box("SprucePaintedWhite", (0, 0, L.RIDGE_Z + 0.04), (W + 2 * ov, 0.10, 0.05))   # ridge cap
    # LED strip under the front header (inside)
    k.box("LedWarm", (0, -D / 2 + T + 0.02, L.EAVE_Z - 0.03), (W - 0.1, 0.02, 0.01))


def flap(k):
    """Top-hinged sales flap, open by booth_flap_open_angle, on two gas struts."""
    a = g("booth_flap_open_angle")
    hinge = np.array([0.0, -D / 2 - 0.012, L.FLAP_Z[1]])
    R = rot_x(-a)                                    # closed: hangs along -z; opening swings the free edge outward
    with k.at(tuple(hinge), R=R):
        k.box("SprucePaintedPink", (0, -0.012, -g("booth_flap_height") / 2), (g("booth_flap_width") + 0.08, 0.024,
                                                                               g("booth_flap_height")))
        k.box("TarpStripeWhite", (0, 0.001, -g("booth_flap_height") / 2), (g("booth_flap_width"), 0.002, 0.04))
        k.box("StainlessSatin", (0, 0.02, -g("booth_flap_height") + 0.08), (0.30, 0.02, 0.02))     # handle (inside)
        for i in range(12):                                   # scalloped valance at the free edge (ILLUSTRATIVE)
            x = -g("booth_flap_width") / 2 - 0.04 + (i + 0.5) * (g("booth_flap_width") + 0.08) / 12
            mat = "SprucePaintedWhite" if i % 2 else "SprucePaintedPink"
            k.extrude(mat, [(-0.07, 0.0), (0.0, -0.10), (0.07, 0.0)], (x, -0.026, -g("booth_flap_height")),
                      (x, -0.020, -g("booth_flap_height")), up=(0, 0, 1))
        for x in (-0.25, 0.25):                                                                       # spot lights
            k.cyl("PoleDark", (x, 0.0, -0.45), (x, 0.05, -0.45), 0.03)
            k.disk("LedWarm", (x, 0.051, -0.45), 0.024, normal=(0, 1, 0))
    tip = hinge + R @ np.array([0, 0, -0.6])
    for x in (-0.72, 0.72):
        base = np.array([x, -D / 2 - 0.01, L.FLAP_Z[1] - 0.45])
        k.cyl("StainlessSatin", tuple(base), tuple(np.array([x, tip[1], tip[2]])), 0.009)
    edge = hinge + R @ np.array([0, 0, -g("booth_flap_height")])
    return edge


def counters(k):
    c, s = centre_size("CounterSteel")
    k.box("StainlessBrushed", (c[0], c[1] + 0.01, (FZ + L.COUNTER_Z - 0.02) / 2), (s[0], s[1] - 0.02, L.COUNTER_Z - FZ - 0.02))
    k.box("StainlessWorktop", (c[0], c[1], L.COUNTER_Z - 0.01), (s[0], s[1] + 0.02, 0.02))
    c, s = centre_size("SalesCounter")
    k.box("SprucePaintedWhite", (c[0], c[1] + 0.02, (FZ + L.COUNTER_Z) / 2 - 0.0135), (s[0], s[1] - 0.04, L.COUNTER_Z - FZ - 0.027))
    k.box("SpruceOiled", (c[0], c[1] - 0.01, L.COUNTER_Z - 0.0135), (s[0], s[1] + 0.04, g("booth_counter_top_t")))
    k.collide((0.5, -0.69, (FZ + L.COUNTER_Z) / 2), (1.0, 0.62, L.COUNTER_Z - FZ), name="Counter")
    # lowered stainless machine table: top, legs, undershelf
    it = ITEMS["MachineTable"]
    lo, hi = np.array(it["lo"]), np.array(it["hi"])
    cx, cy = (lo[:2] + hi[:2]) / 2
    sx, sy = hi[:2] - lo[:2]
    k.box("StainlessWorktop", (cx, cy, hi[2] - 0.015), (sx, sy, 0.03))
    for ex in (lo[0] + 0.03, hi[0] - 0.03):
        for ey in (lo[1] + 0.03, hi[1] - 0.03):
            k.cyl("StainlessSatin", (ex, ey, FZ), (ex, ey, hi[2] - 0.03), 0.018)
    k.box("StainlessBrushed", (cx, cy, FZ + 0.18), (sx - 0.04, sy - 0.04, 0.02))
    k.collide((cx, cy, hi[2] - 0.015), (sx, sy, 0.03), name="MachineTable")


def shelf_and_consumables(k):
    it = ITEMS["SideShelf"]
    lo, hi = np.array(it["lo"]), np.array(it["hi"])
    cx, cy = (lo[:2] + hi[:2]) / 2
    sx, sy = hi[:2] - lo[:2]
    for z in (FZ + 0.10, FZ + 0.53, FZ + 1.00, FZ + 1.45):
        k.box("SpruceOiled", (cx, cy, z), (sx, sy, 0.018))
    for yy in (lo[1] + 0.01, hi[1] - 0.01):
        k.box("SpruceOiled", (cx, yy, (FZ + hi[2]) / 2), (sx, 0.018, hi[2] - FZ))
    # three 10 L sugar tubs: white, pink (E129), blue (E133)
    for i, (sugar, label) in enumerate((("SugarWhite", "WEISS"), ("SugarPink", "HIMBEER E129"), ("SugarBlue", "BLAUBEERE E133"))):
        ty = lo[1] + 0.12 + i * 0.23
        z0 = FZ + 0.54
        k.rbox("TubLid", (cx, ty, z0 + 0.10), (0.24, 0.20, 0.20), r=0.012)
        k.box(sugar, (cx - 0.121, ty, z0 + 0.08), (0.002, 0.18, 0.14))                # sugar seen through the side
        k.rbox("TubLid", (cx, ty, z0 + 0.205), (0.25, 0.21, 0.015), r=0.005)
        png = text_png(os.path.join(TEX, f"tub_{i}.png"), [label], size=(512, 128))
        k.decal(png, (cx - 0.1215, ty, z0 + 0.16), (-1, 0, 0), (0, 0, 1), 0.16, 0.04)
    # stick packs and bag stock on the top board
    for i in range(3):
        k.box("PineStick", (cx, lo[1] + 0.10 + 0.06 * i, FZ + 1.03), (0.04, 0.40, 0.04))
    k.box("BagFilm", (cx, hi[1] - 0.15, FZ + 1.06), (0.28, 0.20, 0.10))
    # wall quiver with sticks
    q = ITEMS["StickHolder"]
    qlo, qhi = np.array(q["lo"]), np.array(q["hi"])
    k.box("SpruceOiled", ((qlo[0] + qhi[0]) / 2, (qlo[1] + qhi[1]) / 2, qlo[2] + 0.11),
          (qhi[0] - qlo[0], qhi[1] - qlo[1], 0.22))
    rng = np.random.default_rng(4)
    for i in range(14):
        sx_, sy_ = qlo[0] + 0.02 + 0.06 * rng.random(), qlo[1] + 0.02 + 0.08 * rng.random()
        k.box("PineStick", (sx_, sy_, qlo[2] + 0.04 + g("stick_length") / 2),
              (g("stick_section"), g("stick_section"), g("stick_length")))
    # GN 1/6 working tray with pink sugar and scoop
    t = ITEMS["SugarWorkTray"]
    tlo, thi = np.array(t["lo"]), np.array(t["hi"])
    c = (tlo + thi) / 2
    s = thi - tlo
    k.box("StainlessBrushed", (c[0], c[1], tlo[2] + 0.001), (s[0], s[1], 0.002))
    for dx, dy, wx, wy in ((-s[0] / 2, 0, 0.002, s[1]), (s[0] / 2, 0, 0.002, s[1]), (0, -s[1] / 2, s[0], 0.002), (0, s[1] / 2, s[0], 0.002)):
        k.box("StainlessBrushed", (c[0] + dx, c[1] + dy, c[2]), (wx, wy, s[2]))
    k.box("SugarPink", (c[0], c[1], tlo[2] + 0.06), (s[0] - 0.006, s[1] - 0.006, 0.004))
    k.cyl("StainlessSatin", (c[0] + 0.02, c[1], tlo[2] + 0.062), (c[0] + 0.02, c[1], tlo[2] + 0.092), 0.025)
    k.cyl("StainlessSatin", (c[0] + 0.045, c[1], tlo[2] + 0.085), (c[0] + 0.14, c[1], tlo[2] + 0.11), 0.007)
    # bag rail with filled bags (display)
    b = ITEMS["BagRail"]
    blo, bhi = np.array(b["lo"]), np.array(b["hi"])
    k.cyl("StainlessSatin", (blo[0], (blo[1] + bhi[1]) / 2, bhi[2]), (bhi[0], (blo[1] + bhi[1]) / 2, bhi[2]), 0.006)
    for i, mat in enumerate(("FlossPink", "FlossBlue", "FlossPink")):
        x = blo[0] + 0.30 + i * 0.16
        y = (blo[1] + bhi[1]) / 2
        with k.at((x, y, bhi[2] - 0.20), R=np.diag([0.07, 0.035, 0.15])):
            k.sphere(mat, (0, 0, 0), 1.0, seg=20)
        k.box("BagFilm", (x, y, bhi[2] - 0.03), (0.06, 0.012, 0.05))


def floss_portion(k, x, y, z_base, mat, seed):
    """A finished portion: 40 cm stick with a fluffy ellipsoid of floss (portion_diameter x portion_length)."""
    L_ = g("stick_length")
    k.box("PineStick", (x, y, z_base + L_ / 2), (g("stick_section"), g("stick_section"), L_))
    rd, ln = g("portion_diameter") / 2, g("portion_length") / 2
    zc = z_base + L_ - ln * 0.9
    rng = np.random.default_rng(seed)
    with k.at((x, y, zc), R=np.diag([rd * 0.85, rd * 0.85, ln * 0.85])):
        k.sphere(mat, (0, 0, 0), 1.0, seg=28)
    for _ in range(9):                                                                # fluff lobes
        d = rng.normal(size=3)
        d /= np.linalg.norm(d)
        r = 0.35 + 0.15 * rng.random()
        with k.at((x + d[0] * rd * 0.6, y + d[1] * rd * 0.6, zc + d[2] * ln * 0.6), R=np.diag([rd * r, rd * r, ln * r])):
            k.sphere(mat, (0, 0, 0), 1.0, seg=16)


def equipment(k):
    c, s = centre_size("HandwashStation")
    k.rbox("PlasticWhite", (c[0], c[1], FZ + s[2] / 2), s, r=0.01)
    k.cyl("StainlessSatin", (c[0], c[1], FZ + s[2] - 0.06), (c[0], c[1], FZ + s[2] + 0.001), 0.15)
    k.cyl("Chrome", (c[0], c[1] + 0.16, FZ + s[2]), (c[0], c[1] + 0.16, FZ + s[2] + 0.18), 0.01)
    k.cyl("Chrome", (c[0], c[1] + 0.16, FZ + s[2] + 0.18), (c[0], c[1] + 0.06, FZ + s[2] + 0.18), 0.008)
    for i, mat in enumerate(("CanisterBlue", "PlasticGrey")):
        k.rbox(mat, (c[0] - 0.09 + 0.18 * i, c[1], FZ + 0.25), (0.15, 0.25, 0.30), r=0.02)
    k.rbox("PlasticWhite", (c[0] + 0.12, L.Y1 - 0.06, FZ + 1.25), (0.22, 0.10, 0.30), r=0.01)       # towel dispenser
    k.rbox("PlasticWhite", (c[0] - 0.14, L.Y1 - 0.05, FZ + 1.15), (0.09, 0.08, 0.16), r=0.01)       # soap
    c, s = centre_size("FireExtinguisher")
    k.box("KnobBlack", (L.X0 + 0.01, c[1], c[2]), (0.02, 0.08, 0.10))
    k.cyl("GlossRed", (c[0] + 0.02, c[1], c[2] - 0.27), (c[0] + 0.02, c[1], c[2] + 0.18), 0.075, r_edge=0.02)
    k.cyl("KnobBlack", (c[0] + 0.02, c[1], c[2] + 0.18), (c[0] + 0.02, c[1], c[2] + 0.25), 0.02)
    k.cyl("KnobBlack", (c[0] + 0.02, c[1], c[2] + 0.22), (c[0] + 0.09, c[1] - 0.05, c[2] - 0.15), 0.008)
    png = text_png(os.path.join(TEX, "extinguisher.png"), ["ABC 6 kg", "EN 3"], size=(256, 256), bg=(250, 250, 245, 255))
    k.decal(png, (c[0] + 0.02, c[1] - 0.076, c[2] - 0.05), (0, -1, 0), (0, 0, 1), 0.08, 0.08)
    c, s = centre_size("PowerDistributor")
    k.rbox("PlasticGrey", c, s, r=0.01)
    k.cyl("PlasticBlue", (c[0] - 0.06, c[1] - 0.05, c[2] - 0.15), (c[0] - 0.06, c[1] - 0.05, c[2] - 0.2), 0.03)
    k.cyl("PlasticBlack", (c[0] - 0.06, c[1] - 0.05, FZ + 0.02), (c[0] - 0.06, c[1] - 0.05, c[2] - 0.2), 0.008)
    c, s = centre_size("CashBox")
    k.rbox("PowderAnthracite", c, s, r=0.008)


def signs(k):
    # fascia sign standing on the front eave (the front roof overhang is only 5 cm, see roof())
    z = L.EAVE_Z + 0.42                    # above the raised flap edge (~2.15 m) so customers can read it
    y = -D / 2 - 0.035
    png = text_png(os.path.join(TEX, "sign_zuckerwatte.png"), [("Zuckerwatte", 1.0, (225, 25, 115, 255))],
                   size=(1600, 320), bg=(255, 250, 252, 255))
    k.rbox("SprucePaintedWhite", (0, y + 0.015, z), (1.90, 0.03, 0.40), r=0.01)
    k.decal(png, (0, y - 0.001, z), (0, -1, 0), (0, 0, 1), 1.70, 0.34, emissive=25.0)
    k.box("SignPink", (0, y - 0.002, z - 0.19), (1.90, 0.01, 0.012))
    k.box("SignPink", (0, y - 0.002, z + 0.19), (1.90, 0.01, 0.012))
    it = ITEMS["InfoBoard"]
    lo, hi = np.array(it["lo"]), np.array(it["hi"])
    c = (lo + hi) / 2
    png = text_png(os.path.join(TEX, "info_board.png"),
                   [("Zuckerwatte  3,00 EUR", 1.4, (255, 255, 255, 255)),
                    ("mit Farbstoff", 0.9, (255, 220, 235, 255)),
                    ("E129: Kann Aktivitaet und Aufmerksamkeit", 0.7, (255, 255, 255, 255)),
                    ("bei Kindern beeintraechtigen.", 0.7, (255, 255, 255, 255)),
                    ("Enthaelt Milch (Laktose)", 0.8, (255, 255, 255, 255))],
                   size=(900, 600), bg=(20, 20, 22, 255))
    k.box("SpruceOiled", (c[0], hi[1] + 0.006, c[2]), (hi[0] - lo[0] + 0.02, 0.012, hi[2] - lo[2] + 0.02))
    # board faces the customers: on the outside of the front wall below the counter edge
    k.decal(png, (c[0], -D / 2 - 0.004, L.COUNTER_Z - 0.20), (0, -1, 0), (0, 0, 1), 0.42, 0.28)


def display(k):
    for i, (mat, dx) in enumerate((("FlossPink", 0.0), ("FlossBlue", 0.11))):
        x, y = 0.62 + dx * 1.5, -0.80 + 0.03 * i
        k.cyl("SpruceOiled", (x, y, L.COUNTER_Z), (x, y, L.COUNTER_Z + 0.06), 0.04)
        floss_portion(k, x, y, L.COUNTER_Z + 0.02, mat, seed=10 + i)


def build():
    st, root = new_asset(OUT, "Booth", "Generated by assets/booth/build_booth.py - edit the script, not this file.")
    parts = (("Shell", shell), ("Roof", roof), ("Flap", flap), ("Counters", counters),
             ("SideShelfAndConsumables", shelf_and_consumables), ("Equipment", equipment), ("Signs", signs),
             ("Display", display))
    for name, fn in parts:
        k = Kit()
        fn(k)
        k.write(st, f"{root}/{name}")
    sdt(st.GetPrimAtPath(root), assetId="CottonCandyBooth", canonicalName="2 x 2 m Zuckerwatte market booth",
        status="SOURCED footprint/panels/counter depth; ANALOGUE heights/flap; ILLUSTRATIVE colours and decoration",
        frame="booth frame B of site/layout.py")
    for part, cls in (("Flap", "SalesFlap"), ("Equipment", "HandwashStation;FireExtinguisher;PowerDistributor"),
                      ("Signs", "InformationBoard"), ("Display", "CottonCandy")):
        sdt(st.GetPrimAtPath(f"{root}/{part}"), semanticAnnotation=cls)
    st.Save()
    print("wrote", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    build()
