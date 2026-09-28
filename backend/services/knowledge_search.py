"""Hybrid semantic/keyword retrieval over canonical SQLite knowledge notes."""

from __future__ import annotations

import logging
from typing import Any

from backend.repositories import knowledge_repository
from backend.services import knowledge_vectors

logger = logging.getLogger(__name__)


def search_knowledge(query: str, limit: int = 5) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        return knowledge_repository.list_recent_notes(limit)

    semantic: list[dict[str, Any]] = []
    if knowledge_vectors.enabled():
        try:
            semantic = knowledge_vectors.search(query, limit=max(limit * 3, 12))
        except Exception:
            logger.exception("Semantic knowledge search failed; using keyword results")

    keyword_rows = knowledge_repository.list_keyword_matches(query, max(limit * 2, 10))
    by_id: dict[str, dict[str, Any]] = {}
    for hit in semantic:
        if hit["score"] < 0.50 or hit["knowledge_id"] in by_id:
            continue
        item = knowledge_repository.get_active_note(hit["knowledge_id"])
        if item:
            item["match_excerpt"] = hit["content"]
            item["score"] = hit["score"]
            by_id[item["id"]] = item
    for item in keyword_rows:
        if item["id"] not in by_id:
            pos = item["content"].lower().find(query.lower())
            if pos >= 0:
                item["match_excerpt"] = item["content"][max(0, pos - 100): pos + 600]
            by_id[item["id"]] = item
    return list(by_id.values())[:limit]
