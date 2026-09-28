from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterable

from backend.core.config import CHAT_DATABASE_URL
from backend.core.db import db, now_iso, row_to_dict


def use_postgres() -> bool:
    return bool(CHAT_DATABASE_URL)


@contextmanager
def pg_db() -> Iterable[Any]:
    if not CHAT_DATABASE_URL:
        raise RuntimeError("CHAT_DATABASE_URL is not configured")
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL chat storage requires psycopg. Install requirements.txt first."
        ) from exc

    with psycopg.connect(CHAT_DATABASE_URL, row_factory=dict_row) as conn:
        yield conn


def row_to_plain_dict(row: Any) -> dict[str, Any]:
    if not row:
        return {}
    if isinstance(row, dict):
        return dict(row)
    return row_to_dict(row)


def json_dumps(value: Any) -> str:
    return json.dumps(value or [], ensure_ascii=False)


def normalize_attachments(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return value
    if not value:
        return []
    if isinstance(value, str):
        return json.loads(value or "[]")
    return list(value)


def init_chat_store() -> None:
    if not use_postgres():
        return
    with pg_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                deleted BOOLEAN NOT NULL DEFAULT FALSE,
                deleted_at TIMESTAMPTZ
            )
            """
        )
        conn.execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ")
        conn.execute(
            "UPDATE conversations SET deleted_at=updated_at "
            "WHERE deleted=TRUE AND deleted_at IS NULL"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                attachments JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_updated_at "
            "ON conversations(updated_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_deleted_updated_at "
            "ON conversations(deleted, updated_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation_created_at "
            "ON messages(conversation_id, created_at)"
        )


def conversation_exists(conversation_id: str) -> bool:
    if use_postgres():
        with pg_db() as conn:
            row = conn.execute("SELECT id FROM conversations WHERE id=%s", (conversation_id,)).fetchone()
        return bool(row)
    with db() as conn:
        row = conn.execute("SELECT id FROM conversations WHERE id=?", (conversation_id,)).fetchone()
    return bool(row)


def create_conversation(conversation_id: str, title: str) -> None:
    timestamp = now_iso()
    if use_postgres():
        with pg_db() as conn:
            conn.execute(
                "INSERT INTO conversations(id,title,created_at,updated_at) VALUES (%s,%s,%s,%s)",
                (conversation_id, title, timestamp, timestamp),
            )
        return
    with db() as conn:
        conn.execute(
            "INSERT INTO conversations(id,title,created_at,updated_at) VALUES (?,?,?,?)",
            (conversation_id, title, timestamp, timestamp),
        )


def add_message(
    message_id: str,
    conversation_id: str,
    role: str,
    content: str,
    attachments: list[dict[str, Any]] | None = None,
) -> None:
    timestamp = now_iso()
    if use_postgres():
        with pg_db() as conn:
            conn.execute(
                "INSERT INTO messages(id,conversation_id,role,content,attachments,created_at) "
                "VALUES (%s,%s,%s,%s,%s::jsonb,%s)",
                (message_id, conversation_id, role, content, json_dumps(attachments), timestamp),
            )
            current = conn.execute(
                "SELECT title FROM conversations WHERE id=%s",
                (conversation_id,),
            ).fetchone()
            if current and current["title"] == "新对话" and role == "user":
                title = content.strip().splitlines()[0][:42] or "新对话"
                conn.execute("UPDATE conversations SET title=%s WHERE id=%s", (title, conversation_id))
            conn.execute("UPDATE conversations SET updated_at=%s WHERE id=%s", (timestamp, conversation_id))
        return

    with db() as conn:
        conn.execute(
            "INSERT INTO messages(id,conversation_id,role,content,attachments,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (message_id, conversation_id, role, content, json_dumps(attachments), timestamp),
        )
        current = conn.execute("SELECT title FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        if current and current["title"] == "新对话" and role == "user":
            title = content.strip().splitlines()[0][:42] or "新对话"
            conn.execute("UPDATE conversations SET title=? WHERE id=?", (title, conversation_id))
        conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (timestamp, conversation_id))


def recent_context(conversation_id: str, limit: int = 8) -> list[dict[str, str]]:
    if use_postgres():
        with pg_db() as conn:
            rows = conn.execute(
                "SELECT role,content FROM messages WHERE conversation_id=%s "
                "ORDER BY created_at DESC LIMIT %s",
                (conversation_id, limit),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    with db() as conn:
        rows = conn.execute(
            "SELECT role,content FROM messages WHERE conversation_id=? "
            "ORDER BY created_at DESC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


def list_history(q: str = "", include_deleted: int = 0) -> list[dict[str, Any]]:
    if use_postgres():
        where = "WHERE deleted=FALSE" if not include_deleted else "WHERE TRUE"
        params: list[Any] = []
        if q:
            where += " AND title ILIKE %s"
            params.append(f"%{q}%")
        with pg_db() as conn:
            rows = conn.execute(
                "SELECT c.*, "
                "(SELECT content FROM messages m WHERE m.conversation_id=c.id "
                "ORDER BY created_at DESC LIMIT 1) preview, "
                "(SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id) message_count "
                f"FROM conversations c {where} "
                "ORDER BY updated_at DESC",
                params,
            ).fetchall()
        return [row_to_plain_dict(row) for row in rows]

    where = "WHERE deleted=0" if not include_deleted else "WHERE 1=1"
    params = []
    if q:
        where += " AND title LIKE ?"
        params.append(f"%{q}%")
    with db() as conn:
        rows = conn.execute(
            f"SELECT c.*, "
            f"(SELECT content FROM messages m WHERE m.conversation_id=c.id "
            f"ORDER BY created_at DESC LIMIT 1) preview, "
            f"(SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id) message_count "
            f"FROM conversations c {where} "
            "ORDER BY updated_at DESC",
            params,
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def get_history_detail(session_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if use_postgres():
        with pg_db() as conn:
            conversation = conn.execute("SELECT * FROM conversations WHERE id=%s", (session_id,)).fetchone()
            rows = conn.execute(
                "SELECT * FROM messages WHERE conversation_id=%s ORDER BY created_at",
                (session_id,),
            ).fetchall()
    else:
        with db() as conn:
            conversation = conn.execute("SELECT * FROM conversations WHERE id=?", (session_id,)).fetchone()
            rows = conn.execute(
                "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at",
                (session_id,),
            ).fetchall()

    messages = []
    for row in rows:
        message = row_to_plain_dict(row)
        message["attachments"] = normalize_attachments(message.get("attachments"))
        messages.append(message)
    return row_to_plain_dict(conversation), messages


def rename_history(session_id: str, title: str) -> None:
    timestamp = now_iso()
    if use_postgres():
        with pg_db() as conn:
            conn.execute(
                "UPDATE conversations SET title=%s, updated_at=%s WHERE id=%s",
                (title, timestamp, session_id),
            )
        return

    with db() as conn:
        conn.execute(
            "UPDATE conversations SET title=?, updated_at=? WHERE id=?",
            (title, timestamp, session_id),
        )


def delete_history(session_id: str, hard: int = 0) -> None:
    timestamp = now_iso()
    if use_postgres():
        with pg_db() as conn:
            if hard:
                conn.execute("DELETE FROM conversations WHERE id=%s", (session_id,))
            else:
                conn.execute(
                    "UPDATE conversations SET deleted=TRUE, deleted_at=%s WHERE id=%s",
                    (timestamp, session_id),
                )
        return

    with db() as conn:
        if hard:
            conn.execute("DELETE FROM conversations WHERE id=?", (session_id,))
        else:
            conn.execute(
                "UPDATE conversations SET deleted=1, deleted_at=? WHERE id=?",
                (timestamp, session_id),
            )


def restore_history(session_id: str) -> None:
    if use_postgres():
        with pg_db() as conn:
            conn.execute(
                "UPDATE conversations SET deleted=FALSE, deleted_at=NULL WHERE id=%s",
                (session_id,),
            )
        return

    with db() as conn:
        conn.execute("UPDATE conversations SET deleted=0, deleted_at='' WHERE id=?", (session_id,))


def list_trash() -> list[dict[str, Any]]:
    if use_postgres():
        with pg_db() as conn:
            rows = conn.execute(
                "SELECT c.*, "
                "(SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id) message_count "
                "FROM conversations c WHERE deleted=TRUE "
                "ORDER BY COALESCE(deleted_at, updated_at) DESC"
            ).fetchall()
        return [row_to_plain_dict(row) for row in rows]

    with db() as conn:
        rows = conn.execute(
            "SELECT c.*, "
            "(SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id) message_count "
            "FROM conversations c WHERE deleted=1 "
            "ORDER BY COALESCE(NULLIF(deleted_at, ''), updated_at) DESC"
        ).fetchall()
    return [row_to_dict(row) for row in rows]
