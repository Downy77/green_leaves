from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Request

from backend.core.db import db, now_iso, row_to_dict

router = APIRouter(prefix="/api", tags=["productivity"])


@router.get("/memos")
def memos() -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM memos ORDER BY created_at DESC").fetchall()
    return {"memos": [row_to_dict(row) for row in rows]}


@router.post("/memos")
async def memo_create(request: Request) -> dict[str, str]:
    payload = await request.json()
    memo_id = secrets.token_hex(10)
    with db() as conn:
        conn.execute(
            "INSERT INTO memos(id,title,content,remind_time,status,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (
                memo_id,
                payload.get("title", "新备忘"),
                payload.get("content", ""),
                payload.get("remind_time", ""),
                "pending",
                now_iso(),
            ),
        )
    return {"id": memo_id}


@router.post("/memos/{memo_id}/complete")
def memo_complete(memo_id: str) -> dict[str, bool]:
    with db() as conn:
        conn.execute("UPDATE memos SET status='completed' WHERE id=?", (memo_id,))
    return {"ok": True}


@router.delete("/memos/{memo_id}")
def memo_delete(memo_id: str) -> dict[str, bool]:
    with db() as conn:
        conn.execute("DELETE FROM memos WHERE id=?", (memo_id,))
    return {"ok": True}


@router.get("/memos/due")
def memos_due() -> dict[str, list[Any]]:
    return {"due_memos": []}


@router.get("/announcements")
def announcements(filter: str = "all") -> dict[str, Any]:
    where = "WHERE read=0" if filter == "unread" else ""
    with db() as conn:
        rows = conn.execute(
            f"SELECT * FROM announcements {where} ORDER BY created_at DESC"
        ).fetchall()
    return {"items": [row_to_dict(row) for row in rows]}


@router.post("/announcements/read-all")
def announcements_read_all() -> dict[str, bool]:
    with db() as conn:
        conn.execute("UPDATE announcements SET read=1")
    return {"ok": True}


@router.get("/announcements/unread-latest")
def announcements_unread_latest() -> dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM announcements WHERE read=0 "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return {"item": row_to_dict(row) if row else None}


@router.post("/ppt/outline")
async def ppt_outline(request: Request) -> dict[str, str]:
    payload = await request.json()
    message = payload.get("message", "主题")
    return {
        "outline": (
            f"1. 背景与目标\n2. 核心洞察：{message[:40]}\n"
            "3. 方案设计\n4. 执行路径\n5. 风险与下一步"
        ),
        "template": "living-grid",
    }


@router.post("/ppt/slides")
async def ppt_slides(request: Request) -> dict[str, list[dict[str, str]]]:
    payload = await request.json()
    lines = [
        line.strip(" -0123456789.")
        for line in payload.get("outline", "").splitlines()
        if line.strip()
    ]
    return {
        "slides": [
            {
                "title": line,
                "body": f"围绕“{line}”展开说明，补充数据、案例和行动项。",
            }
            for line in lines
        ]
    }


@router.post("/evolution/feedback")
async def feedback(request: Request) -> dict[str, bool]:
    await request.json()
    return {"ok": True}


@router.post("/evolution/self-score")
async def self_score(request: Request) -> dict[str, Any]:
    await request.json()
    return {"score": 86, "note": "结构清晰，可继续补充具体案例。"}


@router.get("/evolution/summary")
def evolution_summary() -> dict[str, list[dict[str, str]]]:
    return {
        "strategies": [
            {"key": "clarity", "title": "表达更清晰", "status": "enabled"},
            {"key": "evidence", "title": "增加证据链", "status": "candidate"},
        ]
    }


@router.post("/evolution/strategies/{key}")
async def evolution_strategy(key: str, request: Request) -> dict[str, Any]:
    payload = await request.json()
    return {"key": key, "enabled": bool(payload.get("enabled"))}


@router.get("/research/jobs")
def research_jobs() -> dict[str, list[Any]]:
    return {"jobs": []}


@router.post("/research/jobs")
async def research_create(request: Request) -> dict[str, str]:
    payload = await request.json()
    return {
        "id": secrets.token_hex(8),
        "topic": payload.get("topic", "研究任务"),
        "status": "completed",
    }
