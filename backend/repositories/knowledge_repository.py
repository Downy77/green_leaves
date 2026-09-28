from __future__ import annotations

from typing import Any

from backend.core.db import db, now_iso, row_to_dict


def update_index_status(note_id: str, status: str) -> None:
    with db() as conn:
        conn.execute("UPDATE knowledge SET index_status=? WHERE id=?", (status, note_id))


def list_graph() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with db() as conn:
        nodes = [
            row_to_dict(row)
            for row in conn.execute(
                "SELECT * FROM knowledge WHERE status!='archived' ORDER BY updated_at DESC"
            ).fetchall()
        ]
        active = {node["id"] for node in nodes}
        edges = [
            row_to_dict(row)
            for row in conn.execute("SELECT * FROM relations").fetchall()
            if row["source_id"] in active and row["target_id"] in active
        ]
    return nodes, edges


def create_note(
    note_id: str,
    title: str,
    content: str,
    kind: str,
    source_file: str = "",
) -> None:
    timestamp = now_iso()
    with db() as conn:
        conn.execute(
            "INSERT INTO knowledge(id,title,content,kind,source_file,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (note_id, title, content, kind, source_file, timestamp, timestamp),
        )


def get_active_note(note_id: str) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM knowledge WHERE id=? AND status!='archived'", (note_id,)
        ).fetchone()
    return row_to_dict(row)


def update_note(note_id: str, title: str, content: str, index_status: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE knowledge SET title=?, content=?, updated_at=?, index_status=? WHERE id=?",
            (title, content, now_iso(), index_status, note_id),
        )


def archive_note(note_id: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE knowledge SET status='archived', updated_at=? WHERE id=?",
            (now_iso(), note_id),
        )


def create_relation(source_id: str, target_id: str, relation_id: str, relation_type: str) -> str:
    with db() as conn:
        found = conn.execute(
            "SELECT id FROM knowledge WHERE id IN (?,?) AND status!='archived'",
            (source_id, target_id),
        ).fetchall()
        if len(found) != 2:
            return ""
        duplicate = conn.execute(
            "SELECT id FROM relations WHERE source_id=? AND target_id=?",
            (source_id, target_id),
        ).fetchone()
        if duplicate:
            return duplicate["id"]
        conn.execute(
            "INSERT INTO relations(id,source_id,target_id,type) VALUES (?,?,?,?)",
            (relation_id, source_id, target_id, relation_type),
        )
    return relation_id


def list_recent_notes(limit: int) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM knowledge WHERE status!='archived' ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def list_keyword_matches(query: str, limit: int) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM knowledge WHERE status!='archived' "
            "AND (title LIKE ? OR content LIKE ?) ORDER BY updated_at DESC LIMIT ?",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
    return [row_to_dict(row) for row in rows]
