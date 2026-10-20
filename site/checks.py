"""Design checks of the Cotton Candy Booth twin. Prints PASS/FAIL with the measured values, writes data/checks.json
(with provenance), exits 1 on any failure.

Machine envelope: if data/asset_envelopes.json exists (written by the asset builders from the built USD), the checks
use the MEASURED machine/pan/head boxes; otherwise the register envelope from layout.py (reported as 'register').

Run: $E site/checks.py
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout as L  # noqa: E402
import params as Pm  # noqa: E402
import provenance  # noqa: E402

g = Pm.get
ROOT = os.path.dirname(HERE)
results = []


def check(name, ok, **values):
    results.append(dict(test=name, passed=bool(ok), **values))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  " + ", ".join(f"{k}={v}" for k, v in values.items()), flush=True)


def overlap(a, b, tol=1e-3):
    return all(a["lo"][i] < b["hi"][i] - tol and b["lo"][i] < a["hi"][i] - tol for i in range(3))


def dist_point_box(p, b):
    d = [max(b["lo"][i] - p[i], 0.0, p[i] - b["hi"][i]) for i in range(3)]
    return math.sqrt(sum(v * v for v in d))


def main():
    items = {it["name"]: it for it in L.items()}
    source = "register"
    env_path = os.path.join(ROOT, "data", "asset_envelopes.json")
    head_r = g("head_band_diameter") / 2
    head_c = L.HEAD_CENTRE
    if os.path.exists(env_path):
        env = provenance.load_fresh("asset_envelopes")
        mx, my = L.MACHINE_XY
        for name, key in (("Machine", "machine"), ("MachinePan", "pan")):
            lo, hi = env[key]["lo"], env[key]["hi"]           # asset frame: origin floor centre of the machine
            items[name]["lo"] = (mx + lo[0], my + lo[1], L.TABLE_Z + lo[2])
            items[name]["hi"] = (mx + hi[0], my + hi[1], L.TABLE_Z + hi[2])
        hc = env["head"]["centre"]
        head_c = (mx + hc[0], my + hc[1], L.TABLE_Z + hc[2])
        head_r = env["head"]["radius"]
        source = "MEASURED (asset_envelopes.json)"
    print(f"machine envelope source: {source}")

    # C1 containment
    inside = [n for n, it in items.items() if it["role"] not in ("wall", "roof", "door")]
    bad = [n for n in inside if not (items[n]["lo"][0] >= L.X0 - 1e-6 and items[n]["hi"][0] <= L.X1 + 1e-6 and
                                     items[n]["lo"][1] >= L.Y0 - 1e-6 and items[n]["hi"][1] <= L.Y1 + 1e-6)]
    check("C1 everything inside the booth interior", not bad, outside=bad)

    # C2 no collisions between fixed items (stacking = touching faces, allowed)
    pairs = []
    names = [n for n in inside if items[n]["role"] not in ("pan",)]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if {a, b} <= {"SideShelf", "SugarTubs"}:       # tubs stand on the shelf
                continue
            if overlap(items[a], items[b]):
                pairs.append((a, b))
    check("C2 no overlapping fixed items", not pairs, overlaps=pairs)

    # C3 machine stands on the table with margin; pan clears the walls
    m, t, pan = items["Machine"], items["MachineTable"], items["MachinePan"]
    margin = min(m["lo"][0] - t["lo"][0], t["hi"][0] - m["hi"][0], m["lo"][1] - t["lo"][1], t["hi"][1] - m["hi"][1])
    check("C3a machine cabinet footprint on the table (margin >= 0.03 m)", margin >= 0.03, margin_m=round(margin, 3),
          on_top=abs(m["lo"][2] - t["hi"][2]) < 1e-6)
    gap = min(pan["lo"][0] - L.X0, pan["lo"][1] - L.Y0)
    check("C3b pan rim clears the walls", gap >= 0.02, gap_m=round(gap, 3))

    # C4 heat clearance: heating band surface to combustibles (HN_FW 0.50 m)
    req = g("reg_heat_clearance")
    dists = {n: round(dist_point_box(head_c, it) - head_r, 3) for n, it in items.items() if it["combustible"]}
    worst = min(dists, key=dists.get)
    check("C4 heating band >= 0.50 m from combustibles", dists[worst] >= req, nearest=worst,
          clearance_m=dists[worst], required_m=req)

    # C5 ergonomics: pan rim at elbow height of the operator
    rim = pan["hi"][2] - L.FLOOR_Z
    elbow = g("op_elbow_height")
    ok = elbow - g("op_rim_below_elbow_max") <= rim <= elbow + g("op_rim_above_elbow_max")
    check("C5 pan rim at operator elbow height", ok, rim_above_floor_m=round(rim, 3), elbow_m=elbow,
          rim_on_counter_would_be_m=round(g("booth_counter_height") + (pan["hi"][2] - m["lo"][2]), 3))

    # C6 movement area (ASR A1.2): free floor = interior minus every footprint below 1.8 m; the connected region
    # around the operator must be >= 1.5 m2 and contain a 1.0 x 1.0 m square
    from shapely.geometry import Point, box as sbox
    from shapely.ops import unary_union
    free = sbox(L.X0, L.Y0, L.X1, L.Y1).difference(unary_union(
        [sbox(it["lo"][0], it["lo"][1], it["hi"][0], it["hi"][1]) for n, it in items.items()
         if n in inside and it["lo"][2] < L.FLOOR_Z + 1.8]))
    ox, oy, _ = L.OPERATOR_POSE
    regions = list(getattr(free, "geoms", [free]))
    region = next((r_ for r_ in regions if r_.contains(Point(ox, oy))), None)
    side = g("asr_move_width")
    fits = False
    if region is not None:
        x0, y0, x1, y1 = region.bounds
        steps = [i / 50 for i in range(51)]
        fits = any(region.contains(sbox(x0 + a * (x1 - x0 - side), y0 + b * (y1 - y0 - side),
                                        x0 + a * (x1 - x0 - side) + side, y0 + b * (y1 - y0 - side) + side))
                   for a in steps for b in steps) if (x1 - x0 >= side and y1 - y0 >= side) else False
    area = region.area if region is not None else 0.0
    check("C6 operator movement area >= 1.5 m2 containing a 1.0 x 1.0 m square", area >= g("asr_move_area") and fits,
          area_m2=round(area, 3), square_fits=fits, operator_in_free_region=region is not None)

    # C7 headroom: inside and under the open flap (ASR A1.8)
    inner = L.EAVE_Z - L.FLOOR_Z
    fy, fz = L.flap_edge()
    header = L.EAVE_Z - L.FLAP_Z[1]
    check("C7a interior headroom >= 2.00 m", inner >= g("asr_headroom"), headroom_m=round(inner, 3))
    check("C7b open flap edge >= 2.00 m above the customers", fz >= g("asr_headroom"), edge_z_m=round(fz, 3),
          edge_y_m=round(fy, 3), header_m=round(header, 3))

    # C8 electrical load vs supply (80 % continuous-load derating, ILLUSTRATIVE rule)
    load = g("m_power_230") + g("el_led_lighting_w") + g("el_sign_w")
    cap = g("el_supply_voltage") * g("el_supply_current")
    check("C8 electrical load <= 80 % of 230 V / 16 A", load <= 0.8 * cap, load_w=load, current_a=round(
        load / g("el_supply_voltage"), 2), supply_w=cap, rcd=g("reg_rcd_required"))

    # C9 regulation items present
    board = items["InfoBoard"]["sdt"]["text"]
    present = {"handwash": "HandwashStation" in items, "extinguisher": "FireExtinguisher" in items,
               "rcd_distributor": "PowerDistributor" in items, "mit Farbstoff": g("reg_colour_label") in board,
               "azo warning": g("reg_azo_warning").split(": ", 1)[1] in board, "allergen milk": "Milch" in board}
    check("C9 hygiene / labelling / fire items present", all(present.values()), **present)

    # C10 show and safety: head visible through the flap, out of customer reach
    hx, hy, hz = head_c
    visible = L.FLAP_X[0] < hx < L.FLAP_X[1]
    reach = hy - (-g("booth_depth") / 2)
    check("C10 head visible through the flap and >= 0.5 m behind the customer line", visible and reach >= 0.5,
          visible=visible, behind_front_m=round(reach, 3))

    # C11 process consistency: head refill interval vs. rated output
    per_min = g("op_output_rate") * g("portion_sugar")
    refill_s = 60 * g("head_sugar_capacity") * g("head_fill_fraction") / per_min
    check("C11 head capacity sustains >= 1 portion per fill", g("head_sugar_capacity") * g("head_fill_fraction")
          >= g("portion_sugar"), sugar_g_per_min=round(per_min * 1000, 1), refill_every_s=round(refill_s, 1))

    # C12 sticks within reach of the operator
    ox, oy, _ = L.OPERATOR_POSE
    sh = items["StickHolder"]
    sxy = ((sh["lo"][0] + sh["hi"][0]) / 2, (sh["lo"][1] + sh["hi"][1]) / 2)
    r = math.hypot(sxy[0] - ox, sxy[1] - oy)
    check("C12 stick holder within 0.80 m of the operator", r <= 0.80, reach_m=round(r, 3))

    # C13 working sugar within reach of the operator (refill every ~30 s)
    st = items["SugarWorkTray"]
    r = math.hypot((st["lo"][0] + st["hi"][0]) / 2 - ox, (st["lo"][1] + st["hi"][1]) / 2 - oy)
    check("C13 working sugar within 0.80 m of the operator", r <= 0.80, reach_m=round(r, 3))

    failed = [r_["test"] for r_ in results if not r_["passed"]]
    out = provenance.write("checks", dict(machine_envelope=source, results=results, failed=failed),
                           [os.path.join(HERE, f) for f in ("params.py", "layout.py", "checks.py")])
    print(f"\n{len(results) - len(failed)}/{len(results)} passed -> {os.path.relpath(out, ROOT)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
