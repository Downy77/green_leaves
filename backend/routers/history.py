from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.core.db import db, now_iso, row_to_dict

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history")
def history(q: str = "", include_deleted: int = 0) -> dict[str, Any]:
    where = "WHERE deleted=0" if not include_deleted else "WHERE 1=1"
    params: list[Any] = []
    if q:
        where += " AND title LIKE ?"
        params.append(f"%{q}%")
    with db() as conn:
        rows = conn.execute(
            f"SELECT c.*, (SELECT content FROM messages m WHERE m.conversation_id=c.id "
            f"ORDER BY created_at DESC LIMIT 1) preview FROM conversations c {where} "
            "ORDER BY updated_at DESC",
            params,
        ).fetchall()
    return {"items": [row_to_dict(row) for row in rows]}


@router.get("/history/{session_id}")
def history_detail(session_id: str) -> dict[str, Any]:
    with db() as conn:
        conversation = conn.execute(
            "SELECT * FROM conversations WHERE id=?", (session_id,)
        ).fetchone()
        if not conversation:
            raise HTTPException(404, "会话不存在")
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at",
            (session_id,),
        ).fetchall()
    messages = []
    for row in rows:
        message = row_to_dict(row)
        message["attachments"] = json.loads(message.get("attachments") or "[]")
        messages.append(message)
    return {"conversation": row_to_dict(conversation), "messages": messages}


@router.patch("/history/{session_id}")
async def rename_history(session_id: str, request: Request) -> dict[str, Any]:
    payload = await request.json()
    with db() as conn:
        conn.execute(
            "UPDATE conversations SET title=?, updated_at=? WHERE id=?",
            (payload.get("title", "未命名会话"), now_iso(), session_id),
        )
    return {"ok": True}


@router.delete("/history/{session_id}")
def delete_history(session_id: str, hard: int = 0) -> dict[str, Any]:
    with db() as conn:
        if hard:
            conn.execute("DELETE FROM conversations WHERE id=?", (session_id,))
        else:
            conn.execute(
                "UPDATE conversations SET deleted=1, updated_at=? WHERE id=?",
                (now_iso(), session_id),
            )
    return {"ok": True}


@router.post("/history/{session_id}/restore")
def restore_history(session_id: str) -> dict[str, Any]:
    with db() as conn:
        conn.execute(
            "UPDATE conversations SET deleted=0, updated_at=? WHERE id=?",
            (now_iso(), session_id),
        )
    return {"ok": True}


@router.get("/trash")
def trash() -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE deleted=1 ORDER BY updated_at DESC"
        ).fetchall()
    return {"items": [row_to_dict(row) for row in rows]}
