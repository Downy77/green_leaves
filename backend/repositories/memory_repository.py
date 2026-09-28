from __future__ import annotations

import json
from typing import Any

from backend.core.db import db, now_iso, row_to_dict


def list_memories(q: str = "", status: str = "", kind: str = "") -> list[dict[str, Any]]:
    clauses, params = ["1=1"], []
    if q:
        clauses.append("content LIKE ?")
        params.append(f"%{q}%")
    if status:
        clauses.append("status=?")
        params.append(status)
    if kind:
        clauses.append("kind=?")
        params.append(kind)
    with db() as conn:
        rows = conn.execute(
            f"SELECT * FROM memories WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC",
            params,
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def create_memory(
    memory_id: str,
    content: str,
    kind: str = "fact",
    source_session: str = "",
) -> None:
    timestamp = now_iso()
    with db() as conn:
        conn.execute(
            "INSERT INTO memories(id,content,kind,status,source_session,versions,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (memory_id, content, kind, "confirmed", source_session, "[]", timestamp, timestamp),
        )


def update_memory(memory_id: str, content: str | None = None) -> bool:
    with db() as conn:
        old = conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
        if not old:
            return False
        versions = json.loads(old["versions"] or "[]")
        versions.append({"content": old["content"], "updated_at": old["updated_at"]})
        conn.execute(
            "UPDATE memories SET content=?, versions=?, updated_at=? WHERE id=?",
            (
                old["content"] if content is None else content,
                json.dumps(versions, ensure_ascii=False),
                now_iso(),
                memory_id,
            ),
        )
    return True


def delete_memory(memory_id: str) -> None:
    with db() as conn:
        conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))


def list_versions(memory_id: str) -> list[dict[str, Any]]:
    with db() as conn:
        row = conn.execute("SELECT versions FROM memories WHERE id=?", (memory_id,)).fetchone()
    return json.loads(row["versions"] if row else "[]")


def set_memory_status(memory_id: str, status: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE memories SET status=?, updated_at=? WHERE id=?",
            (status, now_iso(), memory_id),
        )


def list_active_memories(query: str, limit: int = 6) -> list[dict[str, Any]]:
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
