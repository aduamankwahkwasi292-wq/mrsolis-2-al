"""
Calculus problems don't have "givens with units" like the physics word
problems - the parametrizable thing is the EXPRESSION itself (its
coefficients/exponents), and the "formula" is just "apply sp.diff /
sp.limit". sympy computes both generally - it doesn't need to know product
rule vs chain rule vs quotient rule, it just differentiates - which means
one code path covers nearly everything in a "rules of differentiation"
chapter, rather than one handler per rule.

Text extracted from PDF-typeset math is noisy (superscripts flatten onto
the baseline, fractions split across lines, ligatures break). This module
is deliberately narrow: it targets clean single-line polynomial-style
expressions ("f(x) = 3x4 + 2x3 - 5", "C = 680 + 4x + 0.01x2") since those
survive flattening well, rather than attempting to reconstruct arbitrary
nested fractions/roots/stacked-limit notation.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

import sympy as sp
from sympy.parsing.sympy_parser import (
    standard_transformations, implicit_multiplication_application, convert_xor,
    parse_expr,
)

X = sp.symbols("x")
_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)

# PDF ligature/control-char artifacts (seen from PyMuPDF on LaTeX-typeset
# PDFs) normalized to plain equivalents before anything else happens.
_CLEANUP_MAP = {
    "\u0016": "-", "\u2212": "-", "\u0010": '"', "\u0011": '"',
    "\u001c": "fi", "\u0192": "f", "·": "*", "×": "*", "÷": "/",
    "−": "-", "–": "-", "—": "-",
}
_SUPERSCRIPT_MAP = {"²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁰": "0", "¹": "1"}
_SUPERSCRIPT_RE = re.compile("[" + "".join(_SUPERSCRIPT_MAP) + "]+")
_SQRT_PAREN_RE = re.compile(r"√\s*\(")
_SQRT_TOKEN_RE = re.compile(r"√\s*([A-Za-z0-9]+(?:\.[0-9]+)?)")
_PI_RE = re.compile(r"π")


def normalize_math_text(text: str) -> str:
    for bad, good in _CLEANUP_MAP.items():
        text = text.replace(bad, good)
    text = re.sub(r"\(cid:\d+\)", "", text)
    # superscript digits ("x²" -> "x^2") - converted to caret here so the
    # existing implicit-exponent handling below picks it up uniformly
    text = _SUPERSCRIPT_RE.sub(lambda m: "^" + "".join(_SUPERSCRIPT_MAP[c] for c in m.group(0)), text)
    text = _SQRT_PAREN_RE.sub("sqrt(", text)          # √(...)  -> sqrt(...)
    text = _SQRT_TOKEN_RE.sub(r"sqrt(\1)", text)       # √4, √x  -> sqrt(4), sqrt(x)
    text = _PI_RE.sub(" pi ", text)
    return text


# "x2" -> "x**2", "0.3t0.6" -> "0.3*t**0.6" - a bare digit run glued directly
# onto a variable letter with no operator between them is an exponent that
# lost its superscript rendering. Only blocks matching when the LETTER
# itself is preceded by another letter (e.g. inside a word/identifier) -
# a preceding digit is the normal "coefficient x^n" case and must match.
_IMPLICIT_EXP_RE = re.compile(r"(?<![a-zA-Z])([a-zA-Z])(\d+(?:\.\d+)?)(?![a-zA-Z0-9])")


def _fix_implicit_exponents(expr_text: str) -> str:
    return _IMPLICIT_EXP_RE.sub(r"\1**\2", expr_text)


_LABEL_RE = re.compile(
    r"^\s*[A-Za-z][A-Za-z0-9_]{0,3}\s*(?:\([a-zA-Z]\))?\s*=\s*(.+)$"
)
_ALLOWED_EXPR_CHARS = re.compile(r"^[0-9a-zA-Z\s\+\-\*\/\.\(\)\^]+$")


def try_parse_expression(line: str, var: str = "x", allow_number: bool = False) -> Optional[sp.Expr]:
    """Parse a cleaned 'label = polynomial-ish expression' line into a
    sympy Expr. Deliberately conservative: rejects anything containing
    characters we can't confidently interpret (roots, fractions-as-stacked-
    text, trig/log without clean parens) rather than guessing."""
    line = normalize_math_text(line).strip().rstrip(".")
    m = _LABEL_RE.match(line)
    body = m.group(1) if m else line
    if not body or len(body) > 60:
        return None
    if not _ALLOWED_EXPR_CHARS.match(body):
        return None
    if body.count("(") != body.count(")"):
        return None
    body = _fix_implicit_exponents(body)
    try:
        expr = parse_expr(body, local_dict={var: X}, transformations=_TRANSFORMS)
    except Exception:
        return None
    if not expr.free_symbols <= {X}:
        return None
    if expr.is_number and not allow_number:
        return None
    return sp.expand(expr)


DIFF_KEYWORDS = re.compile(
    r"\b(differentiate|derivative|find f'|find y'|dy/dx|d/dx)\b", re.I
)
LIMIT_RE = re.compile(r"lim\s*x\s*(?:[-→]+>?|→)\s*([\-\d.]+|infinity|∞)", re.I)
_TRAILING_NOISE = re.compile(
    r"\s*(with respect to x|wrt x|w\.r\.t\.?\s*x|dx)\s*\.?\s*$", re.I
)
_DIFF_COMMAND = re.compile(
    r"\b(?:differentiate|find\s+(?:the\s+)?derivative\s+of|derivative\s+of|"
    r"what\s+is\s+(?:the\s+)?derivative\s+of|d/dx\s*of|find\s+f'\s*(?:of|for)?)\b[:\s]*",
    re.I,
)
_INTEGRATE_COMMAND = re.compile(
    r"\b(?:integrate|find\s+(?:the\s+)?(?:integral|antiderivative)\s+of|"
    r"(?:integral|antiderivative)\s+of|what\s+is\s+(?:the\s+)?integral\s+of)\b[:\s]*",
    re.I,
)


def _expression_for_command(text: str, command_re: "re.Pattern") -> Optional[sp.Expr]:
    """Natural typed phrasing doesn't always include a 'label = ...' - if the
    command word is found, take everything after it as the target; else
    the whole input is assumed to already BE the expression."""
    m = command_re.search(text)
    remainder = text[m.end():].strip() if m else text.strip()
    remainder = _TRAILING_NOISE.sub("", remainder).strip().rstrip(".")
    if not remainder:
        return None
    if "=" in remainder:
        return try_parse_expression(remainder)
    return try_parse_expression(f"f(x) = {remainder}")


@dataclass
class DiffProblem:
    slide_number: int
    expr: sp.Expr
    label: str  # "f(x)" or "y" etc, for display


@dataclass
class LimitProblem:
    slide_number: int
    expr: sp.Expr
    point: str  # numeric string, or "oo"/"-oo"


def detect_diff_problem(text: str, slide_number: int = 0) -> Optional[DiffProblem]:
    if not DIFF_KEYWORDS.search(text):
        return None
    expr = _expression_for_command(text, _DIFF_COMMAND)
    if expr is None or len(expr.free_symbols) != 1:
        return None
    return DiffProblem(slide_number=slide_number, expr=expr, label="f(x)")


INTEGRATE_KEYWORDS = re.compile(r"\b(integrate|integral|antiderivative)\b", re.I)


def detect_integrate_problem(text: str, slide_number: int = 0) -> Optional[DiffProblem]:
    if not INTEGRATE_KEYWORDS.search(text):
        return None
    expr = _expression_for_command(text, _INTEGRATE_COMMAND)
    if expr is None or len(expr.free_symbols) != 1:
        return None
    return DiffProblem(slide_number=slide_number, expr=expr, label="f(x)")


def detect_limit_problem(line: str, slide_number: int = 0) -> Optional[LimitProblem]:
    line_n = normalize_math_text(line)
    m = LIMIT_RE.search(line_n)
    if not m:
        return None
    point_raw = m.group(1)
    point = "oo" if point_raw.lower() in ("infinity", "∞") else point_raw
    # strip the "lim x-> a" prefix, parse what's left as the expression
    rest = line_n[m.end():].strip()
    rest = re.sub(r"^(?:of\s+|[\)\]]+\s*)", "", rest, flags=re.I).strip()
    expr = try_parse_expression(rest) if rest and "=" not in rest else \
        try_parse_expression("f(x) = " + rest)
    if expr is None or len(expr.free_symbols) != 1:
        return None
    return LimitProblem(slide_number=slide_number, expr=expr, point=point)


def vary_limit_expression(expr: sp.Expr, n: int, seed_text: str) -> List[sp.Expr]:
    """Same mechanism as vary_polynomial - keeps the limit's algebraic shape
    (so a 0/0-removable-singularity example stays removable) while changing
    the numbers."""
    return vary_polynomial(expr, n, seed_text)


# ---------- parametrization: vary coefficients, keep the same shape ----------

MULT_CHOICES = [sp.Rational(1, 2), sp.Rational(2, 3), sp.Rational(3, 4), sp.Rational(4, 5),
                sp.Rational(5, 4), sp.Rational(4, 3), sp.Rational(3, 2), 2, sp.Rational(5, 2),
                3, sp.Rational(7, 2), 4, sp.Rational(1, 3), sp.Rational(1, 4), 5]


def _seeded_choice(seed_text: str, choices: list):
    h = hashlib.md5(seed_text.encode()).hexdigest()
    return choices[int(h, 16) % len(choices)]


def _vary_single_polynomial(expr: sp.Expr, n: int, seed_text: str) -> List[sp.Expr]:
    poly = sp.Poly(expr, X)
    variants = []
    seen = {sp.expand(expr)}
    for attempt in range(n * 8 + 20):
        if len(variants) >= n:
            break
        new_expr = 0
        for monom, coeff in poly.terms():
            deg = monom[0]
            mult = _seeded_choice(f"{seed_text}:{attempt}:{deg}", MULT_CHOICES)
            new_coeff = coeff * mult
            if float(new_coeff).is_integer():
                new_coeff = int(new_coeff)
            new_expr += new_coeff * X ** deg
        new_expr = sp.expand(new_expr)
        if new_expr in seen or new_expr == 0:
            continue
        seen.add(new_expr)
        variants.append(new_expr)
    return variants


def vary_polynomial(expr: sp.Expr, n: int, seed_text: str) -> List[sp.Expr]:
    """Same powers of x, deterministically rescaled coefficients - keeps
    whichever differentiation/limit technique applied to the original still
    applying to the variant (same shape, different numbers). Numerator and
    denominator of a fraction are scaled SEPARATELY as polynomials (not as
    a flat set of numeric atoms) so a removable-singularity limit stays
    algebraically the same kind of problem, just with different numbers."""
    num, den = sp.fraction(sp.together(expr))
    if den != 1 and num.is_polynomial(X) and den.is_polynomial(X):
        num_variants = _vary_single_polynomial(num, n, seed_text + ":num")
        den_variants = _vary_single_polynomial(den, n, seed_text + ":den")
        out = []
        seen = {sp.expand(expr)}
        for i in range(min(len(num_variants), len(den_variants))):
            candidate = num_variants[i] / den_variants[i]
            if candidate in seen:
                continue
            seen.add(candidate)
            out.append(candidate)
        if out:
            return out[:n]
        # fall through to generic handling if we couldn't build enough

    if expr.is_polynomial(X):
        return _vary_single_polynomial(expr, n, seed_text)

    variants = []
    seen = {sp.expand(expr)}
    exponent_atoms = {sub.exp for sub in expr.atoms(sp.Pow) if sub.exp.is_Number}
    for attempt in range(n * 8 + 20):
        if len(variants) >= n:
            break
        mult = _seeded_choice(f"{seed_text}:{attempt}", MULT_CHOICES)
        subs_map = {}
        for atom in expr.atoms(sp.Number):
            if atom == 0 or atom in exponent_atoms:
                continue
            subs_map[atom] = sp.nsimplify(atom * mult)
        new_expr = sp.expand(expr.subs(subs_map, simultaneous=True))
        if new_expr in seen or new_expr == 0:
            continue
        seen.add(new_expr)
        variants.append(new_expr)
    return variants


def format_expr(expr: sp.Expr) -> str:
    s = sp.sstr(sp.nsimplify(expr, rational=False))
    s = s.replace("**", "^").replace("*", "")
    return s
