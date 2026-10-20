"""
The plan control page's commands (cotton_candy.control), executed as the demo thread would, and its HTTP side.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from coraplex.execution_environment import kinematically_simulated_robot

from cotton_candy.control import Command, PlanControl, _handler_for
from test_universal_plan import fresh


def control():
    *_, plan = fresh()
    return PlanControl(plan)


def run(c: PlanControl, name: str, **arguments) -> dict:
    with kinematically_simulated_robot:
        c.execute(Command(name, arguments))
    c.publish_status()
    json.dumps(c.page_status())     # the page must be able to read it
    return c.log[-1]


def test_project_then_achieve_from_a_cold_machine():
    c = control()
    assert run(c, "project")["message"] == ("projection: MACHINE-READY -> STICK-IN-HAND -> CANDY-FORMED -> "
                                            "CANDY-WRAPPED -> HANDED-OVER")
    entry = run(c, "achieve")
    assert entry["ok"] and entry["message"].startswith("achieved: MACHINE-READY -> STICK-IN-HAND -> CANDY-FORMED -> "
                                                       "HANDED-OVER")
    assert c.status["belief"]["fluents"]["delivered"] and c.status["projection"] == []


def test_changes_to_the_booth_move_the_plan_through_its_table():
    c = control()
    run(c, "achieve")
    run(c, "order", flavour="RASPBERRY", customer="Customer")
    assert c.status["selected"] == "STICK-IN-HAND"
    assert run(c, "take_stick")["message"].startswith("robot took CandyStick")
    assert c.status["selected"] == "CANDY-FORMED"
    run(c, "empty_sugar_head")
    # The head is dry with the stick in hand: put the stick back first, so the robot can refill.
    assert c.status["kernels"][3] is False and c.status["selected"] == "FREE-GRIPPER"
    entry = run(c, "achieve")
    assert entry["ok"] and entry["message"].startswith("achieved: FREE-GRIPPER -> MACHINE-READY -> STICK-IN-HAND")
    run(c, "order", flavour="RASPBERRY", customer="Customer")
    assert run(c, "stop_machine")["message"].startswith("robot stopped the machine")
    assert c.status["selected"] == "MACHINE-READY"
    assert run(c, "achieve")["ok"]
    assert c.status["belief"]["fluents"]["delivered"]


def test_a_lost_candy_is_made_again():
    c = control()
    run(c, "lose_candy")
    assert c.status["belief"]["stage"] == "none" and c.status["selected"] == "MACHINE-READY"


def test_unachievable_and_ambiguous_orders_are_reported_not_raised():
    c = control()
    run(c, "cancel_open_orders")
    assert c.status["belief_error"].startswith("no open order")  # nothing ordered yet after cancelling
    run(c, "order", flavour="BLUEBERRY", customer="Customer")
    assert "unachievable" in c.status
    entry = run(c, "achieve")
    assert not entry["ok"] and entry["message"].startswith("GoalUnachievable")
    run(c, "order", flavour="RASPBERRY", customer="Customer")
    assert c.status["belief_error"].startswith("THE candy is ambiguous")
    assert run(c, "achieve")["message"].startswith("MultipleSolutionFound")


def test_http_queues_commands_and_refuses_other_origins():
    c = control()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_for(c))
    c.port = server.server_address[1]
    server.RequestHandlerClass = _handler_for(c)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{c.port}"
    try:
        def post(path, body, origin=None):
            request = urllib.request.Request(base + path, json.dumps(body).encode(), method="POST",
                                             headers={"Content-Type": "application/json", **({"Origin": origin} if origin else {})})
            try:
                return json.loads(urllib.request.urlopen(request).read())
            except urllib.error.HTTPError as error:
                return json.loads(error.read())
        assert post("/order", {"flavour": "RASPBERRY", "customer": "Customer"}, base)["ok"]
        assert c.commands.get_nowait() == Command("order", {"flavour": "RASPBERRY", "customer": "Customer"})
        assert post("/achieve", {}, "https://evil.example")["error"] == "origin not allowed"
        assert post("/order", {"flavour": "MANGO"})["error"] == "unknown flavour"
        assert post("/shutdown", {})["ok"] is False and c.commands.empty()
        assert b"Cotton candy plan control" in urllib.request.urlopen(base + "/").read()
        c.publish_status()
        assert "rows" in json.loads(urllib.request.urlopen(base + "/status").read())
    finally:
        server.shutdown()
