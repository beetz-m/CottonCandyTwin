"""
Measure the robot's parked envelope in the CRAM world and hand it to the twin's checks (``data/robot_envelope.json``),
so the twin's robot-fit check uses measured, not typed, dimensions.

Run: cram/run.sh python -m cotton_candy.robot_envelope
"""

from __future__ import annotations

import importlib.util
import os

import numpy as np

from semantic_digital_twin.robots.pr2 import PR2

from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.datastructures.definitions import StaticJointState

from cotton_candy.booth_world import twin_root


def parked_envelope(world, robot) -> dict:
    """
    :return: Per-link axis-aligned bounding boxes of the parked robot's collision shapes in its base frame, plus
        their union ("lower": base, casters, wheels; "upper": everything else).
    """
    base_inverse = np.linalg.inv(robot.root.global_pose.to_np())
    links, parts = [], {"lower": [], "upper": []}
    for body in robot.bodies:
        corners = []
        for shape in body.collision.shapes:
            world_T_shape = body.global_pose.to_np() @ shape.origin.to_np()
            corners += [(base_inverse @ world_T_shape @ np.append(c, 1.0))[:3] for c in shape_corners(shape)]
        if not corners:
            continue
        corners = np.array(corners)
        part = "lower" if any(key in body.name.name for key in ("base", "caster", "wheel")) else "upper"
        parts[part] += list(corners)
        links.append({"name": body.name.name, "lo": corners.min(axis=0).round(4).tolist(),
                      "hi": corners.max(axis=0).round(4).tolist()})
    union = {name: {"lo": np.array(c).min(axis=0).round(4).tolist(), "hi": np.array(c).max(axis=0).round(4).tolist()}
             for name, c in parts.items()}
    return union | {"links": links,
                    "note": "parked PR2 collision shapes, base frame (x forward, y left, z up from the floor)"}


def shape_corners(shape) -> list:
    """
    :return: The 8 corners of the shape's local bounding box.
    """
    bb = shape.local_frame_bounding_box
    lo = np.array([bb.min_x, bb.min_y, bb.min_z])
    hi = np.array([bb.max_x, bb.max_y, bb.max_z])
    return [np.array([x, y, z]) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def parked_robot_world(robot_type=PR2):
    """
    :return: A world holding only the robot, arms in their PARK joint state (no booth: the booth's stations depend on
        this measurement).
    """
    world = URDFParser.from_file(
        file_path=robot_type.get_ros_file_path(),
        use_visual_as_collision_backup=robot_type.uses_visual_as_collision_backup,
    ).parse()
    robot = robot_type.from_world(world)
    for arm in robot.all_arms:
        park = arm.get_joint_state_by_type(StaticJointState.PARK)
        for connection, value in zip(park.connections, park.target_values):
            connection.position = value
    return world, robot


def main() -> None:
    world, robot = parked_robot_world()
    envelope = parked_envelope(world, robot)
    site = os.path.join(twin_root(), "site")
    spec = importlib.util.spec_from_file_location("twin_provenance", os.path.join(site, "provenance.py"))
    provenance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(provenance)
    out = provenance.write("robot_envelope", {"robot": "PR2", "parked": envelope}, [os.path.abspath(__file__)])
    print("wrote", out, {k: envelope[k] for k in ("lower", "upper")}, len(envelope["links"]), "links")


if __name__ == "__main__":
    main()
