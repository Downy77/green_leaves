from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.core.db import db, row_to_dict
from backend.services.storage import get_setting, set_setting

router = APIRouter(tags=["auth"])


@router.get("/auth/check")
def auth_check() -> dict[str, Any]:
    return {
        "authenticated": True,
        "guest": False,
        "user": {"username": "local-user", "name": "体验用户", "admin_level": "super_admin"},
    }


@router.get("/auth/profile")
def profile_get() -> dict[str, Any]:
    with db() as conn:
        profile = row_to_dict(conn.execute("SELECT * FROM profile WHERE id=1").fetchone())
    profile["role"] = profile.get("identity", "user")
    return profile


@router.put("/auth/profile")
async def profile_put(request: Request) -> dict[str, Any]:
    payload = await request.json()
    with db() as conn:
        conn.execute(
            "UPDATE profile SET name=?, identity=?, company=?, department=? WHERE id=1",
            (
                payload.get("name", ""),
                payload.get("identity", "user"),
                payload.get("company", ""),
                payload.get("department", ""),
            ),
        )
    return {"ok": True, **payload}


@router.post("/auth/logout")
def logout() -> dict[str, bool]:
    return {"ok": True}


@router.get("/auth/api-key-status")
def api_key_status() -> dict[str, Any]:
    value = get_setting("api_key")
    return {"has_key": bool(value), "masked": value[:6] + "..." + value[-4:] if value else ""}


@router.post("/auth/apply-api-key")
def apply_api_key() -> dict[str, Any]:
    key = "clk_" + secrets.token_urlsafe(28)
    set_setting("api_key", key)
    return {"ok": True, "api_key": key}


@router.get("/auth/view-api-key")
def view_api_key() -> dict[str, str]:
    value = get_setting("api_key")
    if not value:
        raise HTTPException(404, "尚未申请 API 密钥")
    return {"api_key": value}


@router.get("/api/login-help")
def login_help() -> dict[str, str]:
    return {
        "title": "联系管理员",
        "content": "本地复刻版默认免登录。如需接入真实组织账号，可在后端替换 /auth/check 和 /auth/profile。",
    }
