"""
The scene graph of the cotton candy booth as a semantic digital twin world.

Placements and dimensions come from the twin's single layout model and parameter register
(``site/layout.py``, ``site/params.py`` of the CottonCandyTwin project), loaded by file path so the CRAM world and
the Isaac Sim stage are built from the same numbers. The world frame is the booth frame "B": origin on the paving
at the centre of the booth, +y from the sales front to the back wall, z up.

Geometry is built from primitives (boxes and cylinders) with the colours of the twin's material choices; the
machine's operating elements are revolute connections so that actions move them.
"""

from __future__ import annotations

import importlib.util
import math
import os
import sys
from dataclasses import dataclass, field
from enum import Enum

from typing_extensions import Dict, List, Tuple, Type

from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.collision_checking.collision_rules import AvoidExternalCollisions
from semantic_digital_twin.datastructures.definitions import StaticJointState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.semantic_annotations.semantic_annotations import Handle, Human
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Pose, Vector3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    Connection6DoF,
    FixedConnection,
    RevoluteConnection,
)
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedomLimits
from semantic_digital_twin.world_description.geometry import Box, Color, Cylinder, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

from cotton_candy.semantic_annotations import (
    CandyStick,
    ControlKnob,
    CottonCandyBooth,
    CottonCandyMachine,
    FireExtinguisher,
    FlossPan,
    HandoverZone,
    HandwashStation,
    InformationBoard,
    LockHandle,
    RockerSwitch,
    SalesFlap,
    SpinnerHead,
    Sponge,
    StickQuiver,
    SugarCarton,
)


# %% the twin's layout model


class TwinModule(Enum):
    """
    The modules of the CottonCandyTwin project this world is built from, loaded by file path.
    """

    PARAMS = "params"
    LAYOUT = "layout"

    @property
    def path(self) -> str:
        """
        :return: The module file in the twin's ``site`` directory.
        """
        return os.path.join(twin_root(), "site", f"{self.value}.py")

    def load(self):
        """
        :return: The loaded module (the layout imports the register by name, so ``site`` goes on the path).
        """
        site = os.path.dirname(self.path)
        if site not in sys.path:
            sys.path.insert(0, site)
        spec = importlib.util.spec_from_file_location(f"cotton_candy_twin_{self.value}", self.path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def twin_root() -> str:
    """
    :return: The CottonCandyTwin project directory (``COTTON_CANDY_TWIN`` overrides the default next to this
        package).
    """
    default = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.environ.get("COTTON_CANDY_TWIN", default)


# %% colours of the twin's materials


class Finish(Enum):
    """
    The surface colours of the booth's materials (ILLUSTRATIVE choices of the twin, see its register).
    """

    SPRUCE = (0.78, 0.62, 0.42, 1.0)
    PINK_PAINT = (0.93, 0.55, 0.72, 1.0)
    WHITE_PAINT = (0.95, 0.94, 0.92, 1.0)
    STAINLESS = (0.74, 0.75, 0.77, 1.0)
    ALUMINIUM = (0.82, 0.83, 0.85, 1.0)
    PANEL_BLUE = (0.10, 0.25, 0.65, 1.0)
    SWITCH_GREEN = (0.20, 0.75, 0.30, 1.0)
    KNOB_BLACK = (0.08, 0.08, 0.08, 1.0)
    DIAL_PINK = (0.92, 0.25, 0.55, 1.0)
    HANDLE_RED = (0.85, 0.10, 0.10, 1.0)
    HEAD_GREY = (0.30, 0.31, 0.33, 1.0)
    PINE = (0.90, 0.80, 0.60, 1.0)
    SUGAR_PINK = (1.00, 0.70, 0.85, 1.0)
    EXTINGUISHER_RED = (0.80, 0.05, 0.05, 1.0)
    PAVING = (0.55, 0.55, 0.53, 1.0)
    BUBBLE = (0.90, 0.95, 1.00, 0.25)
    BOARD_BLACK = (0.12, 0.12, 0.12, 1.0)

    @property
    def color(self) -> Color:
        """
        :return: The finish as a semantic digital twin colour.
        """
        r, g, b, a = self.value
        return Color(r, g, b, a)


# %% robot stations


class RobotStation(Enum):
    """
    Where the robot's base stands to work, from the twin layout's ``ROBOT_STATIONS`` (x, y, yaw in the booth frame).
    """

    MACHINE = "machine"
    MACHINE_CLOSE = "machine_close"
    SERVING = "serving"

    def pose(self, reference_frame: Body) -> Pose:
        """
        :param reference_frame: The booth frame body.
        :return: The base pose of this station.
        """
        x, y, yaw = TwinModule.LAYOUT.load().ROBOT_STATIONS[self.value]
        return Pose.from_xyz_rpy(x=x, y=y, yaw=yaw, reference_frame=reference_frame)


# %% building blocks


def box_body(name: str, size: Tuple[float, float, float], finish: Finish) -> Body:
    """
    :param name: Name of the body (prefix "booth").
    :param size: Edge lengths along x, y, z in metres; the box is centred on the body origin.
    :param finish: Surface colour.
    :return: A body with one box as visual and collision geometry.
    """
    shape = Box(origin=HomogeneousTransformationMatrix(), scale=Scale(*size), color=finish.color)
    return Body(name=PrefixedName(name, "booth"), visual=ShapeCollection([shape]), collision=ShapeCollection([shape]))


def cylinder_body(name: str, diameter: float, height: float, finish: Finish) -> Body:
    """
    :param name: Name of the body (prefix "booth").
    :param diameter: Cylinder diameter in metres.
    :param height: Cylinder height along z in metres; the cylinder is centred on the body origin.
    :param finish: Surface colour.
    :return: A body with one cylinder as visual and collision geometry.
    """
    shape = Cylinder(origin=HomogeneousTransformationMatrix(), width=diameter, height=height, color=finish.color)
    return Body(name=PrefixedName(name, "booth"), visual=ShapeCollection([shape]), collision=ShapeCollection([shape]))


def ring_body(
    name: str, diameter: float, height: float, wall: float, finish: Finish, segments: int = 24,
    opening_deg: float = 0.0, bottom: bool = True,
) -> Body:
    """
    An open ring (pan wall) approximated by boxes, so the inside stays free for the spinner head and the stick.

    :param name: Name of the body (prefix "booth").
    :param diameter: Outer diameter in metres.
    :param height: Wall height in metres; the ring is centred on the body origin.
    :param wall: Wall thickness in metres.
    :param finish: Surface colour.
    :param segments: Number of boxes around the ring.
    :return: A body with the ring wall and a bottom disc as geometry.
    """
    radius = diameter / 2 - wall / 2
    chord = 2 * radius * math.tan(math.pi / segments) + wall
    shapes = [
        Box(
            origin=HomogeneousTransformationMatrix.from_xyz_rpy(
                x=radius * math.cos(angle), y=radius * math.sin(angle), yaw=angle
            ),
            scale=Scale(wall, chord, height),
            color=finish.color,
        )
        for angle in (2 * math.pi * i / segments for i in range(segments))
        if abs(math.degrees(math.atan2(math.sin(angle - math.pi / 2), math.cos(angle - math.pi / 2)))) > opening_deg / 2
    ]
    if bottom:
        shapes.append(
        Cylinder(
            origin=HomogeneousTransformationMatrix.from_xyz_rpy(z=-height / 2 + wall / 2),
            width=diameter,
            height=wall,
            color=finish.color,
        )
        )
    return Body(name=PrefixedName(name, "booth"), visual=ShapeCollection(shapes), collision=ShapeCollection(shapes))


def open_box_body(name: str, size: Tuple[float, float, float], wall: float, finish: Finish) -> Body:
    """
    An open-topped container (tray, tub) as four walls and a bottom, so tools can dip into it.

    :param name: Name of the body (prefix "booth").
    :param size: Outer edge lengths along x, y, z in metres; centred on the body origin.
    :param wall: Wall and bottom thickness in metres.
    :param finish: Surface colour.
    """
    sx, sy, sz = size
    parts = [
        ((0.0, 0.0, -sz / 2 + wall / 2), (sx, sy, wall)),
        ((-sx / 2 + wall / 2, 0.0, 0.0), (wall, sy, sz)),
        ((sx / 2 - wall / 2, 0.0, 0.0), (wall, sy, sz)),
        ((0.0, -sy / 2 + wall / 2, 0.0), (sx, wall, sz)),
        ((0.0, sy / 2 - wall / 2, 0.0), (sx, wall, sz)),
    ]
    shapes = [
        Box(origin=HomogeneousTransformationMatrix.from_xyz_rpy(*xyz), scale=Scale(*dims), color=finish.color)
        for xyz, dims in parts
    ]
    return Body(name=PrefixedName(name, "booth"), visual=ShapeCollection(shapes), collision=ShapeCollection(shapes))


@dataclass
class BoothWorldBuilder:
    """
    Builds the booth, the machine, the tools and a robot into one world from the twin's layout model.
    """

    robot_type: Type[AbstractRobot] = PR2
    """
    The robot that operates the booth.
    """

    station: RobotStation = RobotStation.MACHINE
    """
    The station the robot's base stands at when the world is built.
    """

    machine_set_up: bool = True
    """
    Whether the booth has been set up: the Lock-N-Go transport handles stand UNLOCKED. They sit under the pan's
    overhang where a PR2 gripper cannot reach (kinematic test, 2026-10-20), and the manual uses them "for transport
    ONLY", so unlocking is a set-up task for the staff.
    """

    params: object = field(init=False)
    """
    The twin's parameter register module.
    """

    layout: object = field(init=False)
    """
    The twin's layout module.
    """

    world: World = field(init=False)
    """
    The world being built.
    """

    root: Body = field(init=False)
    """
    The booth frame body (map).
    """

    bodies: Dict[str, Body] = field(init=False, default_factory=dict)
    """
    The bodies built so far, by name.
    """

    def __post_init__(self):
        self.params = TwinModule.PARAMS.load()
        self.layout = TwinModule.LAYOUT.load()

    # %% public entry point

    def build(self) -> World:
        """
        :return: A world with the robot, the booth, the machine and the tools, all semantically annotated.
        """
        self.world = self._robot_world()
        with self.world.modify_world():
            self._booth_shell()
            self._furniture()
            machine = self._machine()
            tools = self._tools()
            booth = self._booth_annotations(machine)
            self._customer()
        return self.world

    # %% robot

    def _robot_world(self) -> World:
        """
        :return: A world rooted at the booth frame with the robot parked at :attr:`station`.
        """
        world = URDFParser.from_file(
            file_path=self.robot_type.get_ros_file_path(),
            use_visual_as_collision_backup=self.robot_type.uses_visual_as_collision_backup,
        ).parse()
        self.robot_type.from_world(world)
        with world.modify_world():
            old_root = world.root
            self.root = Body(name=PrefixedName("map"))
            odom = Body(name=PrefixedName("odom_combined"))
            map_C_odom = Connection6DoF.create_with_dofs(world, self.root, odom)
            world.add_connection(map_C_odom)
            drive = self.robot_type.get_drive_connection_type().create_with_dofs(
                parent=odom, child=old_root, world=world
            )
            world.add_connection(drive)
            drive.has_hardware_interface = True
        # the robot stands on the booth floor, which is raised above the paving
        map_C_odom.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            z=self.layout.FLOOR_Z, reference_frame=self.root
        )
        robot = world.get_semantic_annotations_by_type(self.robot_type)[0]
        # tight-workplace tuning of the base's collision buffer (twin register robot_buffer_base_booth)
        with world.modify_world():
            world.collision_manager.add_default_rule(
                AvoidExternalCollisions(
                    buffer_zone_distance=self.params.get("robot_buffer_base_booth"),
                    violated_distance=self.params.get("robot_violated_base_booth"),
                    robot=robot,
                    body_subset={world.get_body_in_branch_by_name(robot.root, "base_link")},
                )
            )
        for arm in robot.all_arms:
            park = arm.get_joint_state_by_type(StaticJointState.PARK)
            for connection, value in zip(park.connections, park.target_values):
                connection.position = value
        x, y, yaw = self.layout.ROBOT_STATIONS[self.station.value]
        drive.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=x, y=y, yaw=yaw, reference_frame=self.root)
        return world

    # %% helpers

    def _add(self, body: Body, xyz: Tuple[float, float, float], parent: Body | None = None, yaw: float = 0.0) -> Body:
        """
        Attach ``body`` rigidly at ``xyz`` (in the parent frame, the booth frame by default).
        """
        parent = parent or self.root
        self.world.add_kinematic_structure_entity(body)
        self.world.add_connection(
            FixedConnection(
                parent=parent,
                child=body,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    *xyz, yaw=yaw, reference_frame=parent
                ),
            )
        )
        self.bodies[body.name.name] = body
        return body

    def _free(self, body: Body, xyz: Tuple[float, float, float]) -> Body:
        """
        Place ``body`` loose (6 DoF) at ``xyz`` in the booth frame, so the robot can pick it up.
        """
        self.world.add_kinematic_structure_entity(body)
        connection = Connection6DoF.create_with_dofs(self.world, self.root, body)
        self.world.add_connection(connection)
        connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(*xyz, reference_frame=self.root)
        self.bodies[body.name.name] = body
        return body

    def _hinge(
        self,
        body: Body,
        parent: Body,
        xyz: Tuple[float, float, float],
        axis: Vector3,
        lower: float,
        upper: float,
        rpy: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> RevoluteConnection:
        """
        Attach ``body`` to ``parent`` with a revolute connection at ``xyz`` (parent frame).
        """
        self.world.add_kinematic_structure_entity(body)
        roll, pitch, yaw = rpy
        connection = RevoluteConnection.create_with_dofs(
            world=self.world,
            parent=parent,
            child=body,
            axis=axis,
            parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                *xyz, roll=roll, pitch=pitch, yaw=yaw, reference_frame=parent
            ),
            dof_limits=DegreeOfFreedomLimits.from_position_range_and_speed(lower, upper, 2.0),
        )
        self.world.add_connection(connection)
        self.bodies[body.name.name] = body
        return connection

    def _layout_box(self, item: dict, finish: Finish) -> Body:
        """
        Build one axis-aligned item of the twin layout as a box body.
        """
        lo, hi = item["lo"], item["hi"]
        size = tuple(h - l for l, h in zip(lo, hi))
        centre = tuple((l + h) / 2 for l, h in zip(lo, hi))
        return self._add(box_body(item["name"], size, finish), centre)

    # %% booth shell and furniture

    def _booth_shell(self) -> None:
        g, L = self.params.get, self.layout
        width, depth = g("booth_width"), g("booth_depth")
        # ground surfaces are visual only: the robot stands on them kinematically, and a collision shape at
        # contact distance 0 makes giskard's collision monitor flicker around its violation threshold
        for name, size, finish, xyz in (
            ("Paving", (6.0, 6.0, 0.02), Finish.PAVING, (0.0, -1.0, -0.01)),
            ("BoothFloor", (width, depth, L.FLOOR_Z), Finish.SPRUCE, (0.0, 0.0, L.FLOOR_Z / 2)),
        ):
            ground = box_body(name, size, finish)
            ground.collision = ShapeCollection([])
            self._add(ground, xyz)
        items = {item["name"]: item for item in L.items()}
        for name in ("WallLeft", "WallRight", "WallBack", "WallFrontBelowCounter", "WallFrontHeader"):
            finish = Finish.PINK_PAINT if name.startswith("WallFront") else Finish.WHITE_PAINT
            self._layout_box(items[name], finish)
        rise = L.RIDGE_Z - L.EAVE_Z
        half = depth / 2 + g("booth_roof_overhang")
        pitch = math.atan2(rise, depth / 2)
        slab = math.hypot(half, rise)
        for side, sign in (("Front", -1), ("Back", 1)):
            roof = box_body(f"Roof{side}", (width + 2 * g("booth_roof_overhang"), slab, 0.03), Finish.PINK_PAINT)
            self.world.add_kinematic_structure_entity(roof)
            self.world.add_connection(
                FixedConnection(
                    parent=self.root,
                    child=roof,
                    parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                        x=0.0,
                        y=sign * slab / 2 * math.cos(pitch),
                        z=L.EAVE_Z + rise - slab / 2 * math.sin(pitch),
                        roll=-sign * pitch,  # rises towards the ridge
                        reference_frame=self.root,
                    ),
                )
            )
        flap_x0, flap_x1 = L.FLAP_X
        flap = box_body("SalesFlap", (flap_x1 - flap_x0, 0.02, g("booth_flap_height")), Finish.PINK_PAINT)
        flap_connection = self._hinge(
            flap,
            self.root,
            (0.0, -depth / 2 - 0.02, L.FLAP_Z[1]),
            Vector3.X(),
            0.0,
            math.radians(g("booth_flap_open_angle")),
        )
        # the flap body's origin is the hinge; shift its geometry to hang below it
        for shape in flap.visual.shapes + flap.collision.shapes:
            shape.origin = HomogeneousTransformationMatrix.from_xyz_rpy(z=-g("booth_flap_height") / 2)
        flap_handle = box_body("SalesFlapHandle", (0.30, 0.03, 0.03), Finish.STAINLESS)
        self._add(flap_handle, (0.0, -0.03, -g("booth_flap_height") + 0.08), parent=flap)
        self.flap_connection = flap_connection

    def _furniture(self) -> None:
        L = self.layout
        items = {item["name"]: item for item in L.items()}
        finishes = {
            "MachineTable": Finish.STAINLESS,
            "CounterSteel": Finish.STAINLESS,
            "SalesCounter": Finish.SPRUCE,
            "SideShelf": Finish.SPRUCE,
            "HandwashStation": Finish.WHITE_PAINT,
            "FireExtinguisher": Finish.EXTINGUISHER_RED,
            "PowerDistributor": Finish.WHITE_PAINT,
            "SugarTubs": Finish.SUGAR_PINK,
            "CashBox": Finish.KNOB_BLACK,
            "InfoBoard": Finish.BOARD_BLACK,
            "BagRail": Finish.SUGAR_PINK,
        }
        for name, finish in finishes.items():
            self._layout_box(items[name], finish)

    # %% machine

    def _machine(self) -> CottonCandyMachine:
        g, L = self.params.get, self.layout
        mx, my = L.MACHINE_XY
        cabinet_w, cabinet_d, cabinet_h = g("m_cabinet_width"), g("m_cabinet_depth"), g("m_cabinet_height")
        feet = g("m_feet_height")
        cabinet = self._add(
            box_body("FlossMachineCabinet", (cabinet_w, cabinet_d, cabinet_h), Finish.STAINLESS),
            (mx, my, L.TABLE_Z + feet + cabinet_h / 2),
        )
        # the controls face the operator (+y)
        panel = box_body("ControlPanel", (cabinet_w * 0.9, 0.004, cabinet_h * 0.8), Finish.PANEL_BLUE)
        self._add(panel, (0.0, cabinet_d / 2 + 0.002, 0.0), parent=cabinet)
        switches = []
        for i, name in enumerate(("MotorMasterSwitch", "HeatSwitch")):
            rocker = box_body(name, (0.03, 0.02, 0.045), Finish.SWITCH_GREEN)
            self._hinge(
                rocker,
                cabinet,
                (-cabinet_w * 0.36, cabinet_d / 2 + 0.014, cabinet_h * (0.22 - 0.30 * i)),
                Vector3.X(),
                0.0,
                0.52,
            )
            switches.append(RockerSwitch(root=rocker))
        dial = cylinder_body("HeatDial", 0.11, 0.004, Finish.DIAL_PINK)
        self._add(dial, (cabinet_w * 0.05, cabinet_d / 2 + 0.006, 0.0), parent=cabinet)
        for shape in dial.visual.shapes + dial.collision.shapes:
            shape.origin = HomogeneousTransformationMatrix.from_xyz_rpy(roll=math.pi / 2)
        knob = cylinder_body("HeatControlKnob", 0.055, 0.03, Finish.KNOB_BLACK)
        self._hinge(
            knob,
            cabinet,
            (cabinet_w * 0.05, cabinet_d / 2 + 0.023, 0.0),
            Vector3.Z(),
            0.0,
            math.radians(g("m_heat_knob_range")),
            rpy=(-math.pi / 2, 0.0, 0.0),
        )
        handles = []
        for side, sign in (("Left", -1), ("Right", 1)):
            lever = box_body(f"LockNGoHandle{side}", (0.02, 0.025, 0.16), Finish.HANDLE_RED)
            self._hinge(
                lever,
                cabinet,
                (sign * (cabinet_w / 2 + 0.015), 0.04, 0.0),
                Vector3.X(),
                0.0,
                math.radians(g("m_lockngo_angle")),
            )
            handles.append(LockHandle(root=lever))
        bell = cylinder_body("BellHousing", g("m_bell_diameter"), g("m_bell_height"), Finish.ALUMINIUM)
        self._add(bell, (0.0, 0.0, cabinet_h / 2 + g("m_bell_height") / 2), parent=cabinet)
        pan_height = g("pan_height")
        pan = ring_body("FlossPan", g("pan_outer_diameter"), pan_height, g("pan_wall_t") * 3, Finish.ALUMINIUM)
        self._add(pan, (mx, my, L.M_TOP_Z - pan_height / 2))
        head = cylinder_body("SpinnerHead", g("head_band_diameter"), g("head_band_height") + g("head_cap_height"),
                             Finish.HEAD_GREY)
        self._hinge(
            head,
            bell,
            (0.0, 0.0, g("m_bell_height") / 2 + (g("head_band_height") + g("head_cap_height")) / 2),
            Vector3.Z(),
            -1.0e6,
            1.0e6,
        )
        bubble = ring_body("FlossBubble", g("bubble_base_diameter"), g("bubble_height"), 0.003, Finish.BUBBLE, 16,
                           opening_deg=g("bubble_opening_angle"), bottom=False)
        self._add(bubble, (mx, my, L.M_TOP_Z + g("bubble_height") / 2 + 0.002))
        machine = CottonCandyMachine(
            root=cabinet,
            motor_switch=switches[0],
            heat_switch=switches[1],
            heat_control=ControlKnob(root=knob),
            spinner_head=SpinnerHead(root=head),
            floss_pan=FlossPan(root=pan),
            lock_handles=handles,
        )
        self.world.add_semantic_annotation_recursively(machine)
        if self.machine_set_up:
            for handle in handles:
                handle.movable_joint.position = handle.movable_joint.dof.limits.upper.position
        return machine

    # %% tools and consumables

    def _tools(self) -> Dict[str, object]:
        g, L = self.params.get, self.layout
        items = {item["name"]: item for item in L.items()}
        carton_item = items["SugarCarton"]
        lo, hi = carton_item["lo"], carton_item["hi"]
        carton_size = tuple(h - l for l, h in zip(lo, hi))
        carton = self._free(
            box_body("SugarCarton", carton_size, Finish.WHITE_PAINT), tuple((l + h) / 2 for l, h in zip(lo, hi))
        )
        spout = Body(name=PrefixedName("SugarCarton_end_effector", "booth"))
        self.world.add_kinematic_structure_entity(spout)
        self.world.add_connection(
            FixedConnection(
                parent=carton,
                child=spout,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    z=carton_size[2] / 2, reference_frame=carton
                ),
            )
        )
        quiver_item = items["StickHolder"]
        quiver = self._layout_box(quiver_item, Finish.SPRUCE)
        sticks = []
        for i in range(3):
            stick = box_body(f"CandyStick{i}", (g("stick_length"), g("stick_section"), g("stick_section")), Finish.PINE)
            # a stick stands upright in the quiver; its x axis (towards the floss tip) points down
            stick_connection_xyz = (0.02 * (i - 1), 0.0, quiver_item["hi"][2] - quiver_item["lo"][2] - g("stick_length") / 2 + 0.06)
            self.world.add_kinematic_structure_entity(stick)
            self.world.add_connection(
                Connection6DoF.create_with_dofs(
                    self.world, quiver, stick,
                )
            )
            stick.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
                *stick_connection_xyz, pitch=math.pi / 2, reference_frame=quiver
            )
            tip = Body(name=PrefixedName(f"{stick.name.name}_end_effector", "booth"))
            self.world.add_kinematic_structure_entity(tip)
            self.world.add_connection(
                FixedConnection(
                    parent=stick,
                    child=tip,
                    parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                        x=g("stick_length") / 2 - 0.03, reference_frame=stick
                    ),
                )
            )
            sticks.append(CandyStick(root=stick))
        sponge_item = items["Sponge"]
        lo, hi = sponge_item["lo"], sponge_item["hi"]
        sponge = self._free(
            box_body("Sponge", tuple(h - l for l, h in zip(lo, hi)), Finish.SUGAR_PINK),
            tuple((l + h) / 2 for l, h in zip(lo, hi)),
        )
        annotations = dict(
            carton=SugarCarton(root=carton),
            quiver=StickQuiver(root=quiver),
            sticks=sticks,
            sponge=Sponge(root=sponge),
        )
        for annotation in [annotations["carton"], annotations["quiver"], annotations["sponge"],
                           *sticks]:
            self.world.add_semantic_annotation_recursively(annotation)
        return annotations

    # %% booth-level annotations

    def _booth_annotations(self, machine: CottonCandyMachine) -> CottonCandyBooth:
        L = self.layout
        flap_body = self.bodies["SalesFlap"]
        flap = SalesFlap(root=flap_body, handle=Handle(root=self.bodies["SalesFlapHandle"]))
        floor = self.bodies["BoothFloor"]
        booth = CottonCandyBooth(root=floor, machine=machine, sales_flap=flap)
        handover = box_body("HandoverZone", (0.25, 0.20, 0.25), Finish.BUBBLE)
        handover.collision = ShapeCollection([])     # a region, not an obstacle
        self._add(handover, L.HANDOVER_XYZ)
        for annotation in (
            booth,
            HandoverZone(root=handover),
            HandwashStation(root=self.bodies["HandwashStation"]),
            FireExtinguisher(root=self.bodies["FireExtinguisher"]),
            InformationBoard(root=self.bodies["InfoBoard"]),
        ):
            self.world.add_semantic_annotation_recursively(annotation)
        return booth

    def _customer(self) -> None:
        """
        A customer standing in front of the flap, as a simple body (ILLUSTRATIVE: child height 1.25 m).
        """
        customer = cylinder_body("Customer", 0.35, 1.25, Finish.PANEL_BLUE)
        self._add(customer, (self.layout.HANDOVER_XYZ[0], -self.params.get("booth_depth") / 2 - 0.45, 0.625))
        self.world.add_semantic_annotation_recursively(Human(root=customer))
