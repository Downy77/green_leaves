from __future__ import annotations

import json
import secrets
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.core.db import db, now_iso, row_to_dict
from backend.services.storage import get_setting, set_setting

router = APIRouter(prefix="/api", tags=["memory"])


@router.get("/memory/settings")
def memory_settings() -> dict[str, bool]:
    return {"enabled": get_setting("memory_enabled", "true") == "true"}


@router.put("/memory/settings")
async def memory_settings_put(request: Request) -> dict[str, bool]:
    payload = await request.json()
    enabled = bool(payload.get("enabled"))
    set_setting("memory_enabled", "true" if enabled else "false")
    return {"enabled": enabled}


@router.get("/memories")
def memories(q: str = "", status: str = "", kind: str = "") -> dict[str, Any]:
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
    return {
        "enabled": get_setting("memory_enabled", "true") == "true",
        "memories": [row_to_dict(row) for row in rows],
    }


@router.post("/memories")
async def memory_create(request: Request) -> dict[str, str]:
    payload = await request.json()
    memory_id = secrets.token_hex(10)
    timestamp = now_iso()
    with db() as conn:
        conn.execute(
            "INSERT INTO memories(id,content,kind,status,source_session,versions,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                memory_id,
                payload.get("content", ""),
                payload.get("kind", "fact"),
                "confirmed",
                payload.get("source_session", ""),
                "[]",
                timestamp,
                timestamp,
            ),
        )
    return {"id": memory_id}


@router.patch("/memories/{memory_id}")
async def memory_patch(memory_id: str, request: Request) -> dict[str, bool]:
    payload = await request.json()
    with db() as conn:
        old = conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
        if not old:
            raise HTTPException(404, "记忆不存在")
        versions = json.loads(old["versions"] or "[]")
        versions.append({"content": old["content"], "updated_at": old["updated_at"]})
        conn.execute(
            "UPDATE memories SET content=?, versions=?, updated_at=? WHERE id=?",
            (
                payload.get("content", old["content"]),
                json.dumps(versions, ensure_ascii=False),
                now_iso(),
                memory_id,
            ),
        )
    return {"ok": True}


@router.delete("/memories/{memory_id}")
def memory_delete(memory_id: str) -> dict[str, bool]:
    with db() as conn:
        conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
    return {"ok": True}


@router.get("/memories/{memory_id}/versions")
def memory_versions(memory_id: str) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            "SELECT versions FROM memories WHERE id=?", (memory_id,)
        ).fetchone()
    return {"versions": json.loads(row["versions"] if row else "[]")}


@router.post("/memories/{memory_id}/{action}")
def memory_action(memory_id: str, action: str) -> dict[str, bool]:
    status = {"confirm": "confirmed", "archive": "archived", "restore": "confirmed"}.get(action)
    if not status:
        raise HTTPException(400, "未知操作")
    with db() as conn:
        conn.execute(
            "UPDATE memories SET status=?, updated_at=? WHERE id=?",
            (status, now_iso(), memory_id),
        )
    return {"ok": True}
