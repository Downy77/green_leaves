from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.repositories import memory_repository
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
    return {
        "enabled": get_setting("memory_enabled", "true") == "true",
        "memories": memory_repository.list_memories(q=q, status=status, kind=kind),
    }


@router.post("/memories")
async def memory_create(request: Request) -> dict[str, str]:
    payload = await request.json()
    memory_id = secrets.token_hex(10)
    memory_repository.create_memory(
        memory_id,
        payload.get("content", ""),
        payload.get("kind", "fact"),
        payload.get("source_session", ""),
    )
    return {"id": memory_id}


@router.patch("/memories/{memory_id}")
async def memory_patch(memory_id: str, request: Request) -> dict[str, bool]:
    payload = await request.json()
    if not memory_repository.update_memory(memory_id, payload.get("content")):
        raise HTTPException(404, "记忆不存在")
    return {"ok": True}


@router.delete("/memories/{memory_id}")
def memory_delete(memory_id: str) -> dict[str, bool]:
    memory_repository.delete_memory(memory_id)
    return {"ok": True}


@router.get("/memories/{memory_id}/versions")
def memory_versions(memory_id: str) -> dict[str, Any]:
    return {"versions": memory_repository.list_versions(memory_id)}


@router.post("/memories/{memory_id}/{action}")
def memory_action(memory_id: str, action: str) -> dict[str, bool]:
    status = {"confirm": "confirmed", "archive": "archived", "restore": "confirmed"}.get(action)
    if not status:
        raise HTTPException(400, "未知操作")
    memory_repository.set_memory_status(memory_id, status)
    return {"ok": True}
