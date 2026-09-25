from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from backend.services.storage import get_setting, set_setting

router = APIRouter(prefix="/api", tags=["settings"])


def _get_bool(key: str) -> dict[str, bool]:
    return {"enabled": get_setting(key, "true") == "true"}


def _put_bool(key: str, payload: dict[str, Any]) -> dict[str, bool]:
    enabled = bool(payload.get("enabled"))
    set_setting(key, "true" if enabled else "false")
    return {"enabled": enabled}


@router.get("/knowledge/settings")
def knowledge_settings() -> dict[str, bool]:
    return _get_bool("knowledge_enabled")


@router.put("/knowledge/settings")
async def knowledge_settings_put(request: Request) -> dict[str, bool]:
    return _put_bool("knowledge_enabled", await request.json())


@router.get("/context/settings")
def context_settings() -> dict[str, bool]:
    return _get_bool("context_enabled")


@router.put("/context/settings")
async def context_settings_put(request: Request) -> dict[str, bool]:
    return _put_bool("context_enabled", await request.json())

