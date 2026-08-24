"""Deterministic post-transformation cleanup. Not a full grammar checker -
just fixes the specific artifacts our own transformations can introduce,
and refuses (returns None) anything that looks like a construction bug
rather than emitting broken-looking output."""
from __future__ import annotations

import re
from typing import Optional

_VOWEL_SOUND = re.compile(r"^(hour|honest|honor|honou?r|heir|mba|mri|fbi|ic\b|x-ray|xray|sos)", re.I)
_CONSONANT_SOUND = re.compile(
    r"^(uni(?!corn)|use|user|usu|utili|europ|one\b|once\b|ubiqu)", re.I
)


def article_for(word: str) -> str:
    w = word.strip("\"'()")
    if not w:
        return "a"
    if _VOWEL_SOUND.match(w):
        return "an"
    if _CONSONANT_SOUND.match(w):
        return "a"
    return "an" if w[0].lower() in "aeiou" else "a"


def fix_articles(text: str) -> str:
    def repl(m):
        art, word = m.group(1), m.group(2)
        correct = article_for(word)
        if art[0].isupper():
            correct = correct.capitalize()
        return f"{correct} {word}"

    return re.sub(r"\b([Aa]n?)\s+(\S+)", repl, text)


def polish(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = re.sub(r"\s+", " ", text).strip()
    t = t.rstrip(" .!,;:?")
    if not t:
        return None

    words = t.split()
    if len(words) < 3 or len(words) > 28:
        return None
    # Consecutive duplicate word = signature of a construction bug (e.g. a
    # stray re-insertion of the root verb). Refuse rather than ship it.
    for i in range(1, len(words)):
        if words[i].lower() == words[i - 1].lower() and words[i].isalpha() and len(words[i]) > 2:
            return None

    t = fix_articles(t)
    t = t[0].upper() + t[1:]
    if t.count("(") != t.count(")"):
        return None
    if re.search(r"[.,;:]\s*\)", t):
        return None
    return t + "?"


def clean_answer(text: str) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    t = t.strip(" .,;:")
    return t
