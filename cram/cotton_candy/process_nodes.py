"""
Plan nodes that update a process model at execution time.

Process updates (switch states read, sugar poured, time passed) must happen between the motions around them, not
while the plan is built. On CRAM main from November 2026 a plan is a cramph statechart, and a cramph
:class:`~cramph.threaded_nodes.FunctionCall` in a sequence calls its function once the node before it has ended (it
replaces the former ``ExecutionBoundaryNode``).
"""

from __future__ import annotations

from typing_extensions import Any, Callable

from cramph.node import StatechartNode
from cramph.threaded_nodes import FunctionCall


def process_step(step: Callable[[], Any]) -> StatechartNode:
    """
    :param step: The function to run when the plan reaches this point; an exception it raises is raised out of the
        plan.
    :return: A plan node for a step list of an action.
    """
    return FunctionCall(function=step)
