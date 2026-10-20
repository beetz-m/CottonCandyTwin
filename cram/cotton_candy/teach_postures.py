"""
Teach-in of arm postures for the booth: drive the robot along a route that works and record the joint positions at
the poses that later plans start from (``data/robot_postures.json`` in the twin, with provenance).

A 7-DoF arm reaching over the floss pan can end in an elbow-low configuration that rests on the pan rim; starting
the pour from a recorded elbow-up posture (a joint-space move) avoids that local minimum.

Run: cram/run.sh python -m cotton_candy.teach_postures
"""

from __future__ import annotations

import importlib.util
import math
import os

from coraplex.datastructures.dataclasses import Context
from coraplex.execution_environment import kinematically_simulated_robot
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from coraplex.robot_plans.motions.gripper import MoveToolCenterPointMotion
from scipy.spatial.transform import Rotation
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.spatial_types.spatial_types import Pose

from cotton_candy.booth_world import BoothWorldBuilder, RobotStation, twin_root
from cotton_candy.manipulation_categories import ApproachDirection, TransportingAction
from cotton_candy.semantic_annotations import CottonCandyMachine, SugarCarton


def pour_approach_posture(grip_height: float = 0.03, pour_height: float = 0.24, tilt: float = 1.2) -> dict:
    """
    :return: Joint positions of the right arm with the carton held above the near side of the pan, reached from the
        carton's place via the route that works (pick from the machine station, drive to the close station, move).
    """
    world = BoothWorldBuilder().build()
    robot = world.get_semantic_annotations_by_type(PR2)[0]
    machine = world.get_semantic_annotations_by_type(CottonCandyMachine)[0]
    carton = world.get_semantic_annotations_by_type(SugarCarton)[0]
    arm = robot.right_arm
    context = Context(world, robot, sampling_seed=0)
    half = float(carton.get_tool_frame().global_pose.to_np()[2, 3] - carton.root.global_pose.to_np()[2, 3])
    head = machine.spinner_head.root.global_pose.to_np()[:3, 3]
    reach = (2 * half - grip_height) * math.sin(tilt)
    qx, qy, qz, qw = Rotation.from_euler("xyz", list(ApproachDirection.TOWARDS_SALES_FRONT.value)).as_quat()
    approach = Pose.from_xyz_quaternion(
        pos_x=float(head[0]), pos_y=float(head[1]) + reach + 0.25, pos_z=float(head[2]) + pour_height + 0.15,
        quat_x=qx, quat_y=qy, quat_z=qz, quat_w=qw, reference_frame=world.root,
    )
    plan = sequential(
        [
            MoveTorsoAction(TorsoState.MID),
            TransportingAction(carton, arm, ApproachDirection.TOWARDS_SALES_FRONT,
                               grasp_offset=(0.0, 0.0, -half + grip_height)),
            NavigateAction(RobotStation.MACHINE_CLOSE.pose(world.root)),
            MoveToolCenterPointMotion(approach, arm, allow_gripper_collision=True),
        ],
        context,
    )
    with kinematically_simulated_robot(collision_avoidance=True):
        plan.perform()
    return {connection.name.name: float(connection.position) for connection in arm.connections
            if hasattr(connection, "position")}


def main() -> None:
    postures = {"pour_approach_right_arm": pour_approach_posture()}
    site = os.path.join(twin_root(), "site")
    spec = importlib.util.spec_from_file_location("twin_provenance", os.path.join(site, "provenance.py"))
    provenance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(provenance)
    out = provenance.write("robot_postures", {"robot": "PR2", "postures": postures,
                                               "note": "taught by cotton_candy.teach_postures (kinematic, CA on)"},
                           [os.path.abspath(__file__), os.path.join(site, "layout.py")])
    print("wrote", out, postures)


if __name__ == "__main__":
    main()
