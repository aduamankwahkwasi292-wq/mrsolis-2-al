"""
Proofs are a different shape of question from everything else in this
engine: there's no single number to compute, the "answer" is a logical
argument. But classical proofs are often parametrized by one number, and
the ARGUMENT STRUCTURE is fixed regardless of which number you plug in -
which is exactly the kind of thing this engine is built for. "Prove sqrt(2)
is irrational" and "prove sqrt(7) is irrational" are literally the same
proof with one substitution, so we can generate genuinely different,
rigorous, guaranteed-correct proofs by varying that one parameter.

Deliberately scoped to n = prime for now: the argument below relies on
Euclid's lemma (p | a^2 => p | a), which needs n itself to be prime. A
general square-free n needs a more involved exponent-parity argument that
isn't included here (see README).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

import sympy as sp

_IRRATIONAL_ROOT_RE = re.compile(
    r"(?:\b(?:square\s+root\s+of|root\s+of|root|sqrt)\b|√)\s*\(?\s*(\d+)\s*\)?", re.I
)
_PROVE_KEYWORDS = re.compile(r"\b(prove|show\s+that|demonstrate\s+that|verify\s+that)\b", re.I)
_IRRATIONAL_KEYWORD = re.compile(r"\birrational\b", re.I)

PRIME_POOL = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]


@dataclass
class IrrationalityProof:
    n: int


def detect_irrationality_proof(text: str) -> Optional[IrrationalityProof]:
    if not _PROVE_KEYWORDS.search(text) or not _IRRATIONAL_KEYWORD.search(text):
        return None
    m = _IRRATIONAL_ROOT_RE.search(text)
    if not m:
        return None
    n = int(m.group(1))
    if n < 2:
        return None
    return IrrationalityProof(n=n)


def _root_label(n: int) -> str:
    return f"√{n}"


def irrationality_proof_steps(n: int) -> List[str]:
    r = _root_label(n)
    return [
        f"Suppose, for contradiction, that {r} is rational.",
        f"Then {r} = a/b for some integers a and b with no common factor other than 1 "
        f"(the fraction is in lowest terms), and b ≠ 0.",
        f"Squaring both sides: {n} = a²/b², so a² = {n}·b².",
        f"This means {n} divides a² (since a² is {n} times an integer).",
        f"Since {n} is prime and {n} divides a², by Euclid's lemma {n} must divide a itself.",
        f"So a = {n}k for some integer k. Substituting back: ({n}k)² = {n}·b², "
        f"which gives {n}²k² = {n}·b², so {n}k² = b².",
        f"This means {n} divides b² as well, and since {n} is prime, {n} divides b too.",
        f"But then {n} divides both a and b, contradicting the assumption that a/b was in lowest terms.",
        f"This contradiction means the original assumption was false.",
        f"Therefore, {r} is irrational. ∎",
    ]


def build_irrationality_variants(original_n: int, n_variations: int) -> List[int]:
    """Different primes -> genuinely different (but structurally identical
    and equally rigorous) proofs. Deterministic order, original excluded so
    repeat requests surface fresh ones first."""
    import hashlib
    pool = [p for p in PRIME_POOL if p != original_n]
    ordered = sorted(pool, key=lambda p: hashlib.md5(f"{original_n}:{p}".encode()).hexdigest())
    if sp.isprime(original_n):
        ordered = [original_n] + ordered
    return ordered[:max(n_variations, 1)]
