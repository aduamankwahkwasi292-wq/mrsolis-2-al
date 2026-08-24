"""
MrSOLIS 2-AL core: the student types ONE math/calculation question. We
detect what kind it is (word problem with a formula, differentiation,
integration, or limit), then generate N variations by tweaking numbers/
coefficients and recomputing the answer with sympy - correct by
construction, every time.

Typed input sidesteps the hard problem entirely: a student's own clean,
deliberate sentence is vastly easier to parse reliably than text scraped
from a slide (OCR noise, flattened superscripts, caption fragments,
ambiguous single-letter variables with no surrounding context).
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any, Dict, List, Optional

import sympy as sp

from . import store
from .calculus import (
    X, DiffProblem, LimitProblem, format_expr,
    detect_diff_problem, detect_integrate_problem, detect_limit_problem,
    vary_polynomial, vary_limit_expression,
)
from .dedup import DedupFilter
from .distractors_math import differentiation_distractors, word_problem_distractors
from .algebra import EquationProblem, detect_equation, equation_steps, solve_equation
from .paramgen import generate_variations
from .proofs import IrrationalityProof, build_irrationality_variants, detect_irrationality_proof, irrationality_proof_steps
from .render import DEFAULT_UNIT_FOR_QUANTITY, format_value, render_question
from .steps import differentiation_steps, integration_steps, limit_steps, word_problem_steps
from .wordproblems import WordProblem, detect_word_problem

NO_MATCH_MESSAGE = (
    "Couldn't turn this into a calculable question. For a word problem, "
    "include clear given values with units and what to find (e.g. \"A lamp "
    "consumes 200W of power, if the voltage is 100V, calculate the "
    "current\"). For calculus, say what to do (e.g. \"Differentiate "
    "f(x) = 3x^2 + 2x\", \"Integrate x^3 - 2x\", \"Evaluate lim x->2 of "
    "x^2 - 4\")."
)


def _fact_key(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:16]


def _mcq_options(correct: str, distractors: List[str], seed_text: str) -> List[str]:
    opts = [correct] + distractors
    return sorted(opts, key=lambda o: hashlib.md5((seed_text + "|" + o).encode()).hexdigest())


# ---------------------------------------------------------------- word problems

def _build_word_problem_candidates(wp: WordProblem, n_variations: int) -> List[dict]:
    out = []
    fact_key = _fact_key(f"wp:{wp.sentence}")
    for v in generate_variations(wp, n=n_variations, allow_unknown_swap=True):
        qtext = render_question(wp, v)
        if not qtext:
            continue
        unit = DEFAULT_UNIT_FOR_QUANTITY.get(v.unknown, "")
        answer = f"{format_value(v.answer)}{unit}"
        distractors = word_problem_distractors(wp, v, n=3)
        options = _mcq_options(answer, distractors, qtext) if len(distractors) >= 3 else None
        out.append({
            "fact_type": "word_problem",
            "fact_key": fact_key,
            "question_type": "mcq" if options else "short_answer",
            "question": qtext,
            "answer": answer,
            "options": options,
            "steps": word_problem_steps(wp, v),
            "source_sentence": wp.sentence,
            "difficulty": "medium" if len(v.given_values) <= 2 else "hard",
        })
    return out


# ---------------------------------------------------------------- calculus

def _build_diff_candidates(dp: DiffProblem, n_variations: int) -> List[dict]:
    out = []
    fact_key = _fact_key(f"diff:{dp.expr}")
    for expr in vary_polynomial(dp.expr, n_variations, f"diff:{dp.expr}"):
        deriv = sp.diff(expr, X)
        qtext = f"Differentiate f(x) = {format_expr(expr)} with respect to x."
        answer = f"f'(x) = {format_expr(deriv)}"
        distractors = differentiation_distractors(expr, deriv, n=3)
        options = _mcq_options(answer, distractors, qtext) if len(distractors) >= 3 else None
        degree = sp.degree(expr, X) if expr.is_polynomial(X) else 2
        out.append({
            "fact_type": "differentiation",
            "fact_key": fact_key,
            "question_type": "mcq" if options else "short_answer",
            "question": qtext,
            "answer": answer,
            "options": options,
            "steps": differentiation_steps(expr),
            "source_sentence": f"f(x) = {format_expr(dp.expr)}",
            "difficulty": "easy" if degree <= 2 else ("medium" if degree <= 4 else "hard"),
        })
    return out


def _build_integrate_candidates(dp: DiffProblem, n_variations: int) -> List[dict]:
    out = []
    fact_key = _fact_key(f"int:{dp.expr}")
    for expr in vary_polynomial(dp.expr, n_variations, f"int:{dp.expr}"):
        result = sp.integrate(expr, X)
        qtext = f"Find ∫({format_expr(expr)}) dx."
        answer = f"{format_expr(result)} + C"
        degree = sp.degree(expr, X) if expr.is_polynomial(X) else 2
        out.append({
            "fact_type": "integration",
            "fact_key": fact_key,
            "question_type": "short_answer",
            "question": qtext,
            "answer": answer,
            "options": None,
            "steps": integration_steps(expr),
            "source_sentence": f"f(x) = {format_expr(dp.expr)}",
            "difficulty": "easy" if degree <= 2 else ("medium" if degree <= 4 else "hard"),
        })
    return out


def _build_equation_candidates(eq: EquationProblem, n_variations: int) -> List[dict]:
    out = []
    combined = sp.expand(eq.lhs - eq.rhs)
    fact_key = _fact_key(f"eq:{combined}")
    for variant in vary_polynomial(combined, n_variations, f"eq:{combined}"):
        sols = None
        try:
            sols = sp.solve(sp.Eq(variant, 0), X)
        except Exception:
            continue
        if not sols:
            continue
        variant_eq = EquationProblem(lhs=variant, rhs=sp.Integer(0))
        qtext = f"Solve for x: {format_expr(variant)} = 0"
        vals = ", ".join(format_expr(sp.simplify(s)) for s in sols)
        answer = f"x = {vals}"
        degree = sp.degree(variant, X) if variant.is_polynomial(X) else 2
        out.append({
            "fact_type": "algebra",
            "fact_key": fact_key,
            "question_type": "short_answer",
            "question": qtext,
            "answer": answer,
            "options": None,
            "steps": equation_steps(variant_eq, sols),
            "source_sentence": f"{format_expr(eq.lhs)} = {format_expr(eq.rhs)}",
            "difficulty": "easy" if degree <= 1 else ("medium" if degree == 2 else "hard"),
        })
    return out


def _build_proof_candidates(pf: IrrationalityProof, n_variations: int) -> List[dict]:
    out = []
    for n in build_irrationality_variants(pf.n, n_variations):
        if not sp.isprime(n):
            continue
        fact_key = _fact_key(f"proof:irrational-sqrt:{n}")
        qtext = f"Prove that √{n} is irrational."
        answer = f"√{n} is irrational (proof by contradiction using Euclid's lemma)."
        out.append({
            "fact_type": "proof",
            "fact_key": fact_key,
            "question_type": "short_answer",
            "question": qtext,
            "answer": answer,
            "options": None,
            "steps": irrationality_proof_steps(n),
            "source_sentence": f"Prove that √{pf.n} is irrational.",
            "difficulty": "medium",
        })
    return out


def _build_limit_candidates(lp: LimitProblem, n_variations: int) -> List[dict]:
    out = []
    fact_key = _fact_key(f"lim:{lp.expr}:{lp.point}")
    point_sym = sp.sympify(lp.point)
    variants = vary_limit_expression(lp.expr, n_variations, f"lim:{lp.expr}:{lp.point}")
    for expr in [lp.expr] + variants:
        try:
            result = sp.limit(expr, X, point_sym)
        except Exception:
            continue
        if result.has(sp.zoo, sp.nan):
            continue
        qtext = f"Evaluate lim(x→{lp.point}) [{format_expr(expr)}]."
        answer = format_expr(result)
        out.append({
            "fact_type": "limit",
            "fact_key": fact_key,
            "question_type": "short_answer",
            "question": qtext,
            "answer": answer,
            "options": None,
            "steps": limit_steps(expr, point_sym),
            "source_sentence": f"lim(x→{lp.point}) {format_expr(lp.expr)}",
            "difficulty": "medium",
        })
        if len(out) >= n_variations:
            break
    return out


# ---------------------------------------------------------------- selection

_BUILDERS = {
    "word_problem": lambda obj, buf: _build_word_problem_candidates(obj, buf),
    "differentiation": lambda obj, buf: _build_diff_candidates(obj, buf),
    "integration": lambda obj, buf: _build_integrate_candidates(obj, buf),
    "limit": lambda obj, buf: _build_limit_candidates(obj, buf),
    "proof": lambda obj, buf: _build_proof_candidates(obj, buf),
    "algebra": lambda obj, buf: _build_equation_candidates(obj, buf),
}


def _generate_with_retries(detected_type: str, detected_obj, dedup: DedupFilter, n: int) -> List[dict]:
    """Candidate generation and dedup can both come up short of `n` on a
    request that reuses an already-populated deck (most of the "nice"
    variations near the original numbers may already be taken). Escalate
    the buffer and retry, ACCUMULATING across attempts, rather than
    silently returning fewer than asked."""
    builder = _BUILDERS[detected_type]
    selected: List[dict] = []
    selected_texts = set()
    for buffer_mult in (3, 8, 20, 45, 80):
        if len(selected) >= n:
            break
        buffer = max(n * buffer_mult, n + 10)
        candidates = builder(detected_obj, buffer)
        candidates.sort(key=lambda c: hashlib.md5(c["question"].encode()).hexdigest())
        for cand in candidates:
            if len(selected) >= n:
                break
            if cand["question"] in selected_texts:
                continue
            if dedup.is_duplicate(cand["question"], cand["fact_key"], allow_multiple_per_fact=True):
                continue
            selected.append(cand)
            selected_texts.add(cand["question"])
            dedup.register(cand["question"], cand["fact_key"])
    return selected


# ---------------------------------------------------------------- entry point

def generate_from_question(deck_id: str, question_text: str, n: int = 10,
                            reset: bool = False) -> Dict[str, Any]:
    if reset:
        store.clear_deck(deck_id)

    question_text = (question_text or "").strip()
    if not question_text:
        return {"deck_id": deck_id, "detected_type": None, "generated": 0,
                "questions": [], "error": "Please type a question first."}

    detected_type: Optional[str] = None
    detected_obj = None

    pf = detect_irrationality_proof(question_text)
    if pf is not None:
        if sp.isprime(pf.n):
            detected_type, detected_obj = "proof", pf
        elif sp.sqrt(pf.n).is_integer:
            return {"deck_id": deck_id, "detected_type": None, "generated": 0, "questions": [],
                    "error": f"√{pf.n} is actually rational (it equals {int(sp.sqrt(pf.n))}), "
                             f"so this can't be proved irrational. Try a prime number instead, "
                             f"e.g. \"prove √{pf.n + 1 if sp.isprime(pf.n + 1) else 2} is irrational\"."}
        else:
            return {"deck_id": deck_id, "detected_type": None, "generated": 0, "questions": [],
                    "error": f"√{pf.n} is genuinely irrational, but {pf.n} isn't prime, and this engine's "
                             f"irrationality proof currently only covers prime radicands (it relies on "
                             f"Euclid's lemma). Try a prime, e.g. \"prove √2 is irrational\" or \"prove "
                             f"√{pf.n} is irrational\" with a prime nearby."}

    wp = detect_word_problem(question_text, slide_number=0)
    if detected_obj is None and wp is not None and _build_word_problem_candidates(wp, 3):
        detected_type, detected_obj = "word_problem", wp

    if detected_obj is None:
        dp = detect_diff_problem(question_text)
        if dp is not None:
            detected_type, detected_obj = "differentiation", dp

    if detected_obj is None:
        ip = detect_integrate_problem(question_text)
        if ip is not None:
            detected_type, detected_obj = "integration", ip

    if detected_obj is None:
        lp = detect_limit_problem(question_text)
        if lp is not None and _build_limit_candidates(lp, 3):
            detected_type, detected_obj = "limit", lp

    if detected_obj is None:
        eqp = detect_equation(question_text)
        if eqp is not None:
            detected_type, detected_obj = "algebra", eqp

    if detected_obj is None:
        return {"deck_id": deck_id, "detected_type": None, "generated": 0,
                "questions": [], "error": NO_MATCH_MESSAGE}

    # Near-duplicate (TF-IDF) checking is the wrong tool here: these
    # questions are deliberately templated, so two variants correctly
    # differing only in their numbers still share almost all their words
    # and can score as "near-duplicate" even though they're different
    # questions with different correct answers. Exact-hash dedup (still
    # active) is what actually matters for this pipeline.
    dedup = DedupFilter(deck_id, near_dup_threshold=None)
    selected = _generate_with_retries(detected_type, detected_obj, dedup, n)

    for i, c in enumerate(selected, 1):
        c["id"] = f"{deck_id}-{c['fact_key']}-{i}"

    return {
        "deck_id": deck_id,
        "detected_type": detected_type,
        "original_question": question_text,
        "requested": n,
        "generated": len(selected),
        "questions": selected,
    }
