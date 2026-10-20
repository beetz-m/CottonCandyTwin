"""Plan figures of the Cotton Candy Booth twin -> renders/plans/*.png (generated: edit the script, not the outputs).

Reads only the layout model (site/layout.py), the register (site/params.py) and the result JSON in data/ (checks,
robot_envelope, asset_envelopes; loaded with provenance.load_fresh, so a stale result stops the build). Nothing is
typed twice: every box, height and margin comes from those sources.

  booth_plan.png        top view: shell, sales front with the opening, every layout item, robot stations with the
                        measured PR2 envelope, handover point, free floor (the C6 region), dimension lines
  booth_elevation.png   front elevation (as the customer sees it) and side section with the flap opened
  checks_summary.png    the design checks: measured value against its limit, as a relative margin
  register_status.png   register entries per evidence status

Run: $E site/plan_figures.py
"""

import math
import os
import re
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Polygon, Rectangle, Wedge  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout as L  # noqa: E402
import params as Pm  # noqa: E402
import provenance  # noqa: E402

g = Pm.get
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "renders", "plans")
DPI = 200

INK, MUTED, GRID = "#222831", "#6b7280", "#d9dde3"
ROLE_STYLE = {   # role -> (face, edge, label)
    "wall": ("#c9a77c", "#8a6a43", "spruce shell"),
    "table": ("#d5dade", "#7c8590", "stainless"),
    "counter": ("#e2c9a3", "#8a6a43", "counter"),
    "shelf": ("#e8d6b8", "#8a6a43", "shelf"),
    "handwash": ("#cfe3ef", "#4b7a99", "hygiene"),
    "safety": ("#f2b8b5", "#b42318", "safety"),
    "electrical": ("#f5e3a3", "#9a7b12", "electrical"),
    "door": ("#ffffff", "#8a6a43", "door"),
    "machine": ("#b8c2cc", "#3d4a57", "floss machine"),
    "pan": ("#eef1f4", "#3d4a57", "floss pan"),
    "consumable": ("#f7c6d9", "#b5175a", "consumables (combustible)"),
    "cleaning": ("#cdeccd", "#2d7a4a", "cleaning"),
    "sales": ("#e5e1f5", "#5b4b9a", "sales"),
    "label": ("#fff4c2", "#9a7b12", "label"),
}
ROBOT, ROBOT_SOFT = "#24678f", "#24678f22"
HOT = "#d1495b"


def need(d, *keys):
    """Fail loud: d[keys[0]][keys[1]]..."""
    for k in keys:
        if k not in d:
            raise KeyError(f"missing key {k!r} (have {sorted(d)[:12]})")
        d = d[k]
    return d


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", os.path.relpath(path, ROOT))
    return path


def dim(ax, p0, p1, text, offset=(0, 0), color=MUTED, fs=7.5):
    """A dimension line between p0 and p1, shifted by offset, with the text at its middle."""
    (x0, y0), (x1, y1) = (p0[0] + offset[0], p0[1] + offset[1]), (p1[0] + offset[0], p1[1] + offset[1])
    ax.annotate("", (x0, y0), (x1, y1), arrowprops=dict(arrowstyle="<->", color=color, lw=0.8, shrinkA=0, shrinkB=0))
    for (px, py), (qx, qy) in ((p0, (x0, y0)), (p1, (x1, y1))):
        if offset != (0, 0):
            ax.plot([px, qx], [py, qy], color=color, lw=0.5, ls=":")
    vertical = abs(x1 - x0) < abs(y1 - y0)
    ax.text((x0 + x1) / 2, (y0 + y1) / 2, text, fontsize=fs, color=color, ha="center", va="center",
            rotation=90 if vertical else 0, bbox=dict(fc="white", ec="none", pad=0.6))


def robot_parts(station):
    """Footprints of the parked robot at a station: (base box, upper envelope box) as polygons in the booth frame,
    each grown by its collision buffer (PR2_CRAM_CFG), from the MEASURED link boxes."""
    env = provenance.load_fresh("robot_envelope")["parked"]
    links = need(env, "links")
    sx, sy, yaw = L.ROBOT_STATIONS[station]
    c, s = math.cos(yaw), math.sin(yaw)

    def poly(lo, hi, margin):
        pts = [(lo[0] - margin, lo[1] - margin), (hi[0] + margin, lo[1] - margin), (hi[0] + margin, hi[1] + margin),
               (lo[0] - margin, hi[1] + margin)]
        return [(sx + c * x - s * y, sy + s * x + c * y) for x, y in pts]

    base = [l for l in links if "base" in l["name"]]
    blo = [min(l["lo"][i] for l in base) for i in range(3)]
    bhi = [max(l["hi"][i] for l in base) for i in range(3)]
    return (poly(blo, bhi, 0.0), poly(blo, bhi, g("robot_buffer_base_booth")),
            poly(need(env, "upper", "lo"), need(env, "upper", "hi"), 0.0))


# %% 1. plan


def booth_plan():
    items = {it["name"]: it for it in L.items()}
    env = provenance.load_fresh("asset_envelopes")
    fig, ax = plt.subplots(figsize=(9.2, 8.6))
    ax.set_aspect("equal")

    # free floor of the operator (same rule as check C6: interior minus footprints below 1.8 m)
    from shapely.geometry import Point, box as sbox
    from shapely.ops import unary_union
    free = sbox(L.X0, L.Y0, L.X1, L.Y1).difference(unary_union(
        [sbox(it["lo"][0], it["lo"][1], it["hi"][0], it["hi"][1]) for it in items.values()
         if it["role"] not in ("wall", "roof", "door") and it["lo"][2] < L.FLOOR_Z + 1.8]))
    ox, oy, _ = L.OPERATOR_POSE
    region = next(r for r in getattr(free, "geoms", [free]) if r.contains(Point(ox, oy)))
    for ring in [region.exterior]:
        ax.add_patch(Polygon(list(ring.coords), closed=True, fc="#eaf5ea", ec="none", zorder=0))

    drawn_roles = set()
    order = ["wall", "table", "counter", "shelf", "handwash", "door", "machine", "pan", "consumable", "cleaning",
             "sales", "label", "safety", "electrical"]
    for role in order:
        for it in items.values():
            if it["role"] != role:
                continue
            face, edge, _ = ROLE_STYLE[role]
            (x0, y0, _), (x1, y1, _) = it["lo"], it["hi"]
            if role == "pan":
                ax.add_patch(Circle(((x0 + x1) / 2, (y0 + y1) / 2), (x1 - x0) / 2, fc=face, ec=edge, lw=1.0,
                                    alpha=0.9, zorder=3))
            elif role == "wall" and it["name"] in ("WallFrontBelowCounter", "WallFrontHeader"):
                continue   # drawn below as the sales front with its opening
            else:
                ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=face, ec=edge, lw=0.8,
                                       zorder=2 if role in ("table", "counter", "shelf") else 3))
            drawn_roles.add(role)

    # sales front: wall below the counter across the width, the opening above it between FLAP_X
    fw = items["WallFrontBelowCounter"]
    face, edge, _ = ROLE_STYLE["wall"]
    for xa, xb in ((-L.W / 2, L.FLAP_X[0]), (L.FLAP_X[1], L.W / 2)):
        ax.add_patch(Rectangle((xa, fw["lo"][1]), xb - xa, fw["hi"][1] - fw["lo"][1], fc=face, ec=edge, lw=0.8, zorder=3))
    ax.add_patch(Rectangle((L.FLAP_X[0], fw["lo"][1]), L.FLAP_W, fw["hi"][1] - fw["lo"][1], fc="white", ec=edge,
                           lw=0.8, hatch="////", zorder=3))
    fy, _ = L.flap_edge()
    ax.add_patch(Rectangle((L.FLAP_X[0], fy), L.FLAP_W, -L.Dp / 2 - fy, fc="none", ec=MUTED, lw=0.8, ls="--", zorder=1))
    ax.text(0, (fy - L.Dp / 2) / 2, f"sales flap opened {g('booth_flap_open_angle'):.0f}° (projection)",
            ha="center", va="center", fontsize=7.5, color=MUTED)

    # machine head: hot band and keep-out circle of check C4
    head = need(env, "head")
    hx, hy = L.MACHINE_XY
    ax.add_patch(Circle((hx, hy), need(head, "radius"), fc=HOT, ec="none", zorder=4))
    ax.add_patch(Circle((hx, hy), need(head, "radius") + g("reg_heat_clearance"), fc="none", ec=HOT, lw=0.9,
                        ls="--", zorder=4))
    ax.text(-0.80, -1.20, f"{g('reg_heat_clearance'):.2f} m\nto combustibles (C4)", color=HOT, fontsize=6.5,
            zorder=11, bbox=dict(fc="white", ec="none", alpha=0.8, pad=0.4))

    # robot stations
    for station in L.ROBOT_STATIONS:
        base, grown, upper = robot_parts(station)
        sx, sy, yaw = L.ROBOT_STATIONS[station]
        parked = not station.endswith("_close")
        if parked:
            ax.add_patch(Polygon(upper, closed=True, fc="none", ec=ROBOT, lw=0.8, ls=":", zorder=6))
        ax.add_patch(Polygon(grown, closed=True, fc="none", ec=ROBOT, lw=0.6, ls="--", zorder=6))
        ax.add_patch(Polygon(base, closed=True, fc=ROBOT_SOFT, ec=ROBOT, lw=1.2, zorder=6))
        ax.annotate("", (sx + 0.22 * math.cos(yaw), sy + 0.22 * math.sin(yaw)), (sx, sy),
                    arrowprops=dict(arrowstyle="-|>", color=ROBOT, lw=1.2), zorder=7)
        ax.plot(sx, sy, "o", color=ROBOT, ms=3, zorder=7)
    labels = {"machine": ("PR2 at 'machine' (parked)", (-1.40, 0.92), "left"),
              "machine_close": ("'machine_close' (base only,\narms raised; never parked)", (-1.40, 0.70), "left"),
              "serving": ("PR2 at 'serving' (parked)", (0.15, 0.40), "left")}
    for station, (text, (tx, ty), ha) in labels.items():
        sx, sy, _ = L.ROBOT_STATIONS[station]
        ax.annotate(text, (sx, sy), (tx, ty), fontsize=7.5, color=ROBOT, ha=ha, va="center",
                    arrowprops=dict(arrowstyle="-", color=ROBOT, lw=0.6), zorder=8)

    # handover point and customers
    hx_, hy_, hz_ = L.HANDOVER_XYZ
    ax.plot(hx_, hy_, marker="*", color="#b5175a", ms=12, zorder=9)
    ax.annotate(f"handover point\n(z = {hz_ - L.FLOOR_Z:.2f} m above floor)", (hx_, hy_), (hx_ + 0.25, hy_ + 0.35),
                fontsize=7.5, color="#b5175a", arrowprops=dict(arrowstyle="-", color="#b5175a", lw=0.6), zorder=9)
    ax.axhline(-L.Dp / 2, color=MUTED, lw=0.6, ls="-.", zorder=0)
    ax.text(L.W / 2 + 0.03, -L.Dp / 2, "customer line\n(sales front)", fontsize=7, color=MUTED, va="center")
    ax.plot(ox, oy, marker="s", color="#2d7a4a", ms=5, zorder=8)
    ax.annotate("operator pose\n(C6, C12, C13)", (ox, oy), (-1.42, -0.02), fontsize=7, color="#2d7a4a",
                arrowprops=dict(arrowstyle="-", color="#2d7a4a", lw=0.6), zorder=8)

    # item names (small, inside or beside their box)
    names = {"MachineTable": "machine table", "CounterSteel": "steel\ncounter", "SalesCounter": "sales counter",
             "SideShelf": "side shelf", "HandwashStation": "hand-\nwash", "FireExtinguisher": "extinguisher",
             "PowerDistributor": "RCD", "DoorBack": "back door", "StickHolder": "stick\nquiver",
             "SugarCarton": "sugar\ncarton", "Sponge": "sponge", "CashBox": "cash", "SugarTubs": "sugar tubs",
             "BagRail": "bag rail", "InfoBoard": "info board"}
    nudge = {"MachineTable": (0.0, -0.17), "SugarCarton": (0.0, 0.0), "Sponge": (0.12, -0.06),
             "FireExtinguisher": (0.22, 0.0), "PowerDistributor": (-0.12, 0.0), "StickHolder": (0.15, 0.0),
             "BagRail": (0.0, 0.10), "InfoBoard": (0.0, 0.14), "SugarTubs": (-0.06, -0.12), "SideShelf": (-0.06, 0.22),
             "CashBox": (0.0, 0.0), "DoorBack": (0.0, -0.09)}
    for n, text in names.items():
        it = items[need(items, n)["name"]]
        cx = (it["lo"][0] + it["hi"][0]) / 2 + nudge.get(n, (0, 0))[0]
        cy = (it["lo"][1] + it["hi"][1]) / 2 + nudge.get(n, (0, 0))[1]
        ax.text(cx, cy, text, fontsize=6.3, ha="center", va="center", color=INK, zorder=10,
                bbox=dict(fc="white", ec="none", alpha=0.7, pad=0.4))
    ax.text(hx, hy - 0.05, "pan + head", fontsize=6.3, ha="center", va="top", color=INK, zorder=10)
    rx, ry = 0.25, 1.02
    ax.text(rx, ry, f"free floor around the operator\n{region.area:.2f} m² (C6, ≥ {g('asr_move_area'):.1f} m²)",
            fontsize=7.5, color="#2d7a4a", ha="center", zorder=10)

    # dimensions
    dim(ax, (-L.W / 2, L.Dp / 2), (L.W / 2, L.Dp / 2), f"booth width {L.W:.2f} m", offset=(0, 0.22))
    dim(ax, (-L.W / 2, -L.Dp / 2), (-L.W / 2, L.Dp / 2), f"booth depth {L.Dp:.2f} m", offset=(-0.22, 0))
    dim(ax, (L.FLAP_X[0], fy), (L.FLAP_X[1], fy), f"flap / opening {L.FLAP_W:.2f} m", offset=(0, -0.14))
    dim(ax, (L.X0, L.Y0), (L.X0, L.MACHINE_XY[1]), f"{L.MACHINE_XY[1] - L.Y0:.2f}", offset=(0.06, 0), fs=6.5)
    dim(ax, (L.X0, L.MACHINE_XY[1]), (L.MACHINE_XY[0], L.MACHINE_XY[1]), f"{L.MACHINE_XY[0] - L.X0:.2f}",
        offset=(0, -0.43), fs=6.5)

    # legend
    from matplotlib.lines import Line2D
    handles = [Rectangle((0, 0), 1, 1, fc=ROLE_STYLE[r][0], ec=ROLE_STYLE[r][1], label=ROLE_STYLE[r][2])
               for r in order if r in drawn_roles and r not in ("door", "label")]
    handles += [Rectangle((0, 0), 1, 1, fc=ROBOT_SOFT, ec=ROBOT, label="PR2 base (measured)"),
                Line2D([], [], color=ROBOT, ls="--", lw=0.8, label=f"+ base buffer {g('robot_buffer_base_booth'):.2f} m"),
                Line2D([], [], color=ROBOT, ls=":", lw=0.8, label="parked upper body (arms, torso)"),
                Rectangle((0, 0), 1, 1, fc="#eaf5ea", ec="none", label="operator free floor (C6)"),
                Line2D([], [], color=HOT, ls="--", lw=0.9, label="heat keep-out (C4)")]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=7.5, frameon=False)

    ax.set_xlim(-L.W / 2 - 0.40, L.W / 2 + 0.45)
    ax.set_ylim(fy - 0.30, L.Dp / 2 + 0.38)
    ax.set_xlabel("x [m] (customer's right)")
    ax.set_ylabel("y [m] (sales front → back wall)")
    ax.grid(color=GRID, lw=0.4)
    ax.set_axisbelow(True)
    ax.set_title(f"Cotton candy booth, plan view ({L.W:.1f} × {L.Dp:.1f} m, frame B, origin at the footprint centre)",
                 fontsize=10, loc="left")
    return save(fig, "booth_plan.png")


# %% 2. elevations


def booth_elevation():
    items = {it["name"]: it for it in L.items()}
    env = provenance.load_fresh("asset_envelopes")
    renv = provenance.load_fresh("robot_envelope")["parked"]
    fz0 = L.FLOOR_Z
    fig, (af, aside) = plt.subplots(1, 2, figsize=(13.5, 6.4), gridspec_kw=dict(width_ratios=[1.0, 1.25]))

    def draw_items(ax, axis):   # axis 0: x (front elevation), 1: y (side section)
        for it in sorted(items.values(), key=lambda it: -it["hi"][1] if axis == 0 else it["hi"][0]):
            role = it["role"]
            if role in ("roof",) or (axis == 0 and role == "wall" and it["name"] in ("WallLeft", "WallRight", "WallBack")):
                continue
            if axis == 1 and it["name"] in ("WallLeft", "WallRight"):
                continue
            face, edge, _ = ROLE_STYLE[role]
            a0, a1 = it["lo"][axis], it["hi"][axis]
            ax.add_patch(Rectangle((a0, it["lo"][2]), a1 - a0, it["hi"][2] - it["lo"][2], fc=face, ec=edge, lw=0.7,
                                   alpha=0.95 if role != "wall" else 0.55, zorder=2))

    # front elevation: the booth as the customer sees it (front wall cut open at the flap opening)
    ax = af
    ax.set_aspect("equal")
    draw_items(ax, 0)
    face, edge, _ = ROLE_STYLE["wall"]
    for xa, xb in ((-L.W / 2, L.FLAP_X[0]), (L.FLAP_X[1], L.W / 2)):
        ax.add_patch(Rectangle((xa, L.FLAP_Z[0]), xb - xa, L.FLAP_Z[1] - L.FLAP_Z[0], fc=face, ec=edge, lw=0.7, zorder=3))
    ax.add_patch(Rectangle((-L.W / 2, fz0), L.W, L.EAVE_Z - fz0, fc="none", ec=edge, lw=1.2, zorder=4))
    ax.add_patch(Polygon([(-L.W / 2 - 0.1, L.EAVE_Z), (0, L.RIDGE_Z), (L.W / 2 + 0.1, L.EAVE_Z)], closed=True,
                         fc="#a9746e", ec="#6d3f3a", lw=0.8, zorder=4))
    ax.add_patch(Rectangle((L.FLAP_X[0], L.FLAP_Z[0]), L.FLAP_W, L.FLAP_H, fc="none", ec=INK, lw=1.0, ls="--", zorder=5))
    hx, hy, hz = L.HEAD_CENTRE
    ax.add_patch(Circle((hx, hz), need(env, "head", "radius"), fc=HOT, ec="none", zorder=6))
    ax.axhline(0, color=INK, lw=1.0)
    ax.text(-L.W / 2, -0.07, "paving", fontsize=7, color=MUTED, va="top")
    dim(ax, (L.FLAP_X[0], L.FLAP_Z[1]), (L.FLAP_X[1], L.FLAP_Z[1]), f"opening {L.FLAP_W:.2f} m", offset=(0, 0.13))
    dim(ax, (L.FLAP_X[1], L.FLAP_Z[0]), (L.FLAP_X[1], L.FLAP_Z[1]), f"{L.FLAP_H:.2f} m", offset=(0.12, 0))
    dim(ax, (-L.W / 2, 0), (L.W / 2, 0), f"booth width {L.W:.2f} m", offset=(0, -0.22))
    ax.annotate("spinner head", (hx, hz), (hx - 0.05, hz - 0.55), fontsize=7, ha="center", color=HOT,
                arrowprops=dict(arrowstyle="-", color=HOT, lw=0.6), bbox=dict(fc="white", ec="none", pad=0.5))
    for z, text in ((L.COUNTER_Z, f"counter {L.COUNTER_Z - fz0:.2f} m"), (L.EAVE_Z, f"eave {L.EAVE_Z - fz0:.2f} m"),
                    (L.RIDGE_Z, f"ridge {L.RIDGE_Z - fz0:.2f} m"), (fz0, f"booth floor (+{fz0:.2f} m on the paving)")):
        ax.plot([L.W / 2, L.W / 2 + 0.12], [z, z], color=MUTED, lw=0.6)
        ax.text(L.W / 2 + 0.15, z, text, fontsize=7, color=MUTED, va="center")
    ax.set_xlim(-L.W / 2 - 0.25, L.W / 2 + 1.25)
    ax.set_ylim(-0.42, L.RIDGE_Z + 0.2)
    ax.set_xlabel("x [m]")
    ax.set_ylabel("z [m] above the paving")
    ax.set_title("Front elevation, as the customer sees it (heights above the booth floor)", fontsize=9.5, loc="left")
    ax.grid(color=GRID, lw=0.4)
    ax.set_axisbelow(True)

    # side section: y-z, flap opened, robot at the serving station, customer line
    ax = aside
    ax.set_aspect("equal")
    draw_items(ax, 1)
    front = -L.Dp / 2
    ax.add_patch(Polygon([(front, L.EAVE_Z), (front, L.EAVE_Z), (L.Dp / 2, L.EAVE_Z)], closed=True, fc="none"))
    ax.plot([front - 0.1, 0, L.Dp / 2 + 0.1], [L.EAVE_Z, L.RIDGE_Z, L.EAVE_Z], color="#6d3f3a", lw=1.2, alpha=0.4)
    fy, fz = L.flap_edge()
    ax.plot([front, fy], [L.FLAP_Z[1], fz], color="#8a6a43", lw=3.0, solid_capstyle="round", zorder=6)
    ax.add_patch(Wedge((front, L.FLAP_Z[1]), 0.30, -90 - g("booth_flap_open_angle"), -90, fc="none", ec=MUTED, lw=0.6,
                       zorder=6))
    ax.text(front - 0.12, L.FLAP_Z[1] - 0.40, f"{g('booth_flap_open_angle'):.0f}°", fontsize=7, color=MUTED, ha="center")
    ax.text((front + fy) / 2 - 0.05, (L.FLAP_Z[1] + fz) / 2 + 0.10, "sales flap", fontsize=7.5, color="#8a6a43",
            ha="center")
    ax.plot([fy - 0.30, front], [g("asr_headroom")] * 2, color="#b5175a", lw=0.8, ls="--")
    ax.text(fy - 0.30, g("asr_headroom") - 0.06,
            f"{g('asr_headroom'):.2f} m above the paving\n(C7b: flap edge at {fz:.2f} m)", fontsize=7,
            color="#b5175a", va="top")
    ax.axvline(front, color=MUTED, lw=0.6, ls="-.", ymax=0.25)
    ax.text(front - 0.05, 0.25, "customer\nline", fontsize=7, color=MUTED, ha="right")

    # machine head, bubble
    ax.add_patch(Circle((hy, hz), need(env, "head", "radius"), fc=HOT, ec="none", zorder=7))
    pan = items["MachinePan"]
    r_b = g("bubble_base_diameter") / 2
    ax.add_patch(Wedge((hy, L.M_TOP_Z), r_b, 0, 180, fc="#dbeafe55", ec="#7aa6c2", lw=0.8, zorder=7))
    ax.add_patch(Rectangle((hy - r_b, L.M_TOP_Z), 2 * r_b, 0.001, ec="#7aa6c2"))
    ax.text(hy, L.M_TOP_Z + g("bubble_height") + 0.04, "bubble", fontsize=7, ha="center", color="#4b7a99")

    # robot at the serving station (local x points to -y)
    sx, sy, _ = L.ROBOT_STATIONS["serving"]
    for part, ls in (("lower", "-"), ("upper", ":")):
        lo, hi = need(renv, part, "lo"), need(renv, part, "hi")
        ax.add_patch(Rectangle((sy - hi[0], fz0 + lo[2]), hi[0] - lo[0], hi[2] - lo[2], fc=ROBOT_SOFT if ls == "-" else
                               "none", ec=ROBOT, lw=1.0, ls=ls, zorder=8))
    top = fz0 + need(renv, "upper", "hi")[2]
    ax.text(sy, top + 0.06, f"PR2 at 'serving' (parked, {top - fz0:.2f} m)", fontsize=7.5, color=ROBOT, ha="center")
    hx_, hy_, hz_ = L.HANDOVER_XYZ
    ax.plot(hy_, hz_, marker="*", color="#b5175a", ms=11, zorder=9)
    ax.text(hy_ - 0.02, hz_ + 0.07, "handover", fontsize=7, color="#b5175a", ha="center")

    marks = []
    for z, text in ((L.TABLE_Z, f"machine table {L.TABLE_Z - fz0:.2f}"), (L.COUNTER_Z, f"counter {L.COUNTER_Z - fz0:.2f}"),
                    (L.M_TOP_Z, f"pan rim {L.M_TOP_Z - fz0:.3f} (C5: elbow {g('op_elbow_height'):.2f})"),
                    (hz, f"head band {hz - fz0:.2f}"), (L.M_TOP_Z + g("bubble_height"), f"bubble top "
                                                     f"{L.M_TOP_Z + g('bubble_height') - fz0:.2f}"),
                    (L.FLAP_Z[1], f"opening top {L.FLAP_Z[1] - fz0:.2f}"), (L.EAVE_Z, f"eave {L.EAVE_Z - fz0:.2f}")):
        marks.append((z, text))
    last = -1.0
    for z, text in sorted(marks):
        tz = max(z, last + 0.085)    # spread labels that would overlap; the tick stays at the true height
        ax.plot([L.Dp / 2, L.Dp / 2 + 0.08, L.Dp / 2 + 0.12], [z, z, tz], color=MUTED, lw=0.6)
        ax.text(L.Dp / 2 + 0.15, tz, text + " m", fontsize=7, color=MUTED, va="center")
        last = tz
    ax.axhline(0, color=INK, lw=1.0)
    dim(ax, (front, 0), (L.Dp / 2, 0), f"booth depth {L.Dp:.2f} m", offset=(0, -0.22))
    ax.set_xlim(fy - 0.40, L.Dp / 2 + 1.95)
    ax.set_ylim(-0.42, L.RIDGE_Z + 0.2)
    ax.set_xlabel("y [m] (sales front → back wall)")
    ax.set_title("Side section, flap opened; machine items projected (heights above the booth floor)", fontsize=9.5,
                 loc="left")
    ax.grid(color=GRID, lw=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout()
    return save(fig, "booth_elevation.png")


# %% 3. checks


VALUE_KEYS = {   # check id -> (value key, limit key or None, sense, unit); limits not in the JSON come from the test text
    "C3a": ("margin_m", None, ">=", "m"), "C3b": ("gap_m", None, ">", "m"), "C4": ("clearance_m", "required_m", ">=", "m"),
    "C5": ("rim_above_floor_m", "elbow_m", "~", "m"), "C6": ("area_m2", None, ">=", "m²"),
    "C7a": ("headroom_m", None, ">=", "m"), "C7b": ("edge_z_m", None, ">=", "m"), "C8": ("load_w", "supply_w", "<=80%", "W"),
    "C10": ("behind_front_m", None, ">=", "m"), "C12": ("reach_m", None, "<=", "m"), "C13": ("reach_m", None, "<=", "m"),
}


def checks_summary():
    data = provenance.load_fresh("checks")
    results = need(data, "results")
    rows = []
    for r in results:
        cid = r["test"].split()[0]
        text = r["test"][len(cid) + 1:]
        if cid in VALUE_KEYS:
            vk, lk, sense, unit = VALUE_KEYS[cid]
            value = need(r, vk)
            if lk is not None:
                limit = need(r, lk) * (0.8 if sense == "<=80%" else 1.0)
            elif sense == ">":
                limit = 0.0
            else:
                m = re.search(r"(>=|<=|within)\s*([\d.]+)", r["test"])
                if not m:
                    raise KeyError(f"no limit for {cid} in {r['test']!r}")
                limit = float(m.group(2))
            if sense in (">=", ">"):
                margin = (value - limit) / (limit if limit else 1.0)
            elif sense.startswith("<="):
                margin = (limit - value) / limit
            else:   # rim at elbow height: inside the register tolerance band
                tol = g("op_rim_above_elbow_max") if value >= limit else g("op_rim_below_elbow_max")
                margin = 1.0 - abs(value - limit) / tol
            label = f"{value:g} {unit} vs {'≈' if sense == '~' else sense.replace('80%', '')} {limit:g} {unit}"
            rows.append((cid, text, r["passed"], margin, label))
        else:
            rows.append((cid, text, r["passed"], None, "pass/fail" if not r.get("collisions") else "collisions"))
    n_pass = sum(r[2] for r in rows)
    fig, ax = plt.subplots(figsize=(11, 0.36 * len(rows) + 1.3))
    ys = list(range(len(rows)))[::-1]
    for y, (cid, text, ok, margin, label) in zip(ys, rows):
        color = "#2d7a4a" if ok else "#b42318"
        if margin is None:
            ax.plot(0.02, y, marker="s", color=color, ms=7)
            ax.text(0.06, y, "passed (boolean check)" if ok else "FAILED", va="center", fontsize=7.5, color=color)
        else:
            shown = max(min(margin, 1.6), -0.2)
            ax.barh(y, shown, height=0.55, color=color, alpha=0.85)
            ax.text(max(shown, 0) + 0.02, y, f"{label}  (margin {100 * margin:+.0f} %)" + (" ▸" if margin > 1.6 else ""),
                    va="center", fontsize=7.5, color=INK)
        ax.text(-0.03, y, f"{cid}  {text}", ha="right", va="center", fontsize=7.8)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_yticks([])
    ax.set_xlim(-0.03, 2.35)
    ax.set_xticks([0, 0.25, 0.5, 1.0, 1.5])
    ax.set_xticklabels(["limit", "+25 %", "+50 %", "+100 %", "+150 %"], fontsize=7.5)
    ax.set_xlabel("relative margin to the limit (bars clipped at +160 %; C5: share of the elbow tolerance left)",
                  fontsize=8)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    prov = data["_provenance"]
    ax.set_title(f"Design checks: {n_pass}/{len(rows)} pass (data/checks.json, git {prov['git']}, "
                 f"{prov['generated']})", fontsize=10, loc="left", x=-0.95)
    return save(fig, "checks_summary.png")


# %% 4. register


STATUS_ORDER = [  # strongest evidence first; colour by evidence class
    ("SOURCED", "#1b6b45"), ("STANDARD", "#2f8a5b"), ("MEASURED", "#4fa875"), ("SOURCED-VERIFY", "#2c6e9b"),
    ("DERIVED", "#4b8bb8"), ("CALIBRATED", "#7aaed4"), ("PROXY", "#c7861c"), ("ANALOGUE", "#dca64a"),
    ("ILLUSTRATIVE", "#b54848"), ("GAP", "#7a7a7a"),
]


def register_status():
    counts = Pm.status_counts()
    unknown = set(counts) - {s for s, _ in STATUS_ORDER}
    if unknown:
        raise KeyError(f"statuses without a colour: {unknown}")
    total = sum(counts.values())
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ys = list(range(len(STATUS_ORDER)))[::-1]
    for y, (status, color) in zip(ys, STATUS_ORDER):
        n = counts.get(status, 0)
        ax.barh(y, n, color=color, height=0.62)
        ax.text(n + 0.8, y, f"{n}  ({100 * n / total:.0f} %)", va="center", fontsize=8, color=INK if n else MUTED)
    ax.set_yticks(ys)
    ax.set_yticklabels([s for s, _ in STATUS_ORDER], fontsize=8.5)
    ax.set_xlim(0, max(counts.values()) * 1.18)
    ax.set_xlabel("register entries")
    ax.grid(axis="x", color=GRID, lw=0.4)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    strong = sum(counts.get(s, 0) for s in ("SOURCED", "STANDARD", "MEASURED"))
    ax.set_title(f"Parameter register: {total} entries, {100 * strong / total:.0f} % sourced, standard or measured, "
                 f"{100 * counts.get('ILLUSTRATIVE', 0) / total:.0f} % illustrative", fontsize=10, loc="left")
    return save(fig, "register_status.png")


if __name__ == "__main__":
    for f in (booth_plan, booth_elevation, checks_summary, register_status):
        f()
