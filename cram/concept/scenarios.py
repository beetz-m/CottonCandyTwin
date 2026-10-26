"""Disturbance scenarios of the booth activity (ccram run --scenario NAME). Each gets the run: run.demo, run.adapter,
run.interp (hooks: run.interp.after[tag] = fn runs after the step tagged tag)."""


def _motor_on(run):
    sw = run.adapter.machine.motor_switch.movable_joint
    sw.position = sw.dof.limits.upper.position                # a co-worker switches the motor on
    run.adapter.process.notice_switches()
    run.interp.note("DISTURBANCE: motor switched on")


def scenario_motor_on(run):
    """The motor is switched on before the plan starts."""
    _motor_on(run)


def scenario_motor_on_after_take(run):
    """The motor is switched on right after the robot took the carton (the gate must refuse the pour)."""
    run.interp.after["take"] = lambda: _motor_on(run)


def scenario_two_orders_underfilled(run):
    """A nearly empty carton (one portion's sugar only) and a second customer after the first order."""
    from cotton_candy.recipes import Flavour
    run.adapter.amount_override.append(0.022)

    def second_order():
        run.adapter.process.new_order(Flavour.RASPBERRY.value, ordered_by="Customer")
        run.interp.note("a second customer orders")
    run.interp.after["order-1"] = second_order
