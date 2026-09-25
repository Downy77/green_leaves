from __future__ import annotations

import os
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from backend.core.config import BASE_DIR, DATA_DIR, UPLOAD_DIR
from backend.core.db import db, row_to_dict
from backend.services.storage import get_setting, recent_context

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/agent/status", tags=["agent"])
def agent_status() -> dict[str, Any]:
    return {
        "framework": "langgraph",
        "model_provider": "openai-compatible" if os.getenv("OPENAI_API_KEY") else "local-fallback",
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "dotenv_file": str(BASE_DIR / ".env"),
        "dotenv_present": (BASE_DIR / ".env").exists(),
        "api_key_configured": bool(os.getenv("OPENAI_API_KEY")),
        "web_search": bool(os.getenv("TAVILY_API_KEY")),
        "memory": get_setting("memory_enabled", "true") == "true",
        "knowledge": get_setting("knowledge_enabled", "true") == "true",
        "context_optimization": get_setting("context_enabled", "true") == "true",
    }


@router.get("/api/upload-config")
def upload_config() -> dict[str, Any]:
    return {
        "max_size_mb": 50,
        "allowed": ["txt", "md", "pdf", "docx", "xlsx", "csv", "png", "jpg", "py", "js", "html", "css"],
    }


@router.get("/api/uploads/{stored_name}")
def download_upload(stored_name: str) -> FileResponse:
    path = UPLOAD_DIR / Path(stored_name).name
    if not path.exists():
        raise HTTPException(404, "文件不存在")
    return FileResponse(path)


@router.get("/api/context/summary/{session_id}")
def context_summary(session_id: str) -> dict[str, str]:
    messages = recent_context(session_id, 20)
    text = "\n".join(f"{item['role']}: {item['content'][:160]}" for item in messages)
    return {"summary": text or "暂无可摘要内容"}


@router.post("/api/context/migrate")
async def context_migrate(request: Request) -> dict[str, Any]:
    payload = await request.json()
    return {"ok": True, "summary": context_summary(payload.get("session_id", ""))["summary"]}


@router.post("/api/stt")
async def stt() -> dict[str, str]:
    return {"text": "这是语音识别占位结果。接入真实 STT 服务后会返回录音内容。"}


@router.post("/api/tts")
async def tts(text: str = Form("")) -> JSONResponse:
    return JSONResponse({"text": text, "mode": "browser-speech-synthesis"})


@router.post("/api/visualize")
async def visualize(request: Request) -> dict[str, Any]:
    payload = await request.json()
    return {"type": "bars", "title": payload.get("title", "可视化"), "data": [34, 55, 27, 72, 48]}


@router.get("/api/evolution/wiki/export")
def export_wiki() -> FileResponse:
    path = DATA_DIR / "experience-wiki.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        with db() as conn:
            rows = conn.execute(
                "SELECT title,content FROM knowledge WHERE status!='archived'"
            ).fetchall()
        for index, row in enumerate(rows, 1):
            archive.writestr(f"{index}-{row['title']}.md", row["content"])
    return FileResponse(path, filename="experience-wiki.zip")
