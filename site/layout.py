"""Layout model of the Cotton Candy Booth twin (pure Python, no USD). Single source of placements.

Frame "B" (booth): origin on the paving at the centre of the booth footprint; +x to the right as seen by a customer
standing in front of the booth, +y from the sales front (y = -depth/2) to the back wall (y = +depth/2), z up, z = 0 on the paving.
Metres. The booth floor is at FLOOR_Z. Customers stand in front of the sales front.

Everything is an axis-aligned box ITEM with a role and flags that the checks, the scene builder and the ontology
read. Machine geometry here is the register envelope; once the asset is built, site/checks.py re-measures it from the
USD (data/asset_envelopes.json) - measure, don't type.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import params as Pm  # noqa: E402

g = Pm.get
W, Dp = g("booth_width"), g("booth_depth")
T = g("booth_wall_panel_t")
FLOOR_Z = g("booth_floor_height")
X0, X1 = -W / 2 + T, W / 2 - T          # interior faces of the side walls
Y0, Y1 = -Dp / 2 + T, Dp / 2 - T        # interior faces of front / back wall
EAVE_Z = FLOOR_Z + g("booth_eave_height")
RIDGE_Z = FLOOR_Z + g("booth_ridge_height")
COUNTER_Z = FLOOR_Z + g("booth_counter_height")
FLAP_W, FLAP_H = g("booth_flap_width"), g("booth_flap_height")
FLAP_X = (-FLAP_W / 2, FLAP_W / 2)
FLAP_Z = (COUNTER_Z, COUNTER_Z + FLAP_H)          # opening; flap hinged at the top edge
TABLE_Z = FLOOR_Z + g("machine_table_height")
GN16 = g("gn16_size")
CARTON = g("sugar_carton_size")

# machine placement (ILLUSTRATIVE): the heating band keeps 0.5 m to the wooden left and front walls (C4)
HEAT_SETBACK = g("reg_heat_clearance") + g("head_band_diameter") / 2 + 0.002
MACHINE_XY = (X0 + HEAT_SETBACK, Y0 + HEAT_SETBACK)
MACHINE_YAW = 0.0                                  # controls face the operator (+y)
PAN_R_OUT = g("pan_outer_diameter") / 2
M_TOP_Z = TABLE_Z + g("m_overall_height")          # pan rim
HEAD_Z = TABLE_Z + g("m_feet_height") + g("m_cabinet_height") + 0.075   # band centre ~75 mm above the cabinet (photo)
TABLE_X1 = MACHINE_XY[0] + PAN_R_OUT + 0.27        # machine table: pan + room for the sugar carton (C4: >= 0.5 m)
TABLE_Y1 = MACHINE_XY[1] + PAN_R_OUT + 0.03        # table edge on the operator side, just behind the pan
STEEL_X1 = max(MACHINE_XY[0] + HEAT_SETBACK, TABLE_X1 + 0.10)   # wood >= 0.5 m from the band (C4), steel >= 0.10 m

# robot stations (base x, y, yaw), facing the sales front. The forward reach of the parked robot is MEASURED in the
# CRAM world (data/robot_envelope.json, cram/cotton_candy/robot_envelope.py); before that exists, the register base
# footprint stands in.
def robot_envelope():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "robot_envelope.json")
    if os.path.exists(path):
        import provenance
        return provenance.load_fresh("robot_envelope")["parked"]
    half = g("robot_base_footprint") / 2
    return {"lower": {"lo": [-half, -half, 0.0], "hi": [half, half, 1.0]},
            "upper": {"lo": [-half, -half, 0.3], "hi": [half, half, 2.0]}}


def robot_buffer(link_name):
    """Collision-avoidance buffer of a robot link (PR2 rules, register PR2_CRAM_CFG)."""
    if "base_link" in link_name:
        return g("robot_buffer_base_booth")
    if link_name[:2] in ("l_", "r_") and "gripper" not in link_name:
        return g("robot_buffer_arm")
    return g("robot_buffer_default")


_ENV = robot_envelope()
_FRONT_ITEMS_TOP = M_TOP_Z + g("bubble_height") - FLOOR_Z    # highest thing in front of the robot: the bubble dome
_FORWARD = max([l["hi"][0] + robot_buffer(l["name"]) for l in _ENV["links"] if l["lo"][2] < _FRONT_ITEMS_TOP]
               or [_ENV["lower"]["hi"][0] + g("robot_buffer_base_booth")])
_BASE_FORWARD = max(l["hi"][0] + robot_buffer(l["name"]) for l in _ENV["links"] if "base" in l["name"])
ROBOT_STATIONS = {
    # nearer the machine, for working with raised arms (pouring); only the base must clear (C15) - never park here
    # 0.05 m behind the base buffer: nearer and the upper arm lies on the pan rim when reaching over the pan,
    # farther and the head is out of reach (kinematic tests 2026-10-20: 0.083 fails, 0.114 works, 0.155 fails)
    "machine_close": (MACHINE_XY[0] + 0.40, TABLE_Y1 + _BASE_FORWARD + 0.05, -math.pi / 2),
    "machine": (MACHINE_XY[0] + 0.40, TABLE_Y1 + _FORWARD, -math.pi / 2),
    "serving": (0.33, Y0 + g("booth_counter_depth") + _FORWARD, -math.pi / 2),
}
# over the counter, on the side of the robot's right (-x) arm, which holds the stick
HANDOVER_XYZ = (ROBOT_STATIONS["serving"][0] - 0.15, Y0 + 0.37, COUNTER_Z + 0.30)



def box(name, role, lo, hi, combustible=False, **sdt):
    return dict(name=name, role=role, lo=tuple(lo), hi=tuple(hi), combustible=combustible, sdt=sdt)


def items():
    sh = g("side_shelf_depth")
    hw = g("handwash_unit")
    mx, my = MACHINE_XY
    cw, cd = g("m_cabinet_width"), g("m_cabinet_depth")
    return [
        # shell (wood)
        box("WallLeft", "wall", (-W / 2, -Dp / 2, FLOOR_Z), (X0, Dp / 2, EAVE_Z), True, material="spruce 3-ply"),
        box("WallRight", "wall", (X1, -Dp / 2, FLOOR_Z), (W / 2, Dp / 2, EAVE_Z), True, material="spruce 3-ply"),
        box("WallBack", "wall", (-W / 2, Y1, FLOOR_Z), (W / 2, Dp / 2, EAVE_Z), True, material="spruce 3-ply"),
        box("WallFrontBelowCounter", "wall", (-W / 2, -Dp / 2, FLOOR_Z), (W / 2, Y0, COUNTER_Z), True),
        box("WallFrontHeader", "wall", (-W / 2, -Dp / 2, FLAP_Z[1]), (W / 2, Y0, EAVE_Z), True),
        box("RoofUnderside", "roof", (-W / 2, -Dp / 2, EAVE_Z), (W / 2, Dp / 2, EAVE_Z + 0.02), True),
        # furniture
        box("MachineTable", "table", (X0, Y0, FLOOR_Z), (TABLE_X1, TABLE_Y1, TABLE_Z), False, material="stainless"),
        box("CounterSteel", "counter", (TABLE_X1, Y0, FLOOR_Z), (STEEL_X1, Y0 + g("booth_counter_depth"), COUNTER_Z),
            False, material="stainless top and front cladding (non-combustible zone next to the machine, C4)"),
        box("SalesCounter", "counter", (STEEL_X1, Y0, FLOOR_Z), (X1, Y0 + g("booth_counter_depth"), COUNTER_Z), True,
            material="spruce, oiled worktop"),
        box("SideShelf", "shelf", (X1 - sh, -0.30, FLOOR_Z), (X1, 0.40, FLOOR_Z + 1.60), True, material="spruce"),
        box("HandwashStation", "handwash", (X1 - hw[0], Y1 - hw[1], FLOOR_Z), (X1, Y1, FLOOR_Z + hw[2]), True,
            regulation="EU852 Annex II Ch.III 2(a); MS_MB25"),
        box("FireExtinguisher", "safety", (X0, Y1 - 0.17, FLOOR_Z + 0.75), (X0 + 0.135, Y1, FLOOR_Z + 1.35), False,
            regulation="6 kg ABC, EN 3"),
        box("PowerDistributor", "electrical", (X1 - 0.12, 0.42, FLOOR_Z + 1.30),
            (X1, 0.52, FLOOR_Z + 1.60), False, regulation="RCD 30 mA, IP44"),
        box("DoorBack", "door", (-0.20, Y1 - 0.02, FLOOR_Z), (-0.20 + g("booth_side_door_width"), Y1, FLOOR_Z + 1.95)),
        # machine (register envelope; re-measured from the asset later)
        box("Machine", "machine", (mx - cw / 2, my - cd / 2, TABLE_Z), (mx + cw / 2, my + cd / 2, M_TOP_Z), False,
            model="Gold Medal Econo Floss 3017 export (reference)"),
        box("MachinePan", "pan", (mx - PAN_R_OUT, my - PAN_R_OUT, M_TOP_Z - g("pan_height")),
            (mx + PAN_R_OUT, my + PAN_R_OUT, M_TOP_Z), False),
        # consumables (combustible)
        box("StickHolder", "consumable", (X0, 0.12, FLOOR_Z + 0.95), (X0 + 0.10, 0.24, FLOOR_Z + 0.95 +
            g("stick_length")), True, content="wall quiver, pine sticks 40 cm 4x4 mm"),
        box("SugarCarton", "consumable", (TABLE_X1 - CARTON[0] - 0.01, TABLE_Y1 - CARTON[1] - 0.02, TABLE_Z),
            (TABLE_X1 - 0.01, TABLE_Y1 - 0.02, TABLE_Z + CARTON[2]), True,
            content="half-gallon Flossugar carton with E-Z pour spout (GM_MAN_EXP p. 9), cardboard"),
        box("Sponge", "cleaning", (TABLE_X1 - 0.12, TABLE_Y1 - 0.24, TABLE_Z), (TABLE_X1 - 0.02, TABLE_Y1 - 0.17,
            TABLE_Z + 0.03), False, content="damp cleaning sponge (wet: not a fire load; GM_MAN_EXP p. 13 'Wipe all "
            "surfaces with a clean, damp cloth')"),
        box("BagRail", "consumable", (0.10, Y0 + 0.02, FLAP_Z[1] - 0.50), (1.00, Y0 + 0.08, FLAP_Z[1] - 0.02), True,
            content="filled floss bags on display"),
        box("SugarTubs", "consumable", (X1 - sh, -0.28, FLOOR_Z + 0.55), (X1, 0.38, FLOOR_Z + 0.85), True,
            content="3 x 10 L tubs: white, pink (E129), blue (E133)"),
        box("CashBox", "sales", (X1 - 0.40, Y0 + 0.36, COUNTER_Z), (X1 - 0.15, Y0 + 0.56, COUNTER_Z + 0.09), False),
        box("InfoBoard", "label", (X1 - 0.90, Y0 + 0.005, COUNTER_Z), (X1 - 0.45, Y0 + 0.03, COUNTER_Z + 0.30), True,
            text="Zuckerwatte 3 EUR | mit Farbstoff | E129: Kann Aktivitaet und Aufmerksamkeit bei Kindern "
                 "beeintraechtigen. | enthaelt Milch (Laktose)"),
    ]


OPERATOR_POSE = (MACHINE_XY[0], MACHINE_XY[1] + PAN_R_OUT + 0.25, FLOOR_Z)   # stands behind the pan


def flap_edge(angle_deg=None):
    """Edge of the opened sales flap (hinged at the top of the opening, rotating outward/upward)."""
    a = math.radians(g("booth_flap_open_angle") if angle_deg is None else angle_deg)
    return -Dp / 2 - FLAP_H * math.sin(a), FLAP_Z[1] - FLAP_H * math.cos(a)


HEAD_CENTRE = (MACHINE_XY[0], MACHINE_XY[1], HEAD_Z)

if __name__ == "__main__":
    for it in items():
        print(f"{it['name']:<22} {it['role']:<12} lo={tuple(round(v, 3) for v in it['lo'])} "
              f"hi={tuple(round(v, 3) for v in it['hi'])}")
    print("head centre", tuple(round(v, 3) for v in HEAD_CENTRE), "flap edge (y, z)",
          tuple(round(v, 3) for v in flap_edge()))
