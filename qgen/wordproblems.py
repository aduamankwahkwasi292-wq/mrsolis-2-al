"""Detect a worked-example word problem in a sentence: some "givens" (number
+ unit) plus an "ask" clause naming an unknown quantity, where the whole set
matches a known formula. Deliberately strict (exact quantity-set match) -
we'd rather skip a sentence than guess the wrong relationship."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .units import find_quantities, quantity_name_from_word, Quantity
from .formulas import find_formulas_for, try_parse_slide_formula, Formula, symbol_to_quantity

ASK_RE = re.compile(
    r"\b(?:calculate|find|determine|compute|solve\s+for|evaluate|what\s+is|"
    r"what\s+are|what\s+will\s+be|what\s+was)\b(.{0,60}?)(?:[.?]|$)",
    re.I,
)

_SCENARIO_RE = re.compile(r"^\s*(A|An|The)\s+[a-zA-Z][a-zA-Z\s\-]{1,30}?(?=\s+(?:is|are|has|have|consumes|draws|carries|weighs|travels|falls|moves|accelerates|produces|generates|requires|dissipates))", re.I)


@dataclass
class WordProblem:
    slide_number: int
    sentence: str
    givens: List[Quantity]
    ask_quantity: str
    ask_start: int
    ask_end: int
    formula: Formula
    scenario: Optional[str]


def find_ask(sentence: str) -> Optional[Tuple[str, int, int]]:
    m = ASK_RE.search(sentence)
    if not m:
        return None
    phrase = m.group(1)
    words = re.findall(r"[a-zA-Z]+", phrase)
    for word in words:
        q = quantity_name_from_word(word)
        if q:
            return q, m.start(), m.end()
    # fall back to bare-symbol asks ("find F", "solve for V")
    for word in words:
        if len(word) <= 2:
            q = symbol_to_quantity(word)
            if q:
                return q, m.start(), m.end()
    return None


def find_scenario(sentence: str) -> Optional[str]:
    m = _SCENARIO_RE.match(sentence)
    return m.group(0).strip() if m else None


def detect_word_problem(sentence: str, slide_number: int,
                         extra_formula: Optional[Formula] = None) -> Optional[WordProblem]:
    sentence = sentence.strip()
    if not sentence or len(sentence) > 400:
        return None
    ask = find_ask(sentence)
    if not ask:
        return None
    ask_quantity, ask_start, ask_end = ask

    givens = find_quantities(sentence)
    # Only keep givens OUTSIDE the ask clause - a number mentioned inside the
    # ask phrase itself isn't a "known", it's noise (rare but possible).
    givens = [g for g in givens if not (ask_start <= g.start < ask_end)]
    given_names = {g.quantity_name for g in givens}
    if ask_quantity in given_names or not givens:
        return None

    all_quantities = frozenset(given_names | {ask_quantity})
    candidates = find_formulas_for(all_quantities)
    if extra_formula is not None and extra_formula.quantities == all_quantities:
        candidates = [extra_formula] + candidates
    if not candidates:
        return None

    # dedupe givens to one value per quantity name (first occurrence wins)
    seen = set()
    unique_givens = []
    for g in givens:
        if g.quantity_name in seen:
            continue
        seen.add(g.quantity_name)
        unique_givens.append(g)
    if len(unique_givens) != len(givens):
        givens = unique_givens
        given_names = {g.quantity_name for g in givens}
        all_quantities = frozenset(given_names | {ask_quantity})
        candidates = find_formulas_for(all_quantities)
        if not candidates:
            return None

    return WordProblem(
        slide_number=slide_number, sentence=sentence, givens=givens,
        ask_quantity=ask_quantity, ask_start=ask_start, ask_end=ask_end,
        formula=candidates[0], scenario=find_scenario(sentence),
    )


def detect_word_problems_in_slide(slide: dict, slide_formula: Optional[Formula] = None) -> List[WordProblem]:
    from .nlp import split_sentences
    out = []
    texts = list(slide.get("bullets") or [])
    if slide.get("notes"):
        texts.append(slide["notes"])
    for block in texts:
        for sent in split_sentences(block):
            wp = detect_word_problem(sent, slide.get("number", 0), extra_formula=slide_formula)
            if wp:
                out.append(wp)
    return out


def find_slide_formula(slide: dict) -> Optional[Formula]:
    for b in (slide.get("bullets") or []):
        f = try_parse_slide_formula(b)
        if f:
            return f
    return None
