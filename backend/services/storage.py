from __future__ import annotations

import shutil
import secrets
import time
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from backend.core.config import UPLOAD_DIR
from backend.repositories import memory_repository, settings_repository
from backend.services.chat_store import add_message, ensure_conversation, recent_context
from backend.services.knowledge_search import search_knowledge


def get_setting(key: str, default: str = "") -> str:
    return settings_repository.get_setting(key, default)


def set_setting(key: str, value: str) -> None:
    settings_repository.set_setting(key, value)


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
        return search_knowledge(query, limit)

    def active_memories(self, query: str, limit: int = 6) -> list[dict[str, Any]]:
        return memory_repository.list_active_memories(query, limit)
