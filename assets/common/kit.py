"""The LabAutomationTwin mesh kit (assets/common/meshkit.py, loaded read-only by file path) pointed at the site
material library (assets/materials/twin_materials.usda).

Usage:  from assets.common.kit import Kit, new_asset, sdt
"""

import importlib.util
import os

from pxr import Sdf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAT = os.path.expanduser("~/Documents/LabAutomationTwin")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SM = _load("twin_build_materials", os.path.join(ROOT, "assets", "materials", "build_materials.py"))
meshkit = _load("lat_meshkit", os.path.join(LAT, "assets", "common", "meshkit.py"))
meshkit.MATLIB = os.path.join(ROOT, "assets", "materials", "twin_materials.usda")
meshkit.TILE_M.update(SM.TILE_M)
Kit, new_asset = meshkit.Kit, meshkit.new_asset


def sdt(prim, **attrs):
    """Write sdt:* attributes (identity / provenance of a twin node) on a prim."""
    for k, v in attrs.items():
        if isinstance(v, bool):
            t = Sdf.ValueTypeNames.Bool
        elif isinstance(v, int):
            t = Sdf.ValueTypeNames.Int
        elif isinstance(v, float):
            t = Sdf.ValueTypeNames.Double
        elif isinstance(v, (list, tuple)):
            t = Sdf.ValueTypeNames.StringArray
            v = [str(x) for x in v]
        else:
            t = Sdf.ValueTypeNames.String
        prim.CreateAttribute(f"sdt:{k}", t, custom=True).Set(v)
