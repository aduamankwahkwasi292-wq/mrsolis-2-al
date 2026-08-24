"""Persistent per-deck fingerprint store.

Server mode: SQLite on disk (survives across generation calls and restarts).
Browser mode (Pyodide, sys.platform == "emscripten"): in-memory dict mirrored
to localStorage so a deck's "no repeats" memory survives page reloads.
"""
from __future__ import annotations

import os
import sys
from typing import Dict, List

IN_BROWSER = sys.platform == "emscripten"

DB_PATH = os.environ.get("QGEN_DB_PATH", os.path.join(os.path.dirname(__file__), "qgen_store.sqlite3"))

# ---------------------------------------------------------------- browser mode
if IN_BROWSER:
    import json as _json

    _LS_KEY = "qgen_store"
    _MEM: Dict[str, List[Dict]] = {}

    def _ls_get() -> str:
        from js import localStorage
        return localStorage.getItem(_LS_KEY) or ""

    def _ls_set(raw: str) -> None:
        from js import localStorage
        localStorage.setItem(_LS_KEY, raw)

    def _load():
        try:
            raw = _ls_get()
            if raw:
                data = _json.loads(raw)
                for deck_id, rows in data.items():
                    _MEM[deck_id] = [
                        {"hash": r[0], "fact_key": r[1] or "", "text": r[2]} for r in rows
                    ]
        except Exception:
            pass  # localStorage blocked/unavailable -> session-only memory

    def _save():
        try:
            payload = {
                k: [[r["hash"], r["fact_key"], r["text"]] for r in rows]
                for k, rows in _MEM.items()
            }
            _ls_set(_json.dumps(payload))
        except Exception:
            pass  # never let persistence break generation

    _load()

    def get_existing(deck_id: str) -> List[Dict]:
        return list(_MEM.get(deck_id, []))

    def register(deck_id: str, question_hash: str, fact_key: str, question_text: str) -> None:
        rows = _MEM.setdefault(deck_id, [])
        if any(r["hash"] == question_hash for r in rows):
            return
        rows.append({"hash": question_hash, "fact_key": fact_key or "", "text": question_text})
        _save()

    def clear_deck(deck_id: str) -> None:
        _MEM.pop(deck_id, None)
        _save()

    def count_for_deck(deck_id: str) -> int:
        return len(_MEM.get(deck_id, []))

# ---------------------------------------------------------------- server mode
else:
    import sqlite3

    def _conn():
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS questions (
                deck_id TEXT NOT NULL,
                question_hash TEXT NOT NULL,
                fact_key TEXT,
                question_text TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (deck_id, question_hash)
            )"""
        )
        return conn

    def get_existing(deck_id: str) -> List[Dict]:
        conn = _conn()
        try:
            rows = conn.execute(
                "SELECT question_hash, fact_key, question_text FROM questions WHERE deck_id=?",
                (deck_id,),
            ).fetchall()
        finally:
            conn.close()
        return [{"hash": r[0], "fact_key": r[1] or "", "text": r[2]} for r in rows]

    def register(deck_id: str, question_hash: str, fact_key: str, question_text: str) -> None:
        conn = _conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO questions (deck_id, question_hash, fact_key, question_text) "
                "VALUES (?, ?, ?, ?)",
                (deck_id, question_hash, fact_key, question_text),
            )
            conn.commit()
        finally:
            conn.close()

    def clear_deck(deck_id: str) -> None:
        conn = _conn()
        try:
            conn.execute("DELETE FROM questions WHERE deck_id=?", (deck_id,))
            conn.commit()
        finally:
            conn.close()

    def count_for_deck(deck_id: str) -> int:
        conn = _conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM questions WHERE deck_id=?", (deck_id,)
            ).fetchone()
        finally:
            conn.close()
        return int(row[0]) if row else 0
