from __future__ import annotations

import secrets
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import Any, Iterable

from .config import DB_PATH


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()} if row else {}


@contextmanager
def db() -> Iterable[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT DEFAULT '体验用户',
                identity TEXT DEFAULT 'user',
                company TEXT DEFAULT '',
                department TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted INTEGER NOT NULL DEFAULT 0,
                deleted_at TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                attachments TEXT DEFAULT '[]',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'fact',
                status TEXT NOT NULL DEFAULT 'confirmed',
                source_session TEXT DEFAULT '',
                versions TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS knowledge (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'note',
                status TEXT NOT NULL DEFAULT 'ready',
                source_file TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS relations (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT '相关'
            );
            CREATE TABLE IF NOT EXISTS memos (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                remind_time TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS announcements (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """
        )
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(conversations)").fetchall()
        }
        if "deleted_at" not in columns:
            conn.execute("ALTER TABLE conversations ADD COLUMN deleted_at TEXT DEFAULT ''")
        conn.execute(
            "UPDATE conversations SET deleted_at=updated_at "
            "WHERE deleted=1 AND (deleted_at IS NULL OR deleted_at='')"
        )
        conn.execute("INSERT OR IGNORE INTO profile(id) VALUES (1)")
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES "
            "('memory_enabled','true'),('knowledge_enabled','true'),"
            "('context_enabled','true'),('api_key','')"
        )
        if conn.execute("SELECT COUNT(*) c FROM announcements").fetchone()["c"] == 0:
            conn.execute(
                "INSERT INTO announcements(id,title,content,created_at) VALUES (?,?,?,?)",
                (
                    secrets.token_hex(8),
                    "欢迎使用绿叶脉络",
                    "这是一个可部署的 AI 工作台实现。",
                    now_iso(),
                ),
            )


@asynccontextmanager
async def lifespan(_: Any):
    init_db()
    from backend.services.chat_store import init_chat_store

    init_chat_store()
    yield
