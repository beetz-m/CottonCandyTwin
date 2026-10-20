"""
The process model of the floss machine: which phase it is in, how much sugar the spinner head holds and how much
floss has collected in the pan, given the switch and knob positions of the world and the time that has passed.

The kinematic world knows where the switches stand but not what the machine does. This model supplies the
behaviour the manual describes (twin register, source ``GM_MAN_EXP``): the motor runs while "Motor & Master" is on,
the band heats while "Heat" is on as well, floss comes out after the warm-up, sugar may only be poured into a
stopped head, and the burn-out at the end of the day empties the head. In the Isaac Sim twin the same quantities come
from the machine controller instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from krrood.exceptions import DataclassException

from cotton_candy.semantic_annotations import CottonCandyMachine


# %% phases


class FlossMachinePhase(Enum):
    """
    The phases of the floss machine.
    """

    OFF = "off"
    """
    Motor and heat off, the spinner head stands still.
    """

    SPINNING = "spinning"
    """
    The motor runs, the heating ribbon is off.
    """

    WARMING_UP = "warming_up"
    """
    Motor and heat on, the band has not yet reached the melting temperature of the sugar.
    """

    PRODUCING = "producing"
    """
    Motor and heat on, sugar in the head: floss is spun into the pan.
    """

    RUNNING_EMPTY = "running_empty"
    """
    Motor and heat on, the head is empty: excess sugar is burnt out.
    """


# %% failures


@dataclass
class SugarPouredIntoSpinningHead(DataclassException):
    """
    Raised when sugar is poured into the spinner head while the motor runs ("NEVER add sugar when motor is running").
    """

    phase: FlossMachinePhase
    """
    The phase the machine was in.
    """

    def error_message(self) -> str:
        return f"Sugar may only be poured into a stopped spinner head, the machine is {self.phase.value}"

    def suggest_correction(self) -> str:
        return "Stop the machine first: Heat OFF, let the motor run a few seconds, Motor & Master OFF."


@dataclass
class NotEnoughFloss(DataclassException):
    """
    Raised when a portion is taken from the pan before enough floss has collected.
    """

    available_kg: float
    """
    The floss mass in the pan.
    """

    required_kg: float
    """
    The floss mass of one portion.
    """

    def error_message(self) -> str:
        return f"Only {self.available_kg * 1000:.1f} g of floss in the pan, a portion needs {self.required_kg * 1000:.1f} g"

    def suggest_correction(self) -> str:
        return "Let the machine produce longer, or refill the spinner head if it ran empty."


@dataclass
class PhaseNotReached(DataclassException):
    """
    Raised when the machine does not reach a phase within the time allowed for it.
    """

    expected: FlossMachinePhase
    """
    The phase that was waited for.
    """

    actual: FlossMachinePhase
    """
    The phase the machine ended up in.
    """

    def error_message(self) -> str:
        return f"Waited for {self.expected.value}, the machine is {self.actual.value}"

    def suggest_correction(self) -> str:
        return "Check the switches, the heat setting and the sugar in the head."


# %% the model


@dataclass
class FlossMachineTimings:
    """
    The durations, rates and amounts of the machine's process (defaults from the twin register, keys in brackets).
    """

    master_to_heat_delay_s: float = 10.0
    """
    Wait after "Motor & Master" before "Heat" is switched on (op_master_to_heat_delay, SOURCED).
    """

    warm_up_s: float = 25.0
    """
    Time from "Heat" on at maximum setting until floss appears (op_warmup, SOURCED: 20-30 s).
    """

    output_rate_portions_per_min: float = 2.5
    """
    Rated output (op_output_rate, SOURCED: 2-3 servings per minute).
    """

    portion_sugar_kg: float = 0.020
    """
    Sugar per portion (portion_sugar, SOURCED: 1 kg ~ 50 portions).
    """

    head_capacity_kg: float = 0.025
    """
    Sugar the head holds when full (head_sugar_capacity, ILLUSTRATIVE).
    """

    fill_fraction: float = 0.90
    """
    Fill level for a balanced head (head_fill_fraction, SOURCED).
    """

    burn_out_s: float = 210.0
    """
    Burn-out at maximum heat with the head empty (op_burnout_clean_min, SOURCED: 3-4 min).
    """

    cool_down_s: float = 90.0
    """
    Motor run after "Heat" off at shutdown (SOURCED: 1-2 min).
    """

    @classmethod
    def from_twin_register(cls, params) -> FlossMachineTimings:
        """
        :param params: The twin's parameter register module (``site/params.py``).
        :return: Timings read from the register, so the CRAM model and the Isaac Sim twin share their numbers.
        """
        g = params.get
        return cls(
            master_to_heat_delay_s=g("op_master_to_heat_delay"),
            warm_up_s=g("op_warmup"),
            output_rate_portions_per_min=g("op_output_rate"),
            portion_sugar_kg=g("portion_sugar"),
            head_capacity_kg=g("head_sugar_capacity"),
            fill_fraction=g("head_fill_fraction"),
            burn_out_s=g("op_burnout_clean_min") * 60.0,
        )


@dataclass
class FlossMachineProcess:
    """
    The state of one floss machine's process over time.
    """

    machine: CottonCandyMachine
    """
    The machine whose switches and knob drive the process.
    """

    timings: FlossMachineTimings = field(default_factory=FlossMachineTimings)
    """
    Durations, rates and amounts of the process.
    """

    time_s: float = 0.0
    """
    Process time since the model was created.
    """

    sugar_in_head_kg: float = 0.0
    """
    Sugar in the spinner head.
    """

    floss_in_pan_kg: float = 0.0
    """
    Floss collected on the stabilizer in the pan.
    """

    heat_on_since_s: float | None = None
    """
    When "Heat" was last switched on, or None while it is off.
    """

    burnt_out_s: float = 0.0
    """
    How long the empty head has been run at maximum heat.
    """

    portions_served: int = 0
    """
    Portions taken from the pan so far.
    """

    # %% phase

    @property
    def phase(self) -> FlossMachinePhase:
        """
        :return: The phase given the switch positions, the warm-up and the sugar in the head.
        """
        if not self.machine.motor_switch.is_on:
            return FlossMachinePhase.OFF
        if not self.machine.heat_switch.is_on:
            return FlossMachinePhase.SPINNING
        if self.heat_on_since_s is None or self.time_s - self.heat_on_since_s < self.timings.warm_up_s:
            return FlossMachinePhase.WARMING_UP
        if self.sugar_in_head_kg > 1e-6:
            return FlossMachinePhase.PRODUCING
        return FlossMachinePhase.RUNNING_EMPTY

    @property
    def head_fill_level(self) -> float:
        """
        :return: Sugar in the head as a fraction of its capacity.
        """
        return self.sugar_in_head_kg / self.timings.head_capacity_kg

    @property
    def portion_ready(self) -> bool:
        """
        :return: Whether one portion of floss has collected in the pan.
        """
        return self.floss_in_pan_kg + 1e-9 >= self.timings.portion_sugar_kg

    # %% events

    def notice_switches(self) -> None:
        """
        Register a change of the heat switch (call after an action moved a switch).
        """
        heat = self.machine.motor_switch.is_on and self.machine.heat_switch.is_on
        if heat and self.heat_on_since_s is None:
            self.heat_on_since_s = self.time_s
        if not heat:
            self.heat_on_since_s = None

    def advance(self, seconds: float) -> None:
        """
        Let ``seconds`` of process time pass: sugar turns into floss at the rated output while producing; an empty
        head at full heat burns out.
        """
        self.notice_switches()
        step = 0.5
        remaining = seconds
        while remaining > 1e-9:
            dt = min(step, remaining)
            self.time_s += dt
            remaining -= dt
            phase = self.phase
            if phase is FlossMachinePhase.PRODUCING:
                spun = min(
                    self.sugar_in_head_kg,
                    self.timings.output_rate_portions_per_min * self.timings.portion_sugar_kg * dt / 60.0,
                )
                self.sugar_in_head_kg -= spun
                self.floss_in_pan_kg += spun
            elif phase is FlossMachinePhase.RUNNING_EMPTY and self.machine.heat_control.travel_fraction > 0.95:
                self.burnt_out_s += dt

    def advance_until(self, phase: FlossMachinePhase, timeout_s: float) -> float:
        """
        Let time pass until the machine is in ``phase``.

        :return: The time waited.
        :raises PhaseNotReached: When the phase is not reached within ``timeout_s``.
        """
        waited = 0.0
        while self.phase is not phase and waited < timeout_s:
            self.advance(0.5)
            waited += 0.5
        if self.phase is not phase:
            raise PhaseNotReached(phase, self.phase)
        return waited

    def advance_until_portion(self, timeout_s: float = 120.0) -> float:
        """
        Let time pass until one portion of floss has collected.

        :return: The time waited.
        """
        waited = 0.0
        while not self.portion_ready and waited < timeout_s and self.phase is FlossMachinePhase.PRODUCING:
            self.advance(0.5)
            waited += 0.5
        if not self.portion_ready:
            raise NotEnoughFloss(self.floss_in_pan_kg, self.timings.portion_sugar_kg)
        return waited

    def pour_sugar(self, kg: float) -> None:
        """
        Pour ``kg`` of sugar into the head (only while it stands still).

        :raises SugarPouredIntoSpinningHead: When the motor runs.
        """
        if self.phase is not FlossMachinePhase.OFF:
            raise SugarPouredIntoSpinningHead(self.phase)
        self.sugar_in_head_kg = min(self.timings.head_capacity_kg, self.sugar_in_head_kg + kg)

    def take_portion(self) -> None:
        """
        Wind one portion of floss from the pan onto a stick.

        :raises NotEnoughFloss: When less than a portion has collected.
        """
        if not self.portion_ready:
            raise NotEnoughFloss(self.floss_in_pan_kg, self.timings.portion_sugar_kg)
        self.floss_in_pan_kg -= self.timings.portion_sugar_kg
        self.portions_served += 1
