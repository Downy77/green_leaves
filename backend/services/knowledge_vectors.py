"""Optional local Chinese embeddings stored in the existing PostgreSQL."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from backend.core.config import DATA_DIR, KNOWLEDGE_DATABASE_URL
from backend.services.knowledge_documents import chunk_text

logger = logging.getLogger(__name__)
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
EMBEDDING_DIMENSIONS = 512


def enabled() -> bool:
    return bool(KNOWLEDGE_DATABASE_URL)


@lru_cache(maxsize=1)
def _embedder():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=EMBEDDING_MODEL, cache_dir=str(DATA_DIR / "models"))


def _vectors(texts: list[str]) -> list[list[float]]:
    vectors = [vector.tolist() for vector in _embedder().embed(texts)]
    if any(len(vector) != EMBEDDING_DIMENSIONS for vector in vectors):
        raise RuntimeError("知识向量维度与数据库定义不一致")
    return vectors


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"


def init_index() -> None:
    if not enabled():
        return
    import psycopg

    with psycopg.connect(KNOWLEDGE_DATABASE_URL) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS knowledge_chunks ("
            "knowledge_id TEXT NOT NULL, chunk_index INTEGER NOT NULL, "
            "content TEXT NOT NULL, embedding vector(512) NOT NULL, "
            "PRIMARY KEY (knowledge_id, chunk_index))"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw "
            "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
        )


def index_note(note_id: str, content: str) -> int:
    """Replace all chunks atomically in PostgreSQL; caller owns the source record."""
    if not enabled():
        return 0
    import psycopg

    chunks = chunk_text(content, size=450, overlap=70)
    vectors = _vectors(chunks) if chunks else []
    with psycopg.connect(KNOWLEDGE_DATABASE_URL) as conn:
        conn.execute("DELETE FROM knowledge_chunks WHERE knowledge_id=%s", (note_id,))
        for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
            conn.execute(
                "INSERT INTO knowledge_chunks (knowledge_id,chunk_index,content,embedding) "
                "VALUES (%s,%s,%s,%s::vector)",
                (note_id, index, chunk, _vector_literal(vector)),
            )
    return len(chunks)


def delete_note(note_id: str) -> None:
    if not enabled():
        return
    import psycopg

    with psycopg.connect(KNOWLEDGE_DATABASE_URL) as conn:
        conn.execute("DELETE FROM knowledge_chunks WHERE knowledge_id=%s", (note_id,))


def search(query: str, limit: int = 8) -> list[dict[str, Any]]:
    if not enabled() or not query.strip():
        return []
    import psycopg

    vector = _vector_literal(_vectors([query.strip()])[0])
    with psycopg.connect(KNOWLEDGE_DATABASE_URL) as conn:
        rows = conn.execute(
            "SELECT knowledge_id,chunk_index,content,1-(embedding <=> %s::vector) AS score "
            "FROM knowledge_chunks ORDER BY embedding <=> %s::vector LIMIT %s",
            (vector, vector, limit),
        ).fetchall()
    return [
        {"knowledge_id": row[0], "chunk_index": row[1], "content": row[2], "score": float(row[3])}
        for row in rows
    ]
