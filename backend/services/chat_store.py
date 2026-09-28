from __future__ import annotations

import secrets
from typing import Any

from backend.repositories import chat_repository

pg_db = chat_repository.pg_db
use_postgres = chat_repository.use_postgres


def init_chat_store() -> None:
    chat_repository.init_chat_store()


def ensure_conversation(session_id: str | None, title: str = "新对话") -> str:
    conversation_id = session_id or secrets.token_hex(12)
    if not chat_repository.conversation_exists(conversation_id):
        chat_repository.create_conversation(conversation_id, title)
    return conversation_id


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    attachments: list[dict[str, Any]] | None = None,
) -> str:
    message_id = secrets.token_hex(12)
    chat_repository.add_message(message_id, conversation_id, role, content, attachments)
    return message_id


def recent_context(conversation_id: str, limit: int = 8) -> list[dict[str, str]]:
    return chat_repository.recent_context(conversation_id, limit)


def list_history(q: str = "", include_deleted: int = 0) -> list[dict[str, Any]]:
    return chat_repository.list_history(q, include_deleted)


def get_history_detail(session_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return chat_repository.get_history_detail(session_id)


def rename_history(session_id: str, title: str) -> None:
    chat_repository.rename_history(session_id, title)


def delete_history(session_id: str, hard: int = 0) -> None:
    chat_repository.delete_history(session_id, hard)


def restore_history(session_id: str) -> None:
    chat_repository.restore_history(session_id)


def list_trash() -> list[dict[str, Any]]:
    return chat_repository.list_trash()
