"""
Core NLP utilities: model loading + a fragment-safe parser.

Slide bullets are frequently NOT full sentences ("Reduces cost by 20%",
"Improves scalability across distributed systems"). Fed raw into a
statistical dependency parser, verb-initial fragments like "Reduces cost..."
get silently mis-tagged (the parser expects a subject, so it reinterprets
the leading verb as a noun subject and the following noun as the verb).
That corrupts every downstream step, so we detect this pattern and repair
it by parsing with a synthetic subject, then remembering that the subject
was synthetic so we never quiz on it directly.
"""
from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from typing import Optional

import spacy
from spacy.tokens import Doc, Span, Token

_MODEL_NAME = "en_core_web_sm"

# Common slide-bullet action verbs that start headless fragments. Curated
# rather than inferred, because relying on the parser's own tag here is
# circular -- it's precisely the tag we can't trust yet.
_BARE_ACTION_VERBS = {
    "reduces", "reduce", "improves", "improve", "increases", "increase",
    "decreases", "decrease", "enables", "enable", "supports", "support",
    "provides", "provide", "delivers", "deliver", "ensures", "ensure",
    "allows", "allow", "includes", "include", "requires", "require",
    "uses", "use", "creates", "create", "generates", "generate",
    "offers", "offer", "features", "feature", "integrates", "integrate",
    "streamlines", "streamline", "enhances", "enhance", "minimizes", "minimize",
    "maximizes", "maximize", "eliminates", "eliminate", "simplifies", "simplify",
    "automates", "automate", "optimizes", "optimize", "prevents", "prevent",
    "boosts", "boost", "drives", "drive", "powers", "power", "unlocks", "unlock",
    "facilitates", "facilitate", "handles", "handle", "manages", "manage",
    "processes", "process", "stores", "store", "tracks", "track", "monitors",
    "monitor", "validates", "validate", "protects", "protect", "encrypts",
    "encrypt", "compresses", "compress", "caches", "cache", "scales", "scale",
    "solves", "solve", "prevents", "removes", "remove", "avoids", "avoid",
    "detects", "detect", "identifies", "identify", "combines", "combine",
    "replaces", "replace", "extends", "extend", "accelerates", "accelerate",
    "guarantees", "guarantee", "maintains", "maintain", "captures", "capture",
}

# Imperative-mood bullets ("Use a voltmeter to...", "Verify the circuit is
# de-energized") make fine list items but awkward SVO facts once a title is
# substituted in as a synthetic subject (it personifies the title as an
# agent performing the instruction). These are routed to the list-fact
# pathway only rather than forced through subject-verb-object extraction.
IMPERATIVE_VERBS = {
    "use", "check", "verify", "ensure", "confirm", "determine", "select",
    "choose", "avoid", "follow", "refer", "note", "remember", "complete",
    "perform", "apply", "install", "connect", "disconnect", "turn", "press",
    "click", "enable", "disable", "set", "configure", "review", "read",
    "identify", "locate", "measure", "test", "inspect", "calculate",
    "record", "observe", "compare", "safely", "always", "never", "make",
    "take", "place", "remove", "attach", "adjust", "calibrate", "explain",
    "describe", "discuss", "state", "list", "define", "summarize", "outline",
    "demonstrate", "illustrate", "justify", "analyze", "evaluate", "draw",
    "sketch", "label", "show", "find", "solve", "calculate",
}

GENERIC_TITLE_STOPLIST = {
    "benefits", "features", "advantages", "overview", "summary", "agenda",
    "introduction", "key points", "highlights", "key features", "key benefits",
    "conclusion", "takeaways", "key takeaways", "pros and cons", "results",
    "findings", "outline", "recap", "next steps", "questions", "thank you",
    "goals", "objectives", "background",
}


@functools.lru_cache(maxsize=1)
def get_nlp():
    return spacy.load(_MODEL_NAME)


@dataclass
class ParsedUnit:
    doc: Doc
    root: Token
    subject: Optional[Token]
    subject_is_synthetic: bool
    source_text: str  # the original, un-repaired text (for display/dedup)


def _looks_headless(doc: Doc) -> bool:
    """True if this looks like a subjectless slide-bullet fragment."""
    if len(doc) == 0:
        return False
    first = doc[0]
    if first.lemma_.lower() in _BARE_ACTION_VERBS or first.text.lower() in _BARE_ACTION_VERBS:
        return True
    roots = [t for t in doc if t.dep_ == "ROOT"]
    if roots and not any(c.dep_ in ("nsubj", "nsubjpass") for c in roots[0].children):
        # No subject attached to the root at all -> likely a fragment,
        # imperative, or gerund-headed bullet ("Improving throughput via...").
        # VERB/AUX roots without a subject are the risky case; a bare NOUN
        # root ("Zero-copy networking") is a label, not a fact - leave it
        # for the structural list extractor instead of forcing an SVO read.
        return roots[0].pos_ in ("VERB", "AUX")
    return False


def parse_slide_text(text: str) -> ParsedUnit:
    """Parse a sentence/bullet, repairing subjectless fragments."""
    nlp = get_nlp()
    text = text.strip()
    doc = nlp(text)

    if _looks_headless(doc):
        synthetic = "It " + text[0].lower() + text[1:]
        if not synthetic.endswith((".", "!", "?")):
            synthetic += "."
        repaired = nlp(synthetic)
        root = next((t for t in repaired if t.dep_ == "ROOT"), None)
        subj = next((c for c in root.children if c.dep_ in ("nsubj", "nsubjpass")), None) if root else None
        return ParsedUnit(doc=repaired, root=root, subject=subj,
                           subject_is_synthetic=True, source_text=text)

    root = next((t for t in doc if t.dep_ == "ROOT"), None)
    subj = next((c for c in root.children if c.dep_ in ("nsubj", "nsubjpass")), None) if root else None
    return ParsedUnit(doc=doc, root=root, subject=subj,
                       subject_is_synthetic=False, source_text=text)


def title_as_subject_phrase(title: Optional[str]) -> Optional[str]:
    """Turn a slide title into a usable subject NP, or None if unusable."""
    if not title:
        return None
    norm = title.strip().lower().rstrip(":").strip()
    if not norm or norm in GENERIC_TITLE_STOPLIST:
        return None
    nlp = get_nlp()
    doc = nlp(title)
    if not any(t.pos_ in ("NOUN", "PROPN") for t in doc):
        return None
    if title.strip().endswith("?"):
        return None
    cleaned = title.strip().rstrip(":").strip()
    if cleaned.split()[0].lower() in ("the", "a", "an"):
        return cleaned
    return "the " + cleaned


def split_sentences(text: str):
    nlp = get_nlp()
    doc = nlp(text)
    return [s.text.strip() for s in doc.sents if s.text.strip()]
