"""Distractors modeled on real mistakes (wrong operation, unit slip, dropped
exponent) rather than random noise - pedagogically meaningful wrong answers."""
from __future__ import annotations

import hashlib
from typing import List

import sympy as sp

from .paramgen import Variation
from .wordproblems import WordProblem
from .calculus import X, format_expr
from . import render as render_mod


def _dedupe_numeric(values, correct, n):
    seen = {round(float(correct), 6)}
    out = []
    for v in values:
        try:
            rv = round(float(v), 6)
        except (TypeError, ValueError):
            continue
        if rv in seen or rv <= 0:
            continue
        seen.add(rv)
        out.append(v)
        if len(out) >= n:
            break
    return out


def word_problem_distractors(wp: WordProblem, variation: Variation, n: int = 3) -> List[str]:
    correct = variation.answer
    values = list(variation.given_values.values())
    candidates = []

    if len(values) == 2:
        a, b = values
        candidates.append(a * b)
        if b:
            candidates.append(a / b)
        if a:
            candidates.append(b / a)

    for factor in (10, 0.1, 1000, 0.001, 2, 0.5):
        candidates.append(correct * factor)

    picked = _dedupe_numeric(candidates, correct, n)
    return [render_mod.format_value(v) for v in picked]


def differentiation_distractors(expr: sp.Expr, correct_deriv: sp.Expr, n: int = 3) -> List[str]:
    candidates = []
    if expr.is_polynomial(X):
        poly = sp.Poly(expr, X)
        terms = poly.terms()

        # forgot to decrement the exponent (kept x^n instead of x^(n-1))
        wrong_a = sp.expand(sum(coeff * deg * X ** deg for (deg,), coeff in terms if deg > 0))
        # forgot to multiply by the exponent (only dropped the power)
        wrong_b = sp.expand(sum(coeff * X ** (deg - 1) for (deg,), coeff in terms if deg > 0))
        for w in (wrong_a, wrong_b):
            if w != correct_deriv and w != 0:
                candidates.append(w)

        # sign flip on one term
        add_terms = sp.Add.make_args(correct_deriv)
        if len(add_terms) >= 2:
            candidates.append(sp.expand(correct_deriv - 2 * add_terms[0]))
        # dropped the constant/lowest-order term entirely
        if len(add_terms) >= 2:
            candidates.append(sp.expand(correct_deriv - add_terms[-1]))

    seen = {format_expr(correct_deriv)}
    out = []
    seed = str(correct_deriv)
    candidates.sort(key=lambda c: hashlib.md5(f"{seed}:{c}".encode()).hexdigest())
    for c in candidates:
        s = format_expr(c)
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= n:
            break
    return out
