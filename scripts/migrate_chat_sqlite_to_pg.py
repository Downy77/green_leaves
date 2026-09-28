from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.config import CHAT_DATABASE_URL, DB_PATH  # noqa: E402
from backend.services.chat_store import init_chat_store, pg_db  # noqa: E402


def _load_json(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def migrate(sqlite_path: Path = DB_PATH) -> tuple[int, int]:
    if not CHAT_DATABASE_URL:
        raise RuntimeError("请先在 .env 中配置 CHAT_DATABASE_URL")
    if not sqlite_path.exists():
        raise FileNotFoundError(f"找不到 SQLite 数据库：{sqlite_path}")

    init_chat_store()
    source = sqlite3.connect(sqlite_path)
    source.row_factory = sqlite3.Row
    try:
        columns = {
            row["name"]
            for row in source.execute("PRAGMA table_info(conversations)").fetchall()
        }
        deleted_at_expr = "deleted_at" if "deleted_at" in columns else "'' AS deleted_at"
        conversations = source.execute(
            f"SELECT id,title,created_at,updated_at,deleted,{deleted_at_expr} FROM conversations"
        ).fetchall()
        messages = source.execute(
            "SELECT id,conversation_id,role,content,attachments,created_at FROM messages"
        ).fetchall()

        with pg_db() as target:
            for row in conversations:
                target.execute(
                    """
                    INSERT INTO conversations(id,title,created_at,updated_at,deleted,deleted_at)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO UPDATE SET
                        title=EXCLUDED.title,
                        updated_at=EXCLUDED.updated_at,
                        deleted=EXCLUDED.deleted,
                        deleted_at=EXCLUDED.deleted_at
                    """,
                    (
                        row["id"],
                        row["title"],
                        row["created_at"],
                        row["updated_at"],
                        bool(row["deleted"]),
                        row["deleted_at"] or None,
                    ),
                )
            for row in messages:
                target.execute(
                    """
                    INSERT INTO messages(id,conversation_id,role,content,attachments,created_at)
                    VALUES (%s,%s,%s,%s,%s::jsonb,%s)
                    ON CONFLICT (id) DO UPDATE SET
                        role=EXCLUDED.role,
                        content=EXCLUDED.content,
                        attachments=EXCLUDED.attachments,
                        created_at=EXCLUDED.created_at
                    """,
                    (
                        row["id"],
                        row["conversation_id"],
                        row["role"],
                        row["content"],
                        json.dumps(_load_json(row["attachments"]), ensure_ascii=False),
                        row["created_at"],
                    ),
                )
    finally:
        source.close()

    return len(conversations), len(messages)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate chat conversations from SQLite to PostgreSQL.")
    parser.add_argument(
        "--sqlite",
        type=Path,
        default=DB_PATH,
        help="SQLite database path, defaults to data/app.db.",
    )
    args = parser.parse_args()
    conversation_count, message_count = migrate(args.sqlite)
    print(f"已迁移 {conversation_count} 个会话，{message_count} 条消息。")


if __name__ == "__main__":
    main()
