"""Persistent per-deck fingerprint store. Lives outside /mnt/user-data (which
is uploads-only) so it survives across separate generation calls for the
same deck - the actual mechanism behind "no repeating of questions"."""
from __future__ import annotations

import os
import sqlite3
from typing import List, Dict

DB_PATH = os.environ.get("QGEN_DB_PATH", os.path.join(os.path.dirname(__file__), "qgen_store.sqlite3"))


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
        row = conn.execute("SELECT COUNT(*) FROM questions WHERE deck_id=?", (deck_id,)).fetchone()
    finally:
        conn.close()
    return row[0] if row else 0
