"""Shared Isaac Sim 6.2 path-tracing setup for the site renders (one GPU job at a time).

Use inside a script that has already created SimulationApp({"renderer": "PathTracing", ...}).
"""

import os

import numpy as np


def configure(spp=16, sub=48, bounces=8):
    import carb
    s = carb.settings.get_settings()
    s.set("/rtx/rendermode", "PathTracing")
    s.set("/rtx/pathtracing/spp", spp)
    s.set("/rtx/pathtracing/totalSpp", spp * sub)
    s.set("/rtx/pathtracing/maxBounces", bounces)
    s.set("/rtx/pathtracing/maxSpecularAndTransmissionBounces", bounces)
    s.set("/rtx/pathtracing/optixDenoiser/enabled", True)
    s.set("/rtx/post/aa/op", 2)
    return sub


def daylight(stage, root="/World/Light", sun_elev=38.0, sun_az=205.0, sun=2.6, sky=900.0):
    """Physically scaled-down outdoor light: a distant sun + a bluish sky dome (render-only)."""
    from pxr import Gf, UsdGeom, UsdLux
    d = UsdLux.DistantLight.Define(stage, f"{root}/Sun")
    d.CreateIntensityAttr(sun * 1000)
    d.CreateAngleAttr(0.53)
    d.CreateColorAttr(Gf.Vec3f(1.0, 0.96, 0.9))
    x = UsdGeom.Xformable(d)
    x.AddRotateZOp().Set(float(sun_az))
    x.AddRotateXOp().Set(float(90 - sun_elev))
    dome = UsdLux.DomeLight.Define(stage, f"{root}/Sky")
    dome.CreateIntensityAttr(sky)
    dome.CreateColorAttr(Gf.Vec3f(0.78, 0.86, 1.0))
    return d, dome


class Camera:
    def __init__(self, stage, res, sub, path="/World/RenderOnly/Cam", far=8000.0):
        import omni.replicator.core as rep
        from pxr import Gf, UsdGeom
        cam = UsdGeom.Camera.Define(stage, path)
        cam.CreateHorizontalApertureAttr(36.0)
        cam.CreateVerticalApertureAttr(36.0 * res[1] / res[0])
        cam.CreateClippingRangeAttr(Gf.Vec2f(0.05, far))
        self.cam, self.op, self.rep, self.sub = cam, UsdGeom.Xformable(cam.GetPrim()).AddTransformOp(), rep, sub
        self.rp = rep.create.render_product(path, res)
        self.rgb = rep.AnnotatorRegistry.get_annotator("rgb")
        self.rgb.attach(self.rp)

    def shot(self, out, eye, target, focal=24.0):
        from PIL import Image
        from pxr import Gf
        self.op.Set(Gf.Matrix4d().SetLookAt(Gf.Vec3d(*map(float, eye)), Gf.Vec3d(*map(float, target)),
                                           Gf.Vec3d(0, 0, 1)).GetInverse())
        self.cam.GetFocalLengthAttr().Set(float(focal))
        self.rep.orchestrator.step(rt_subframes=self.sub, delta_time=0.0)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        Image.fromarray(np.asarray(self.rgb.get_data())[..., :3].astype(np.uint8)).save(out)
        print("[render]", out, flush=True)
        return out
