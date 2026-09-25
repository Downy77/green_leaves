from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from backend.core.db import db, now_iso, row_to_dict
from backend.services.storage import save_upload

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/graph")
def knowledge_graph() -> dict[str, Any]:
    with db() as conn:
        nodes = [
            row_to_dict(row)
            for row in conn.execute(
                "SELECT * FROM knowledge WHERE status!='archived' ORDER BY updated_at DESC"
            ).fetchall()
        ]
        edges = [
            row_to_dict(row)
            for row in conn.execute("SELECT * FROM relations").fetchall()
        ]
    return {"nodes": nodes, "edges": edges}


@router.get("/sources")
def knowledge_sources() -> dict[str, Any]:
    return knowledge_graph()


@router.post("/sources")
async def knowledge_upload(files: list[UploadFile] = File(default=[])) -> dict[str, Any]:
    created: list[dict[str, Any]] = []
    with db() as conn:
        for file in files:
            metadata = save_upload(file)
            knowledge_id = secrets.token_hex(10)
            timestamp = now_iso()
            content = metadata.get("preview") or (
                f"原始文件：{metadata['original_name']}，大小 {metadata['size']} bytes。"
            )
            conn.execute(
                "INSERT INTO knowledge(id,title,content,kind,source_file,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    knowledge_id,
                    metadata["original_name"],
                    content,
                    "file",
                    metadata["stored_name"],
                    timestamp,
                    timestamp,
                ),
            )
            created.append({"id": knowledge_id, **metadata})
    return {"ok": True, "items": created}


@router.post("/sources/text")
async def knowledge_text(request: Request) -> dict[str, str]:
    payload = await request.json()
    knowledge_id = secrets.token_hex(10)
    timestamp = now_iso()
    with db() as conn:
        conn.execute(
            "INSERT INTO knowledge(id,title,content,kind,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (
                knowledge_id,
                payload.get("title", "未命名知识"),
                payload.get("text", ""),
                "text",
                timestamp,
                timestamp,
            ),
        )
    return {"id": knowledge_id, "status": "ready"}


@router.get("/search")
def knowledge_search(q: str = "") -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM knowledge WHERE status!='archived' "
            "AND (title LIKE ? OR content LIKE ?) ORDER BY updated_at DESC",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
    return {"items": [{"note_id": row["id"], **row_to_dict(row)} for row in rows]}


@router.get("/notes/{note_id}")
def knowledge_note(note_id: str) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute("SELECT * FROM knowledge WHERE id=?", (note_id,)).fetchone()
    if not row:
        raise HTTPException(404, "知识不存在")
    return row_to_dict(row)


@router.patch("/notes/{note_id}")
async def knowledge_note_patch(note_id: str, request: Request) -> dict[str, str]:
    payload = await request.json()
    with db() as conn:
        conn.execute(
            "UPDATE knowledge SET title=?, content=?, updated_at=? WHERE id=?",
            (
                payload.get("title", "未命名知识"),
                payload.get("content", ""),
                now_iso(),
                note_id,
            ),
        )
    return {"id": note_id}


@router.delete("/notes/{note_id}")
def knowledge_note_delete(note_id: str) -> dict[str, bool]:
    with db() as conn:
        conn.execute(
            "UPDATE knowledge SET status='archived', updated_at=? WHERE id=?",
            (now_iso(), note_id),
        )
    return {"ok": True}


@router.post("/relations")
async def knowledge_relation(request: Request) -> dict[str, str]:
    payload = await request.json()
    relation_id = secrets.token_hex(10)
    with db() as conn:
        conn.execute(
            "INSERT INTO relations(id,source_id,target_id,type) VALUES (?,?,?,?)",
            (
                relation_id,
                payload.get("source_id"),
                payload.get("target_id"),
                payload.get("type", "相关"),
            ),
        )
    return {"id": relation_id}
