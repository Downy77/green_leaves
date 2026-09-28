from __future__ import annotations

from backend.core.db import db


def get_setting(key: str, default: str = "") -> str:
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with db() as conn:
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)", (key, value))
