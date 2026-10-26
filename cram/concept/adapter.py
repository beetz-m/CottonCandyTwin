"""The cotton candy booth as a conceptual CRAM research activity: the adapter between ccram's generic kernel and the
CRAM booth world (coraplex, kinematic PR2, FlossMachineProcess).

  atoms()      the StateReader: ground atoms for the OBSERVABLE predicates (process model + world)
  resolve()    the booth's servants: order-record, layout-stations, recipe, free candy stick
  r_<schema>   realisations: schema phases -> the existing coraplex actions (parameters of cotton_candy/actions.py)
  predict()    emulation of monitoring-process on a copy of the floss machine model (D4 pre-act verdict)
"""
from __future__ import annotations

import copy
import math
import os

from ccram import goals as G
from ccram.adapter import Adapter
from ccram.kernel import KernelFailure

STATIONS = {"at-machine": "MACHINE", "machine-close": "MACHINE_CLOSE", "serving": "SERVING"}
TAG_OF_STATION = {v: k for k, v in STATIONS.items()}
ARM_SCHEMAS = ("transporting", "pressing-button", "turning", "gathering", "wrapping", "handing-over", "wiping")
DEFAULT_TAG = {"sugar-carton": "sugar-carton-raspberry", "cotton-candy-machine": "machine", "customer": "customer",
               "handover-location": "handover-zone", "sponge": "sponge", "candy-stick": "stick-1"}


class BoothAdapter(Adapter):
    MODEL_ONLY = {"dropped", "spilled", "contact", "clean"}       # not observable in the kinematic booth
    OBSERVABLE = {"mode", "gripper-free", "held-by", "at", "contains", "portion-spun", "on", "switch-state",
                  "travel-fraction", "on-tool", "stage", "holds", "burnt-out", "delivered"}
    EXCEPTION_KINDS = {"SugarPouredIntoSpinningHead": "sugar-poured-into-spinning-head",
                       "PhaseNotReached": "phase-not-reached"}

    def __init__(self, world, context, process):
        super().__init__(world, context)
        from cotton_candy.semantic_annotations import CandyStick, CottonCandyMachine, HandoverZone, Sponge, SugarCarton
        from semantic_digital_twin.semantic_annotations.semantic_annotations import Human
        self.process = process
        one = lambda c: world.get_semantic_annotations_by_type(c)[0]            # noqa: E731
        self.machine = one(CottonCandyMachine)
        self.types = {"cotton-candy-machine": CottonCandyMachine, "sugar-carton": SugarCarton, "candy-stick": CandyStick,
                      "sponge": Sponge, "customer": Human, "handover-location": HandoverZone}
        self.symbol_of = {id(self.machine): "machine", id(self.robot.right_arm): "right-arm",
                          id(self.robot.left_arm): "left-arm"}
        self.parent = {}                # the body an object hung from (re-attached when it is put back)
        self.grip = {}                  # grip point recorded at the take (pouring lifts from it)
        self.amount_override = []       # scenario: amounts the recipe servant yields first (a near-empty carton)
        self.tracked = [v for k, c in self.types.items() if k != "cotton-candy-machine"
                        for v in world.get_semantic_annotations_by_type(c)]

    # -- state
    def time(self):
        return self.process.time_s

    def advance(self, dt=None):
        """(wait-for (elapsed D)): D in seconds, or a named timing of the machine (master-to-heat-delay ->
        FlossMachineTimings.master_to_heat_delay_s)."""
        if isinstance(dt, str):
            dt = getattr(self.process.timings, dt.replace("-", "_") + "_s", 10.0)
        self.process.advance(10.0 if dt is None else float(dt))

    def atoms(self):
        from coraplex.querying.predicates import GripperIsFree
        from cotton_candy.booth_world import RobotStation
        p, tracked = self.process, self.tracked
        a = [["mode", "floss-machine", p.phase.value.replace("_", "-")]]
        if p.sugar_in_head_kg > 1e-6:                          # a quantity: (contains head (mass kg))
            a.append(["contains", "spinner-head", ["mass", round(p.sugar_in_head_kg, 4)]])
        if p.portion_ready:
            a.append(["portion-spun"])
        if p.burnt_out_s >= p.timings.burn_out_s - 1e-6:
            a.append(["burnt-out", "machine"])
        for sw in ("motor-switch", "heat-switch"):
            a.append(["switch-state", sw, "on" if getattr(self.machine, sw.replace("-", "_")).is_on else "off"])
        a.append(["travel-fraction", "heat-control", round(float(self.machine.heat_control.travel_fraction), 2)])
        for i, c in enumerate(p.candies):
            st, cs = c.stage.value, f"candy-{i + 1}"            # the order's symbol (climb: order-record)
            if st in ("gathered", "wrapped", "delivered"):
                stick = next((self.sym(o) for o in tracked if o.root.name.name == c.stick), c.stick or "candy-stick")
                a.append(["on-tool", "floss", stick])        # the process names the stick by its body, the plan by tag
            a.append(["stage", cs, st])
            if st == "delivered":
                a.append(["delivered", cs, "customer"])
        humans = self.world.get_semantic_annotations_by_type(self.types["customer"])
        for obj in tracked:
            par = obj.root.parent_kinematic_structure_entity
            for hu in humans:
                if par is hu.root:
                    a.append(["holds", self.sym(hu), self.sym(obj)])
                    a.append(["taken-by", self.sym(hu), self.sym(obj)])     # the hand-over's release condition
        for arm in (self.robot.right_arm, self.robot.left_arm):
            ee = arm.end_effector
            if GripperIsFree(ee)():
                a.append(["gripper-free", self.sym(arm)])
            branch = self.world.get_kinematic_structure_entities_of_branch(ee.tool_frame)
            for obj in tracked:
                if obj.root in branch:
                    a.append(["held-by", self.sym(obj), self.sym(arm)])
        base = self.robot.root.global_pose.to_np()
        for st in RobotStation:
            q = st.pose(self.world.root).to_np()
            if math.hypot(*(base[:2, 3] - q[:2, 3])) < 0.02:          # stations lie centimetres apart
                a.append(["at", ["the", "robot"], TAG_OF_STATION[st.name]])
        for obj in tracked:
            h = self.home.get(id(obj))
            if h is not None:
                d = obj.root.global_pose.to_np()[:3, 3] - h.to_np()[:3, 3]
                if float((d ** 2).sum()) ** 0.5 < 0.05 and not any(x[0] == "held-by" and x[1] == self.sym(obj) for x in a):
                    a.append(["on", self.sym(obj), "home-of-" + self.sym(obj)])
        return a

    # -- servants
    def resolve(self, x, env, role, climb):
        if not isinstance(x, list) or not x:
            return None
        p = self.process
        if x[0] in ("a", "an", "the") and x[1] == "cotton-candy":    # order-record: the candy belief of the order
            c = p.candy
            return c, f"candy-{p.candies.index(c) + 1}", dict(servant="order-record", status="recorded",
                                                              ordered_by=c.customer)
        if x[0] == "the" and x[1] == "station":                 # robot-station -> layout-stations
            from cotton_candy.booth_world import RobotStation
            tag = next(c[1] for c in x[2:] if isinstance(c, list) and c[0] == "tag")
            return RobotStation[STATIONS[tag]].pose(self.world.root), tag, dict(servant="layout-stations",
                                                                                 status="recorded")
        if x[0] == "some":                                      # amount -> recipe
            t = p.timings
            kg = max(0.0, t.head_capacity_kg * t.fill_fraction - p.sugar_in_head_kg)
            target = t.head_capacity_kg * t.fill_fraction       # what the head must contain afterwards
            if self.amount_override:
                kg = self.amount_override.pop(0)
                return kg, ["mass", round(p.sugar_in_head_kg + kg, 4)], dict(
                    servant="recipe", status="assumed", value_kg=round(kg, 4),
                    note="carton nearly empty: less than the recipe")
            return kg, ["mass", round(target, 4)], dict(servant="recipe", status="commonsense", value_kg=round(kg, 4))
        if x[0] in ("a", "an", "the") and x[1] in ("arm", "right-arm", "left-arm"):   # robot-model
            left = x[1] == "left-arm"
            arm = self.robot.left_arm if left else self.robot.right_arm
            return arm, "left-arm" if left else "right-arm", dict(servant="robot-model", status="recorded")
        if x[0] in ("a", "an", "the") and x[1] == "candy-stick":   # a free stick: not handed to a customer
            vs = self.world.get_semantic_annotations_by_type(self.types["candy-stick"])
            hum = [h.root for h in self.world.get_semantic_annotations_by_type(self.types["customer"])]
            free = [v for v in vs if v.root.parent_kinematic_structure_entity not in hum]
            k = vs.index(free[0]) if free else 0
            return vs[k], self.name(vs[k], f"stick-{k + 1}"), dict(servant="eql-annotations", status="recorded",
                                                                   candidates=len(free))
        return None

    def resolve_symbol(self, s):
        if s in STATIONS:                                       # (at (the robot) serving): a station by its tag
            from cotton_candy.booth_world import RobotStation
            return RobotStation[STATIONS[s]].pose(self.world.root)
        return super().resolve_symbol(s)

    def default_symbol(self, type_kw, v):
        return DEFAULT_TAG.get(type_kw, self.sym(v))

    def _right_arm(self):
        return self.robot.right_arm, "right-arm", dict(servant="robot-model", status="recorded")

    def default_param(self, pname, ptype):
        return self._right_arm() if ptype == "arm" else None

    def default_roles(self, schema, R):
        return {"arm": self._right_arm()} if schema in ARM_SCHEMAS and "arm" not in R else {}

    def belongs_elsewhere(self, obj, atoms):
        s = self.sym(obj)
        if any(a[0] == "holds" and a[2] == s for a in atoms):
            return "with the customer -- belongs there now"
        return None

    def gate_failure(self, phi):
        return "sugar-poured-into-spinning-head" if phi[0] == "poured-into" else "closing-event-violation"

    # -- emulation (D4)
    def predict(self, t, R):
        """Emulate a process-driven step on a copy of the floss machine model: does it reach its condition, or does
        a microtheory signal come first? (the copy shares nothing that advance() mutates)"""
        if t != "monitoring-process" or "until" not in R:
            return None
        p = copy.copy(self.process)
        until, waited, prev = R["until"][1], 0.0, p.phase.value
        saved = self.process
        self.process = p                            # atoms() looks at the copy while emulating
        try:
            while waited < 900.0:
                if G.holds(until, self.interp.atoms()):
                    return dict(prediction=f"{G.show(until)} after {waited:.0f} s", predicted_failure=None)
                p.advance(0.5)
                waited += 0.5
                if p.phase.value == "running_empty" and prev != "running_empty":
                    return dict(prediction=f"head-running-empty after {waited:.0f} s",
                                predicted_failure="head-running-empty")
                prev = p.phase.value
            return dict(prediction="condition not reached within 900 s", predicted_failure="phase-not-reached")
        finally:
            self.process = saved

    # -- realisations (schema phases -> coraplex actions)
    @staticmethod
    def _half(obj):
        spout = obj.get_tool_frame().global_pose.to_np()
        root = obj.root.global_pose.to_np()
        return float(((spout[:3, 3] - root[:3, 3]) ** 2).sum()) ** 0.5

    def _step(self, fn):
        from cotton_candy.process_nodes import process_step
        return process_step(fn)

    def _arm(self, R):
        return R.get("arm", (self.robot.right_arm,))[0]

    def r_transporting(self, R):
        """grasp servant (grasp-candidates): approach and grasp offset per object class, as cotton_candy/actions.py."""
        from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
        from cotton_candy.actions import pose_above
        from cotton_candy.manipulation_categories import ApproachDirection, TransportingAction
        from semantic_digital_twin.datastructures.definitions import TorsoState
        obj, arm = R["object"][0], R["arm"][0]
        kind = type(obj).__name__
        if os.environ.get("KERNEL_DEBUG"):
            from coraplex.querying.predicates import GripperIsFree
            print("      [debug] take", kind, "base", self.robot.root.global_pose.to_np()[:3, 3].round(3),
                  "free R/L", GripperIsFree(self.robot.right_arm.end_effector)(),
                  GripperIsFree(self.robot.left_arm.end_effector)(), "obj", obj.root.global_pose.to_np()[:3, 3].round(3),
                  "obj parent", obj.root.parent_kinematic_structure_entity.name.name, flush=True)
        if id(obj) not in self.home:                   # class home (D7): the full pose it was taken from (orientation
            from scipy.spatial.transform import Rotation   # matters: a stick goes back upright into the quiver) and
            from semantic_digital_twin.spatial_types.spatial_types import Pose   # the body it hung from
            m = obj.root.global_pose.to_np()
            qx, qy, qz, qw = Rotation.from_matrix(m[:3, :3]).as_quat()
            self.home[id(obj)] = Pose.from_xyz_quaternion(pos_x=float(m[0, 3]), pos_y=float(m[1, 3]),
                                                          pos_z=float(m[2, 3]), quat_x=qx, quat_y=qy, quat_z=qz,
                                                          quat_w=qw, reference_frame=self.world.root)
            self.parent[id(obj)] = obj.root.parent_kinematic_structure_entity
        if kind == "SugarCarton":
            half = self._half(obj)
            self.grip[id(obj)] = pose_above(obj.root.global_pose, -half + 0.03, self.world.root)
            return [MoveTorsoAction(TorsoState.HIGH),
                    TransportingAction(obj, arm, ApproachDirection.TOWARDS_SALES_FRONT,
                                       grasp_offset=(0.0, 0.0, -half + 0.03))]
        if kind == "CandyStick":
            return [MoveTorsoAction(TorsoState.LOW), TransportingAction(obj, arm, ApproachDirection.TOWARDS_LEFT_WALL)]
        return [TransportingAction(obj, arm, ApproachDirection.TOWARDS_SALES_FRONT)]

    def r_pressing_button(self, R):
        from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction, ParkArmsAction
        from cotton_candy.manipulation_categories import PressingButtonAction
        from semantic_digital_twin.datastructures.definitions import TorsoState
        on = str(R["state"][1]) == "on"
        return [MoveTorsoAction(TorsoState.LOW), PressingButtonAction(R["object"][0], self._arm(R), 1.0 if on else 0.0),
                self._step(self.process.notice_switches), ParkArmsAction(self.robot.all_arms)]   # as Start/Stop end

    def r_turning(self, R):
        from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
        from cotton_candy.manipulation_categories import TurningAction
        return [TurningAction(R["object"][0], self._arm(R), float(R["setting"][0])),
                ParkArmsAction(self.robot.all_arms)]

    def r_monitoring_process(self, R):
        """Waits on the process model until the condition holds (the machine's reported state on a real one)."""
        until = R["until"][1]
        limit = float(R["timeout"][0]) if "timeout" in R else 900.0

        def wait():
            p = self.process
            p.notice_switches()
            waited, prev = 0.0, p.phase.value
            while not G.holds(until, self.interp.atoms()) and waited < limit:
                p.advance(0.5)
                waited += 0.5
                ph = p.phase.value
                if ph == "running_empty" and prev != "running_empty":       # floss-machine microtheory: mode
                    self.interp.signal("head-running-empty",                  # running-empty :signals
                                       f"spinner head ran empty at t = {p.time_s:.0f} s")
                prev = ph
            if not G.holds(until, self.interp.atoms()):
                from cotton_candy.process import PhaseNotReached
                raise PhaseNotReached(p.phase, p.phase)
        return [self._step(wait)]

    def r_gathering(self, R):
        from cotton_candy.manipulation_categories import GatheringAction
        stick, pan = R["tool"][0], R["container"][0]
        return [GatheringAction(arm=self._arm(R), tool=stick, container=pan.root),
                self._step(lambda: self.process.take_portion(stick.root.name.name))]

    def r_wrapping(self, R):
        from cotton_candy.manipulation_categories import WrappingAction
        return [WrappingAction(arm=self._arm(R), tool=R["tool"][0], above=R["above"][0].root),
                self._step(self.process.candy_wrapped)]

    def r_handing_over(self, R):
        from coraplex.plans.attachment_nodes import ReAttachNode
        from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
        from cotton_candy.manipulation_categories import HandingOverAction
        from semantic_digital_twin.spatial_types.spatial_types import Pose
        stick, customer, zone = R["object"][0], R["recipient"][0], R["destination"][0]
        z = zone.root.global_pose.to_np()
        pose = Pose.from_xyz_rpy(x=float(z[0, 3]), y=float(z[1, 3]), z=float(z[2, 3]), pitch=-math.pi / 2,
                                 reference_frame=self.world.root)
        return [HandingOverAction(stick, self._arm(R), pose), ReAttachNode(body=stick.root, new_parent=customer.root),
                self._step(lambda: self.process.candy_delivered(customer.root.name.name)),
                ParkArmsAction(self.robot.all_arms)]

    def r_wiping(self, R):
        """The stainless strip beside the pan (the original CleanFlossMachineAction: never water in the head)."""
        from coraplex.datastructures.enums import WipingTechnique
        from cotton_candy.manipulation_categories import CategorisedWipingAction
        from semantic_digital_twin.spatial_types.spatial_types import Pose
        sponge = R["tool"][0]
        table = self.world.get_body_by_name("MachineTable")
        bbox = table.collision.as_bounding_box_collection_in_frame(self.world.root).bounding_box()
        sp = sponge.root.global_pose.to_np()
        target = Pose.from_xyz_rpy(x=float(sp[0, 3]), y=float(bbox.max_y) - 0.08, z=float(bbox.max_z),
                                   reference_frame=self.world.root)
        return [CategorisedWipingAction(arm=self._arm(R), tool=sponge, target_pose=target,
                                        technique=WipingTechnique.WIPE, length=0.15, cycles=2.0)]

    def r_navigating(self, R):
        from coraplex.robot_plans.actions.core.navigation import NavigateAction
        return [NavigateAction(R["destination"][0])]

    def r_pouring_into(self, R):
        from cotton_candy.manipulation_categories import PouringIntoAction
        obj, head = R["object"][0], R["destination"][0]
        tilt, grip_h = 1.2, 0.03
        half = self._half(obj)
        kg = R["amount"][0]

        def pour():
            self.events.append((self.process.time_s, ["poured-into", R["amount"][1], R["destination"][1]],
                                self.atoms()))
            self.process.pour_sugar(kg)
        return [PouringIntoAction(self.robot.right_arm, head.root, standoff=(2 * half - grip_h) * math.sin(tilt),
                                  pour_height=0.24, tilt_angle=tilt, lift_from=self.grip[id(obj)],
                                  may_touch=[self.machine.floss_pan.root, self.world.get_body_by_name("FlossBubble")]),
                self._step(pour)]

    def r_putting_down(self, R):
        from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
        from cotton_candy.manipulation_categories import PuttingDownAction
        arm = self.robot.right_arm
        obj = R["object"][0]
        par = self.parent.get(id(obj)) if R["destination"][1].startswith("home-of-") else None
        return [ParkArmsAction([arm]), PuttingDownAction(obj, R["destination"][0], new_parent=par),
                ParkArmsAction(self.robot.all_arms)]


def make_adapter(demo, world, context):
    """activity.toml [twin] adapter entry point."""
    return BoothAdapter(world, context, demo.process)
