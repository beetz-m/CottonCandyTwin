"""
Plan nodes that update a process model at execution time.

coraplex runs a ``code`` node's function while the plan is being expanded, i.e. before the motions in front of it
have run; process updates (switch states read, sugar poured, time passed) must instead happen between the motions.
An :class:`~coraplex.plans.plan_node.ExecutionBoundaryNode` splits the motion state charts around itself, and its
executable runs in plan order - the same mechanism coraplex uses to re-attach objects (``ReAttachNode``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Any, Callable

from coraplex.plans.executables import Executable
from coraplex.plans.factories import execute_single
from coraplex.plans.plan_node import ExecutionBoundaryNode, PlanNode


@dataclass
class ProcessStepExecutable(Executable):
    """
    Runs one process step when the plan reaches it.
    """

    step: Callable[[], Any] = field(kw_only=True)
    """
    The function that updates the process.
    """

    def execute(self) -> Any:
        return self.step()


@dataclass
class ProcessStepNode(ExecutionBoundaryNode):
    """
    A plan node that updates a process model at execution time, between the motions around it.
    """

    step: Callable[[], Any] = field(kw_only=True)
    """
    The function that updates the process.
    """

    def notify(self):
        pass

    def parse(self) -> ProcessStepExecutable:
        return ProcessStepExecutable(context=self.context, step=self.step)


def process_step(step: Callable[[], Any]) -> PlanNode:
    """
    :param step: The function to run when the plan reaches this point.
    :return: A plan node for ``sequential`` and the other plan factories.
    """
    return execute_single(ProcessStepNode(step=step))
