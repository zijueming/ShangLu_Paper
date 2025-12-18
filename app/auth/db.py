from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable


def db_path(base_output_dir: Path) -> Path:
    base_output_dir = (base_output_dir or Path(".")).resolve()
    return base_output_dir / "_db" / "app.db"


def connect(base_output_dir: Path) -> sqlite3.Connection:
    path = db_path(base_output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def _exec_many(conn: sqlite3.Connection, stmts: Iterable[str]) -> None:
    for stmt in stmts:
        conn.execute(stmt)


def init_db(conn: sqlite3.Connection) -> None:
    _exec_many(
        conn,
        [
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              is_admin INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS invite_codes (
              code TEXT PRIMARY KEY,
              max_uses INTEGER NOT NULL DEFAULT 1,
              uses INTEGER NOT NULL DEFAULT 0,
              disabled INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              created_by INTEGER,
              FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS invite_uses (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              code TEXT NOT NULL,
              user_id INTEGER NOT NULL,
              used_at TEXT NOT NULL,
              FOREIGN KEY(code) REFERENCES invite_codes(code) ON DELETE CASCADE,
              FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS sessions (
              token TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              last_seen_at TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_invite_uses_code ON invite_uses(code)",
            "CREATE INDEX IF NOT EXISTS idx_invite_uses_user_id ON invite_uses(user_id)",
        ],
    )
    conn.commit()

