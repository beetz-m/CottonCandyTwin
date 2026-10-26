"""The kernel's episode in cramera's query panel: per step the designator, the goal template (D10), the gate, the
verdict, and per role the binding with the servant that made it and its status (the climb, D3). Filled live while the
plan runs (the lists grow; queries see the current state)."""
from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, List

from cramera.knowledge.presets import Preset
from cramera.knowledge.query_domain import QueryDomain
from cramera.knowledge.queryable_knowledge import QueryableKnowledge, QueryScope


@dataclass
class EpisodeStep:
    order: int
    path: str
    schema: str
    designator: str
    goal: str
    gate: str
    verdict: str
    warrant: str
    preact: str
    prediction: str
    t0: float
    t1: float


@dataclass
class EpisodeBinding:
    order: int
    path: str
    role: str
    symbol: str
    servant: str
    status: str


PRESETS = [
    ("Episode", "Which steps ran, in which plan, with what verdict?",
     "set_of(step.order, step.path, step.schema, step.verdict)"),
    ("Goals (D10)", "Which goal template did each step carry (perform -> goal)?",
     "set_of(step.order, step.schema, step.goal)"),
    ("Climb (D3)", "Who filled which role, with which servant and status?",
     "set_of(binding.order, binding.role, binding.symbol, binding.servant, binding.status)"),
    ("Climb (D3)", "Which bindings rest only on common sense (not recorded or anchored)?",
     "set_of(binding.order, binding.path, binding.role, binding.symbol, binding.servant)"
     ".where(binding.status == 'commonsense')"),
    ("Gate (D6)", "Which steps were not achieved by acting (skipped, refused, failed)?",
     "set_of(step.order, step.path, step.schema, step.verdict).where(step.verdict != 'goal achieved')"),
    ("Warrant (KR3)", "How well founded was each step (plausible / justified / rational), and why?",
     "set_of(step.order, step.schema, step.warrant, step.preact)"),
    ("Verdict (D4)", "Which steps did the pre-act verdict predict to fail, and what did it decide?",
     "set_of(step.order, step.path, step.prediction, step.preact).where(step.prediction != '')"),
    ("Process", "When (process time) did each step start and end?",
     "set_of(step.order, step.schema, step.t0, step.t1)"),
]


@dataclass
class EpisodeSource:
    steps: List[EpisodeStep]
    bindings: List[EpisodeBinding]

    def add(self, node: dict) -> None:
        k = len(self.steps) + 1
        self.steps.append(EpisodeStep(k, node.get("path", ""), node.get("schema", "note"),
                                      node.get("designator", node.get("note", "")), " ".join(node.get("goal", [])),
                                      node.get("gate", ""), node.get("verdict", node.get("note", "")),
                                      node.get("warrant", ""), node.get("preact", ""), node.get("prediction", ""),
                                      float(node.get("t0", node.get("t", 0.0))), float(node.get("t1", node.get("t", 0.0)))))
        for role, b in (node.get("bindings") or {}).items():
            self.bindings.append(EpisodeBinding(k, node.get("path", ""), role, str(b.get("symbol")),
                                                b.get("servant", ""), b.get("status", "")))

    def knowledge(self) -> List[QueryableKnowledge]:
        return [QueryableKnowledge(scope=QueryScope.CURRENT_STATE,
                                   domains=[QueryDomain("step", EpisodeStep, self.steps),
                                            QueryDomain("binding", EpisodeBinding, self.bindings)],
                                   extra_names={})]

    def presets(self) -> List[Preset]:
        return [Preset(f"[{c}] {q}", code, requires_live=True) for c, q, code in PRESETS]

    def register_on(self, bridge: Any) -> None:
        bridge.register_query_source(self.knowledge(), "Conceptual CRAM episode (booth.lisp)", self.presets())
