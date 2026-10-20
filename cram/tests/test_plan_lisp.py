"""
The Lisp rendering of the generalized plan (plans/make-and-hand-over.lisp) stays in step with the executable plan:
it reads as balanced s-expressions, and its triangle table has the same sub-goal tags in the same order.
"""

from __future__ import annotations

import re
from pathlib import Path

from test_universal_plan import fresh

LISP = Path(__file__).resolve().parents[1] / "plans" / "make-and-hand-over.lisp"


def read_forms(text: str) -> list:
    """
    :return: The top-level s-expressions of a Lisp text (comments, strings and quote marks removed).
    """
    text = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)
    text = re.sub(r";[^\n]*", "", text).replace("'", " ")
    stack = [[]]
    for token in re.findall(r"\(|\)|[^\s()]+", text):
        if token == "(":
            stack.append([])
        elif token == ")":
            assert len(stack) > 1, "unbalanced ')'"
            form = stack.pop()
            stack[-1].append(form)
        else:
            stack[-1].append(token)
    assert len(stack) == 1, f"{len(stack) - 1} unclosed '('"
    return stack[0]


def triangle_table_rows(forms: list) -> list:
    table = next(f for f in forms if f[:2] == ["def-triangle-table", "make-and-hand-over-table"])
    return [row for row in table[3:] if row and row[0].isdigit()]


def test_lisp_plan_is_balanced_and_matches_the_executable_sub_goals():
    rows = triangle_table_rows(read_forms(LISP.read_text()))
    *_, plan = fresh()
    assert [int(r[0]) for r in rows] == [s.index for s in plan.steps()]
    assert [r[1].upper() for r in rows] == [s.tag for s in plan.steps()]
    for row in rows:
        assert ":goal" in row and ":kernel" in row and ":methods" in row
    protected = [r[1].upper() for r in rows if ":protects" in r]
    assert protected == [s.tag for s in plan.steps() if s.protects is not None]
