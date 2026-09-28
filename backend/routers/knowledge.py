from __future__ import annotations

import logging
import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from backend.core.config import UPLOAD_DIR
from backend.repositories import knowledge_repository
from backend.services.knowledge_documents import MAX_EXTRACTED_CHARS, extract_text
from backend.services.knowledge_search import search_knowledge
from backend.services.knowledge_vectors import delete_note, enabled, index_note
from backend.services.storage import save_upload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _index_saved_note(note_id: str, content: str) -> tuple[str, int]:
    if not enabled():
        status, count = "disabled", 0
    else:
        try:
            count = index_note(note_id, content)
            status = "ready"
        except Exception:
            logger.exception("Knowledge indexing failed for %s", note_id)
            try:
                delete_note(note_id)
            except Exception:
                logger.exception("Could not remove stale vectors for %s", note_id)
            status, count = "failed", 0
    knowledge_repository.update_index_status(note_id, status)
    return status, count


@router.get("/graph")
def knowledge_graph() -> dict[str, Any]:
    nodes, edges = knowledge_repository.list_graph()
    return {"nodes": nodes, "edges": edges}


@router.get("/sources")
def knowledge_sources() -> dict[str, Any]:
    return knowledge_graph()


def _store_file(file: UploadFile) -> tuple[dict[str, Any], str]:
    metadata = save_upload(file)
    path = UPLOAD_DIR / metadata["stored_name"]
    try:
        if metadata["size"] > 20 * 1024 * 1024:
            raise ValueError("单个文件不能超过 20 MB")
        content = extract_text(path)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return metadata, content


@router.post("/sources")
async def knowledge_upload(files: list[UploadFile] = File(default=[])) -> dict[str, Any]:
    created: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for file in files:
        try:
            metadata, content = await run_in_threadpool(_store_file, file)
        except (ValueError, OSError) as exc:
            errors.append({"file": file.filename or "文件", "error": str(exc)})
            continue
        except Exception:
            logger.exception("Unable to parse knowledge file %s", file.filename)
            errors.append({"file": file.filename or "文件", "error": "文件解析失败"})
            continue
        knowledge_id = secrets.token_hex(10)
        knowledge_repository.create_note(
            knowledge_id,
            metadata["original_name"],
            content,
            "file",
            metadata["stored_name"],
        )
        index_status, chunk_count = await run_in_threadpool(_index_saved_note, knowledge_id, content)
        created.append({"id": knowledge_id, **metadata, "index_status": index_status, "chunk_count": chunk_count})
    return {"ok": not errors, "items": created, "errors": errors}


@router.post("/sources/text")
async def knowledge_text(request: Request) -> dict[str, Any]:
    payload = await request.json()
    title = str(payload.get("title") or "未命名知识").strip()[:200]
    content = str(payload.get("text") or "").strip()
    if not content:
        raise HTTPException(422, "知识内容不能为空")
    if len(content) > MAX_EXTRACTED_CHARS:
        raise HTTPException(413, "知识内容过长")
    knowledge_id = secrets.token_hex(10)
    knowledge_repository.create_note(knowledge_id, title, content, "text")
    index_status, chunk_count = await run_in_threadpool(_index_saved_note, knowledge_id, content)
    return {"id": knowledge_id, "status": "ready", "index_status": index_status, "chunk_count": chunk_count}


@router.get("/search")
def knowledge_search(q: str = "") -> dict[str, Any]:
    return {"items": [{"note_id": item["id"], **item} for item in search_knowledge(q, limit=20)]}


@router.get("/notes/{note_id}")
def knowledge_note(note_id: str) -> dict[str, Any]:
    note = knowledge_repository.get_active_note(note_id)
    if not note:
        raise HTTPException(404, "知识不存在")
    return note


@router.get("/notes/{note_id}/download")
def knowledge_download(note_id: str) -> FileResponse:
    note = knowledge_note(note_id)
    if not note["source_file"]:
        raise HTTPException(404, "该知识没有原始文件")
    path = UPLOAD_DIR / Path(note["source_file"]).name
    if not path.is_file():
        raise HTTPException(404, "原始文件不存在")
    return FileResponse(path, filename=note["title"])


@router.patch("/notes/{note_id}")
async def knowledge_note_patch(note_id: str, request: Request) -> dict[str, Any]:
    payload = await request.json()
    old = knowledge_note(note_id)
    title = str(payload.get("title", old["title"])).strip()[:200]
    content = str(payload.get("content", old["content"])).strip()
    if not title or not content:
        raise HTTPException(422, "标题和内容不能为空")
    if len(content) > MAX_EXTRACTED_CHARS:
        raise HTTPException(413, "知识内容过长")
    changed = content != old["content"]
    knowledge_repository.update_note(
        note_id,
        title,
        content,
        "pending" if changed else old["index_status"],
    )
    index_status = (
        (await run_in_threadpool(_index_saved_note, note_id, content))[0]
        if changed else old["index_status"]
    )
    return {"id": note_id, "index_status": index_status}


@router.delete("/notes/{note_id}")
async def knowledge_note_delete(note_id: str) -> dict[str, bool]:
    knowledge_note(note_id)
    knowledge_repository.archive_note(note_id)
    try:
        await run_in_threadpool(delete_note, note_id)
    except Exception:
        logger.exception("Could not remove archived vectors for %s", note_id)
    return {"ok": True}


@router.post("/relations")
async def knowledge_relation(request: Request) -> dict[str, str]:
    payload = await request.json()
    source_id, target_id = str(payload.get("source_id") or ""), str(payload.get("target_id") or "")
    if not source_id or not target_id or source_id == target_id:
        raise HTTPException(422, "请选择两个不同的知识节点")
    relation_id = knowledge_repository.create_relation(
        source_id,
        target_id,
        secrets.token_hex(10),
        str(payload.get("type") or "相关")[:40],
    )
    if not relation_id:
        raise HTTPException(404, "关联的知识节点不存在")
    return {"id": relation_id}
