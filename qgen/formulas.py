"""
A formula is a sympy Eq over named symbols, tagged with which quantity-names
(from units.py) it relates. Given any N-1 of its quantities as numbers, we
solve symbolically for whichever one is missing - so the answer is derived
by real algebra, not looked up or guessed, and is correct by construction.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional

import sympy as sp

# One shared symbol per quantity name, positive-real by default (division/
# sqrt behave better; a few overridden below where negative is meaningful).
_NAMES = [
    "voltage", "current", "power", "resistance", "capacitance", "inductance",
    "frequency", "time", "length", "radius", "diameter", "mass", "force",
    "pressure", "energy", "speed", "acceleration", "angle", "temperature",
    "area", "volume", "circumference", "charge", "period", "momentum",
    "work", "torque", "density", "wavelength",
]
SYM: Dict[str, sp.Symbol] = {n: sp.symbols(n, positive=True) for n in _NAMES}


@dataclass
class Formula:
    name: str
    eq: sp.Eq
    quantities: FrozenSet[str]
    units_hint: Dict[str, str]  # quantity_name -> canonical unit symbol, for display


def _f(name, lhs_name, rhs_expr, units_hint):
    lhs = SYM[lhs_name]
    quantities = frozenset({lhs_name} | {s.name for s in rhs_expr.free_symbols})
    return Formula(name=name, eq=sp.Eq(lhs, rhs_expr), quantities=quantities, units_hint=units_hint)


V, I, P, R = SYM["voltage"], SYM["current"], SYM["power"], SYM["resistance"]
m, a, F, s_, t, v_ = SYM["mass"], SYM["acceleration"], SYM["force"], SYM["length"], SYM["time"], SYM["speed"]
r_, A_, C_, d_ = SYM["radius"], SYM["area"], SYM["circumference"], SYM["diameter"]
f_, T_, E_ = SYM["frequency"], SYM["period"], SYM["energy"]
Q_, cap_, mom_, W_, tor_, rho_, lam_, vol_ = (
    SYM["charge"], SYM["capacitance"], SYM["momentum"], SYM["work"],
    SYM["torque"], SYM["density"], SYM["wavelength"], SYM["volume"],
)

FORMULA_LIBRARY: List[Formula] = [
    _f("Ohm's Law", "voltage", I * R, {"voltage": "V", "current": "A", "resistance": "ohm"}),
    _f("Power (V, I)", "power", V * I, {"power": "W", "voltage": "V", "current": "A"}),
    _f("Power (I, R)", "power", I ** 2 * R, {"power": "W", "current": "A", "resistance": "ohm"}),
    _f("Power (V, R)", "power", V ** 2 / R, {"power": "W", "voltage": "V", "resistance": "ohm"}),
    _f("Newton's Second Law", "force", m * a, {"force": "N", "mass": "kg", "acceleration": "m/s^2"}),
    _f("Distance-Speed-Time", "length", v_ * t, {"length": "m", "speed": "m/s", "time": "s"}),
    _f("Speed", "speed", s_ / t, {"speed": "m/s", "length": "m", "time": "s"}),
    _f("Kinetic Energy", "energy", sp.Rational(1, 2) * m * v_ ** 2, {"energy": "J", "mass": "kg", "speed": "m/s"}),
    _f("Circle Area", "area", sp.pi * r_ ** 2, {"area": "m^2", "radius": "m"}),
    _f("Circle Circumference", "circumference", 2 * sp.pi * r_, {"circumference": "m", "radius": "m"}),
    _f("Diameter-Radius", "diameter", 2 * r_, {"diameter": "m", "radius": "m"}),
    _f("Frequency-Period", "frequency", 1 / T_, {"frequency": "Hz", "time": "s"}),
    _f("Momentum", "momentum", m * v_, {"momentum": "kg*m/s", "mass": "kg", "speed": "m/s"}),
    _f("Impulse-Momentum", "momentum", F * t, {"momentum": "kg*m/s", "force": "N", "time": "s"}),
    _f("Work", "work", F * s_, {"work": "J", "force": "N", "length": "m"}),
    _f("Power from Work", "power", W_ / t, {"power": "W", "work": "J", "time": "s"}),
    _f("Charge from Current", "charge", I * t, {"charge": "C", "current": "A", "time": "s"}),
    _f("Capacitor Charge", "charge", cap_ * V, {"charge": "C", "capacitance": "F", "voltage": "V"}),
    _f("Sphere Volume", "volume", sp.Rational(4, 3) * sp.pi * r_ ** 3, {"volume": "m^3", "radius": "m"}),
    _f("Sphere Surface Area", "area", 4 * sp.pi * r_ ** 2, {"area": "m^2", "radius": "m"}),
    _f("Cylinder Volume", "volume", sp.pi * r_ ** 2 * s_, {"volume": "m^3", "radius": "m", "length": "m"}),
    _f("Torque", "torque", F * s_, {"torque": "N*m", "force": "N", "length": "m"}),
    _f("Density", "density", m / vol_, {"density": "kg/m^3", "mass": "kg", "volume": "m^3"}),
    _f("Wave Speed", "speed", f_ * lam_, {"speed": "m/s", "frequency": "Hz", "wavelength": "m"}),
    _f("Gravitational PE", "energy", m * 9.8 * s_, {"energy": "J", "mass": "kg", "length": "m"}),
]


def find_formulas_for(quantities: FrozenSet[str]) -> List[Formula]:
    """Formulas whose quantity set is exactly this set (most specific match)."""
    return [f for f in FORMULA_LIBRARY if f.quantities == quantities]


def solve_for(formula: Formula, knowns: Dict[str, float], unknown: str) -> Optional[float]:
    """Substitute knowns into formula.eq and solve for `unknown`. Returns a
    plain float, or None if unsolvable / no real positive solution."""
    subs = {SYM[k]: v for k, v in knowns.items() if k in SYM}
    eq = formula.eq.subs(subs)
    try:
        sols = sp.solve(eq, SYM[unknown])
    except Exception:
        return None
    real_sols = []
    for sol in sols:
        try:
            val = complex(sol)
        except TypeError:
            continue
        if abs(val.imag) < 1e-9:
            real_sols.append(val.real)
    if not real_sols:
        return None
    positive = [v for v in real_sols if v > 0]
    return positive[0] if positive else real_sols[0]


def rearranged_expression(formula: Formula, unknown: str) -> Optional[sp.Expr]:
    """Symbolic (not numeric) rearrangement - used for showing solution
    steps, e.g. turning 'P = V*I' into 'I = P/V' before any numbers go in."""
    try:
        sols = sp.solve(formula.eq, SYM[unknown])
    except Exception:
        return None
    return sols[0] if sols else None


_EQUATION_LINE = __import__("re").compile(
    r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*([^=]+?)\s*$"
)


def _insert_implicit_mult(text: str) -> str:
    """'ma' -> 'm*a', 'VI' -> 'V*I': split a run of letters into single-char
    multiplication ONLY when every letter in the run is one of our known
    single-letter physics symbols - avoids mangling real multi-letter names."""
    import re

    def repl(m):
        run = m.group(0)
        if len(run) > 1 and all(c.lower() in _LETTER_HINTS for c in run):
            return "*".join(run)
        return run

    return re.sub(r"[A-Za-z]+", repl, text)


def try_parse_slide_formula(line: str) -> Optional[Formula]:
    """Parse a short 'P = V * I' style line from a slide into a Formula.
    Deliberately narrow (single '=', short line) to avoid misreading prose
    that happens to contain an equals sign."""
    line = line.strip().rstrip(".")
    if len(line) > 40 or line.count("=") != 1:
        return None
    m = _EQUATION_LINE.match(line)
    if not m:
        return None
    lhs_raw, rhs_raw = m.group(1), m.group(2)
    lhs_q = symbol_to_quantity(lhs_raw)
    if lhs_q is None:
        return None
    try:
        rhs_raw = _insert_implicit_mult(rhs_raw)
        local_dict = {sym: SYM[qname] for sym, qname in _slide_symbol_map(rhs_raw).items()}
        transformations = sp.parsing.sympy_parser.standard_transformations + (
            sp.parsing.sympy_parser.implicit_multiplication_application,
        )
        rhs_expr = sp.parsing.sympy_parser.parse_expr(
            rhs_raw, local_dict=local_dict, transformations=transformations
        )
    except Exception:
        return None
    quantities = frozenset({lhs_q} | {s.name for s in rhs_expr.free_symbols})
    if len(quantities) < 2:
        return None
    unresolved = [s for s in rhs_expr.free_symbols if s.name not in SYM]
    if unresolved:
        return None  # a letter we couldn't map to a known quantity - don't guess
    return Formula(name=f"(from slide) {line}", eq=sp.Eq(SYM[lhs_q], rhs_expr),
                    quantities=quantities, units_hint={})


# Single-letter symbol conventions used on slides -> our quantity names.
_LETTER_HINTS = {
    "v": "voltage", "e": "voltage", "i": "current", "p": "power", "r": "resistance",
    "f": "force", "m": "mass", "a": "acceleration", "d": "length", "s": "length",
    "t": "time", "c": "circumference", "j": "energy", "w": "energy", "hz": "frequency",
}


def symbol_to_quantity(sym: str) -> Optional[str]:
    return _LETTER_HINTS.get(sym.strip().lower())


def _slide_symbol_map(expr_text: str) -> Dict[str, str]:
    import re
    out = {}
    for tok in re.findall(r"[A-Za-z]+", expr_text):
        q = symbol_to_quantity(tok)
        if q:
            out[tok] = q
    return out
