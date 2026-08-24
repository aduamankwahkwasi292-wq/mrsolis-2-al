"""Generate new parameter sets for a detected word problem: same formula,
different numbers, and optionally a different unknown - every answer is
computed by solving the real equation, so it's correct by construction."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Optional

from .formulas import Formula, solve_for
from .wordproblems import WordProblem

MULTIPLIERS = [0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1.1, 1.2, 1.25, 1.3, 1.4, 1.5,
               1.6, 1.75, 1.8, 2.0, 2.25, 2.5, 2.75, 3.0]


@dataclass
class Variation:
    given_values: Dict[str, float]
    unknown: str
    answer: float


def _nice_round(value: float) -> float:
    if value >= 1000:
        return round(value / 50) * 50
    if value >= 100:
        return round(value / 5) * 5
    if value >= 10:
        return round(value)
    if value >= 1:
        return round(value, 1)
    if value >= 0.01:
        return round(value, 3)
    return value


def _is_reasonable(value: float) -> bool:
    if value != value or value in (float("inf"), float("-inf")):
        return False
    if value <= 0:
        return False
    if value > 5e6 or value < 1e-6:
        return False
    return True


def _seeded_combo(seed_text: str, attempt: int, k: int) -> List[float]:
    out = []
    for i in range(k):
        h = hashlib.md5(f"{seed_text}:{attempt}:{i}".encode()).hexdigest()
        idx = int(h, 16) % len(MULTIPLIERS)
        out.append(MULTIPLIERS[idx])
    return out


def generate_variations(wp: WordProblem, n: int = 4, allow_unknown_swap: bool = True,
                         tries_per_target: int = 24) -> List[Variation]:
    formula = wp.formula
    all_quantities = sorted(formula.quantities)
    base_givens = {g.quantity_name: g.base_value for g in wp.givens}

    original_answer = solve_for(formula, base_givens, wp.ask_quantity)
    if original_answer is None or not _is_reasonable(original_answer):
        return []
    reference = dict(base_givens)
    reference[wp.ask_quantity] = original_answer

    targets = [wp.ask_quantity]
    if allow_unknown_swap:
        targets += [q for q in all_quantities if q != wp.ask_quantity]

    variations: List[Variation] = []
    seen = set()
    pending = {q: 0 for q in targets}  # next attempt index per target, for round-robin diversity
    progressed = True
    while len(variations) < n and progressed:
        progressed = False
        for unknown in targets:
            if len(variations) >= n:
                break
            given_names = [q for q in all_quantities if q != unknown]
            attempt = pending[unknown]
            if attempt >= tries_per_target:
                continue
            pending[unknown] += 1
            combo = _seeded_combo(wp.sentence + unknown, attempt, len(given_names))
            new_givens = {}
            for qname, mult in zip(given_names, combo):
                ref = reference.get(qname, 10.0)
                new_givens[qname] = _nice_round(ref * mult)
            answer = solve_for(formula, new_givens, unknown)
            if answer is None or not _is_reasonable(answer):
                continue
            answer = round(answer, 6)
            sig = (unknown, tuple(sorted(new_givens.items())))
            if sig in seen:
                continue
            seen.add(sig)
            variations.append(Variation(given_values=new_givens, unknown=unknown, answer=answer))
            progressed = True
    return variations
