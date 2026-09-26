from __future__ import annotations

import json
import secrets
import shutil
import time
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from backend.core.config import UPLOAD_DIR
from backend.core.db import db, now_iso, row_to_dict


def get_setting(key: str, default: str = "") -> str:
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with db() as conn:
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)", (key, value))


def ensure_conversation(session_id: str | None, title: str = "新对话") -> str:
    conversation_id = session_id or secrets.token_hex(12)
    with db() as conn:
        if not conn.execute("SELECT id FROM conversations WHERE id=?", (conversation_id,)).fetchone():
            timestamp = now_iso()
            conn.execute(
                "INSERT INTO conversations(id,title,created_at,updated_at) VALUES (?,?,?,?)",
                (conversation_id, title, timestamp, timestamp),
            )
    return conversation_id


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    attachments: list[dict[str, Any]] | None = None,
) -> str:
    message_id = secrets.token_hex(12)
    with db() as conn:
        timestamp = now_iso()
        conn.execute(
            "INSERT INTO messages(id,conversation_id,role,content,attachments,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (
                message_id,
                conversation_id,
                role,
                content,
                json.dumps(attachments or [], ensure_ascii=False),
                timestamp,
            ),
        )
        current = conn.execute(
            "SELECT title FROM conversations WHERE id=?", (conversation_id,)
        ).fetchone()
        if current and current["title"] == "新对话" and role == "user":
            title = content.strip().splitlines()[0][:42] or "新对话"
            conn.execute(
                "UPDATE conversations SET title=? WHERE id=?", (title, conversation_id)
            )
        conn.execute(
            "UPDATE conversations SET updated_at=? WHERE id=?",
            (timestamp, conversation_id),
        )
    return message_id


def recent_context(conversation_id: str, limit: int = 8) -> list[dict[str, str]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT role,content FROM messages WHERE conversation_id=? "
            "ORDER BY created_at DESC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


def save_upload(file: UploadFile) -> dict[str, Any]:
    safe_name = Path(file.filename or "upload.bin").name
    stored_name = f"{int(time.time())}_{secrets.token_hex(5)}_{safe_name}"
    target = UPLOAD_DIR / stored_name
    with target.open("wb") as output:
        shutil.copyfileobj(file.file, output)

    preview = ""
    if target.suffix.lower() in {".txt", ".md", ".csv", ".json", ".py", ".js", ".html", ".css"}:
        preview = target.read_text(encoding="utf-8", errors="ignore")[:4000]
    return {
        "original_name": safe_name,
        "stored_name": stored_name,
        "size": target.stat().st_size,
        "content_type": file.content_type or "application/octet-stream",
        "preview": preview,
    }


class SQLiteAgentStore:
    """Storage adapter consumed by the LangGraph runtime."""

    def setting(self, key: str, default: str = "") -> str:
        return get_setting(key, default)

    def recent_context(self, conversation_id: str, limit: int = 8) -> list[dict[str, str]]:
        return recent_context(conversation_id, limit)

    def search_knowledge(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        query = query.strip()
        with db() as conn:
            if not query:
                rows = conn.execute(
                    "SELECT * FROM knowledge WHERE status!='archived' "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM knowledge WHERE status!='archived' "
                    "AND (title LIKE ? OR content LIKE ?) "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (f"%{query}%", f"%{query}%", limit),
                ).fetchall()
        return [row_to_dict(row) for row in rows]

    def active_memories(self, query: str, limit: int = 6) -> list[dict[str, Any]]:
        query = query.strip()
        with db() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE status='confirmed' "
                "AND (content LIKE ? OR ?='') ORDER BY updated_at DESC LIMIT ?",
                (f"%{query}%", query, limit),
            ).fetchall()
            if query and not rows:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE status='confirmed' "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [row_to_dict(row) for row in rows]
