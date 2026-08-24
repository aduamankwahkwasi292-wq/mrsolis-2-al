"""General equation solving - linear, quadratic, or anything sympy can
solve exactly. Unlike the word-problem engine (which needs a formula from
a curated library), this handles a bare equation directly: move everything
to one side, vary coefficients, solve with sp.solve."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

import sympy as sp

from .calculus import X, format_expr, normalize_math_text, try_parse_expression

SOLVE_KEYWORDS = re.compile(r"\b(solve|find\s+x|value\s+of\s+x)\b", re.I)
_EQUATION_SPLIT = re.compile(r"^(.*?)=(.*)$")
_TRAILING_FORX = re.compile(r"\s*for\s+x\s*\.?\s*$", re.I)
_SOLVE_COMMAND = re.compile(r"\bsolve\b[:\s]*", re.I)


@dataclass
class EquationProblem:
    lhs: sp.Expr
    rhs: sp.Expr


def detect_equation(text: str) -> Optional[EquationProblem]:
    if not SOLVE_KEYWORDS.search(text) or "=" not in text:
        return None
    body = _SOLVE_COMMAND.sub("", normalize_math_text(text), count=1).strip()
    body = _TRAILING_FORX.sub("", body).strip().rstrip(".")
    m = _EQUATION_SPLIT.match(body)
    if not m:
        return None
    lhs_text, rhs_text = m.group(1).strip(), m.group(2).strip()
    lhs = try_parse_expression(f"f(x) = {lhs_text}", allow_number=True)
    rhs = try_parse_expression(f"f(x) = {rhs_text}", allow_number=True)
    if lhs is None or rhs is None:
        return None
    combined = lhs - rhs
    if not combined.free_symbols <= {X} or X not in combined.free_symbols:
        return None
    return EquationProblem(lhs=lhs, rhs=rhs)


def solve_equation(eq: EquationProblem):
    combined = sp.expand(eq.lhs - eq.rhs)
    try:
        solutions = sp.solve(sp.Eq(combined, 0), X)
    except Exception:
        return None
    return solutions


def equation_steps(eq: EquationProblem, solutions) -> List[str]:
    combined = sp.expand(eq.lhs - eq.rhs)
    steps = [
        f"Original equation: {format_expr(eq.lhs)} = {format_expr(eq.rhs)}",
        f"Move everything to one side: {format_expr(combined)} = 0",
    ]
    degree = sp.degree(combined, X) if combined.is_polynomial(X) else None
    if degree == 1:
        steps.append("This is linear - isolate x directly.")
    elif degree == 2:
        a = combined.as_poly(X).all_coeffs()
        steps.append("This is quadratic - solved using the quadratic formula "
                      "x = (-b ± √(b²-4ac)) / 2a.")
    if not solutions:
        steps.append("No real solution exists for this equation.")
    elif len(solutions) == 1:
        steps.append(f"Answer: x = {format_expr(sp.simplify(solutions[0]))}")
    else:
        vals = ", ".join(format_expr(sp.simplify(s)) for s in solutions)
        steps.append(f"Answer: x = {vals}")
    return steps
