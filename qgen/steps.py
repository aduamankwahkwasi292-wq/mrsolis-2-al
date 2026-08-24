"""Human-readable step-by-step working, generated from the same computation
that produced the answer - so the steps are guaranteed consistent with it,
not a separate explanation that could drift from the real calculation."""
from __future__ import annotations

from typing import List

import sympy as sp

from .formulas import Formula, SYM, rearranged_expression
from .paramgen import Variation
from .wordproblems import WordProblem
from .calculus import X, format_expr
from . import render as render_mod


def word_problem_steps(wp: WordProblem, variation: Variation) -> List[str]:
    formula = wp.formula
    unknown_sym = SYM[variation.unknown]
    steps = []

    steps.append(f"Formula: {sp.sstr(formula.eq.lhs)} = {sp.sstr(formula.eq.rhs)}")

    rearranged = rearranged_expression(formula, variation.unknown)
    if rearranged is not None and formula.eq.lhs != unknown_sym:
        steps.append(f"Rearrange for {variation.unknown}: {variation.unknown} = {sp.sstr(rearranged)}")
    else:
        rearranged = formula.eq.rhs if formula.eq.lhs == unknown_sym else rearranged

    given_desc = ", ".join(
        f"{k} = {render_mod.format_value(v)}" for k, v in sorted(variation.given_values.items())
    )
    steps.append(f"Substitute known values ({given_desc}).")

    if rearranged is not None:
        subs = {SYM[k]: v for k, v in variation.given_values.items() if k in SYM}
        numeric_form = rearranged.subs(subs)
        steps.append(f"{variation.unknown} = {sp.sstr(numeric_form)}")

    unit = render_mod.DEFAULT_UNIT_FOR_QUANTITY.get(variation.unknown, "")
    steps.append(f"Answer: {variation.unknown} = {render_mod.format_value(variation.answer)}{unit}")
    return steps


def differentiation_steps(expr: sp.Expr) -> List[str]:
    steps = ["Differentiate term by term using the power rule: d/dx(x^n) = n*x^(n-1)."]
    if expr.is_polynomial(X):
        poly = sp.Poly(expr, X)
        term_derivs = []
        for monom, coeff in poly.terms():
            deg = monom[0]
            term = coeff * X ** deg
            d_term = sp.diff(term, X)
            if deg == 0:
                steps.append(f"d/dx({format_expr(term)}) = 0")
            else:
                steps.append(f"d/dx({format_expr(term)}) = {format_expr(d_term)}")
            term_derivs.append(d_term)
        total = sp.expand(sum(term_derivs))
        steps.append(f"Combine all terms: f'(x) = {format_expr(total)}")
    else:
        total = sp.diff(expr, X)
        steps.append(f"f'(x) = {format_expr(total)}")
    return steps


def integration_steps(expr: sp.Expr) -> List[str]:
    steps = ["Integrate term by term using the power rule: ∫x^n dx = x^(n+1)/(n+1) + C."]
    if expr.is_polynomial(X):
        poly = sp.Poly(expr, X)
        term_ints = []
        for monom, coeff in poly.terms():
            deg = monom[0]
            term = coeff * X ** deg
            i_term = sp.integrate(term, X)
            steps.append(f"∫{format_expr(term)} dx = {format_expr(i_term)}")
            term_ints.append(i_term)
        total = sp.expand(sum(term_ints))
        steps.append(f"Combine all terms and add the constant of integration: {format_expr(total)} + C")
    else:
        total = sp.integrate(expr, X)
        steps.append(f"Result: {format_expr(total)} + C")
    return steps
    steps = [f"Substitute x = {point} directly into the expression."]
    try:
        direct = expr.subs(X, point)
    except Exception:
        direct = None
    if direct is not None and direct.is_finite is not False and not direct.has(sp.zoo, sp.nan):
        steps.append(f"f({point}) = {format_expr(sp.simplify(direct))}")
    else:
        steps.append("Direct substitution gives an indeterminate form - simplify first.")
    result = sp.limit(expr, X, point)
    steps.append(f"Answer: the limit is {format_expr(result)}")
    return steps


def limit_steps(expr: sp.Expr, point) -> List[str]:
    steps = [f"Substitute x = {point} directly into the expression."]
    try:
        direct = expr.subs(X, point)
    except Exception:
        direct = None
    if direct is not None and not (hasattr(direct, "has") and direct.has(sp.zoo, sp.nan)):
        steps.append(f"f({point}) = {format_expr(sp.simplify(direct))}")
    else:
        steps.append("Direct substitution gives an indeterminate form - simplify first.")
    result = sp.limit(expr, X, point)
    steps.append(f"Answer: the limit is {format_expr(result)}")
    return steps
