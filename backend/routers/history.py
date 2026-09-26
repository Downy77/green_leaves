from __future__ import annotations
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.services import chat_store

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history")
def history(q: str = "", include_deleted: int = 0) -> dict[str, Any]:
    return {"items": chat_store.list_history(q=q, include_deleted=include_deleted)}


@router.get("/history/{session_id}")
def history_detail(session_id: str) -> dict[str, Any]:
    conversation, messages = chat_store.get_history_detail(session_id)
    if not conversation:
        raise HTTPException(404, "会话不存在")
    return {"conversation": conversation, "messages": messages}


@router.patch("/history/{session_id}")
async def rename_history(session_id: str, request: Request) -> dict[str, Any]:
    payload = await request.json()
    chat_store.rename_history(session_id, payload.get("title", "未命名会话"))
    return {"ok": True}


@router.delete("/history/{session_id}")
def delete_history(session_id: str, hard: int = 0) -> dict[str, Any]:
    chat_store.delete_history(session_id, hard=hard)
    return {"ok": True}


@router.post("/history/{session_id}/restore")
def restore_history(session_id: str) -> dict[str, Any]:
    chat_store.restore_history(session_id)
    return {"ok": True}


@router.get("/trash")
def trash() -> dict[str, Any]:
    return {"items": chat_store.list_trash()}
