"""Build pgvector chunks for knowledge notes created before vector indexing.

Run ``python -m scripts.reindex_knowledge`` from the project root after setting
KNOWLEDGE_DATABASE_URL.
"""

from backend.core.db import db, init_db
from backend.services.knowledge_vectors import enabled, index_note, init_index


def main() -> None:
    if not enabled():
        raise SystemExit("请先设置 KNOWLEDGE_DATABASE_URL")
    init_db()
    init_index()
    with db() as conn:
        notes = conn.execute(
            "SELECT id,content FROM knowledge WHERE status!='archived'"
        ).fetchall()
    success = 0
    failed = 0
    for note in notes:
        try:
            count = index_note(note["id"], note["content"])
            status = "ready"
            print(f"{note['id']}: {count} chunks")
            success += 1
        except Exception as exc:
            status = "failed"
            failed += 1
            print(f"{note['id']}: failed ({exc})")
        with db() as conn:
            conn.execute("UPDATE knowledge SET index_status=? WHERE id=?", (status, note["id"]))
    print(f"完成：{success} 成功，{failed} 失败")


if __name__ == "__main__":
    main()
