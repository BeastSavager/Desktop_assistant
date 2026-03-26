"""
Jarvis AI Assistant — Memory Module
Short-term context (recent messages) and long-term recall via SQLite.
"""

import sqlite3
import threading
from datetime import datetime
from typing import Optional

from config import DATABASE_PATH, CONTEXT_WINDOW


class MemoryManager:
    """Thread-safe SQLite-backed conversation memory."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DATABASE_PATH
        self._local = threading.local()
        self._init_db()

    # ── connection per thread ─────────────────────────────────────────────
    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                role      TEXT    NOT NULL,
                content   TEXT    NOT NULL,
                timestamp TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                key       TEXT    NOT NULL UNIQUE,
                value     TEXT    NOT NULL,
                timestamp TEXT    NOT NULL
            )
        """)
        conn.commit()

    # ── short-term: recent conversation ───────────────────────────────────
    def add_message(self, role: str, content: str) -> None:
        """Store a conversation message (role = 'user' | 'assistant' | 'system')."""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO conversations (role, content, timestamp) VALUES (?, ?, ?)",
            (role, content, datetime.now().isoformat()),
        )
        conn.commit()

    def get_recent_messages(self, n: Optional[int] = None) -> list[dict]:
        """Return the last *n* messages as a list of {role, content} dicts."""
        n = n or CONTEXT_WINDOW
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?",
            (n,),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    # ── long-term: keyword search ─────────────────────────────────────────
    def search_memory(self, query: str, limit: int = 5) -> list[dict]:
        """Basic keyword search across all stored messages."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT role, content, timestamp FROM conversations "
            "WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        return [
            {"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]}
            for r in rows
        ]

    # ── facts / persistent knowledge ──────────────────────────────────────
    def store_fact(self, key: str, value: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO facts (key, value, timestamp) VALUES (?, ?, ?)",
            (key, value, datetime.now().isoformat()),
        )
        conn.commit()

    def get_fact(self, key: str) -> Optional[str]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT value FROM facts WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    # ── housekeeping ──────────────────────────────────────────────────────
    def clear_short_term(self) -> None:
        """Wipe conversation history (keeps facts)."""
        conn = self._get_conn()
        conn.execute("DELETE FROM conversations")
        conn.commit()

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
