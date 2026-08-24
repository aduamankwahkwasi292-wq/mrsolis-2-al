"""Three layers of no-repeat guarantee:
1. Exact hash of normalized question text.
2. Fact-level - one question per underlying fact by default.
3. TF-IDF cosine similarity - catches paraphrases of the same question.
All persisted per-deck in SQLite so re-generating later still won't repeat.
"""
from __future__ import annotations

import hashlib
import re
from typing import List, Optional

from . import store


def normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def question_hash(text: str) -> str:
    return hashlib.sha1(normalize(text).encode()).hexdigest()[:24]


class DedupFilter:
    def __init__(self, deck_id: str, near_dup_threshold: Optional[float] = 0.86):
        self.deck_id = deck_id
        self.threshold = near_dup_threshold
        existing = store.get_existing(deck_id)
        self.seen_hashes = {e["hash"] for e in existing}
        self.seen_fact_keys = {e["fact_key"] for e in existing if e["fact_key"]}
        self.seen_texts: List[str] = [e["text"] for e in existing if e["text"]]
        self._vec: Optional[TfidfVectorizer] = None
        self._matrix = None
        self._rebuild()

    def _rebuild(self):
        if self.threshold is not None and len(self.seen_texts) >= 2:
            # Imported lazily: the near-dup layer is off in production
            # (pipeline passes threshold=None), and a hard top-level import
            # would drag scikit-learn/scipy into every environment, including
            # browser (Pyodide) builds that don't ship sklearn at all.
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            self._vec = TfidfVectorizer(stop_words="english")
            self._matrix = self._vec.fit_transform(self.seen_texts)
        else:
            self._vec = None
            self._matrix = None

    def is_duplicate(self, text: str, fact_key: Optional[str] = None,
                      allow_multiple_per_fact: bool = False) -> bool:
        h = question_hash(text)
        if h in self.seen_hashes:
            return True
        if fact_key and not allow_multiple_per_fact and fact_key in self.seen_fact_keys:
            return True
        if self.threshold is not None and self._vec is not None:
            try:
                vec = self._vec.transform([text])
                sims = cosine_similarity(vec, self._matrix)[0]
                if len(sims) and sims.max() >= self.threshold:
                    return True
            except ValueError:
                pass
        return False

    def register(self, text: str, fact_key: Optional[str] = None):
        h = question_hash(text)
        self.seen_hashes.add(h)
        if fact_key:
            self.seen_fact_keys.add(fact_key)
        self.seen_texts.append(text)
        store.register(self.deck_id, h, fact_key or "", text)
        if self.threshold is not None and (len(self.seen_texts) % 8 == 0 or self._vec is None):
            self._rebuild()
