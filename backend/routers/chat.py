from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from backend.core.config import available_models
from backend.services.agent_service import get_agent_runtime
from backend.services.storage import add_message, ensure_conversation, save_upload

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/models")
def chat_models() -> dict:
    models = available_models()
    first_configured = next((item for item in models if item["configured"]), models[0])
    return {
        "models": models,
        "default": first_configured["id"],
    }


@router.post("/stream")
async def chat_stream(request: Request) -> StreamingResponse:
    form = await request.form()
    message = str(form.get("message") or "")
    session_id = str(form.get("session_id") or "") or None
    web_mode = str(form.get("web_search_mode") or "auto")
    models = available_models()
    selected_id = str(form.get("model") or "").strip() or chat_models()["default"]
    selected = next((item for item in models if item["id"] == selected_id), None)
    if selected is None:
        raise HTTPException(status_code=400, detail="所选模型不可用，请刷新页面后重试。")
    if not selected["configured"] and not (selected["provider"] == "openai" and not any(item["configured"] for item in models)):
        raise HTTPException(status_code=400, detail=f"请先配置 {selected['provider_label']} 的 API Key。")
    conversation_id = ensure_conversation(session_id)
    attachments = [
        save_upload(value)
        for _, value in form.multi_items()
        if isinstance(value, UploadFile)
    ]
    add_message(conversation_id, "user", message, attachments)

    async def generate() -> AsyncIterator[bytes]:
        full_answer = ""
        runtime = get_agent_runtime()
        status = {"type": "status", "phase": "thinking", "text": "📚 正在整理上下文…"}
        yield f"data: {json.dumps(status, ensure_ascii=False)}\n\n".encode()
        try:
            agent_state = await runtime.prepare(
                conversation_id=conversation_id,
                user_message=message,
                web_mode=web_mode,
                model=selected["model"],
                provider=selected["provider"],
                attachments=attachments,
            )
            trace = {
                "type": "trace",
                "phase": "prepared",
                "attachments": len(attachments),
                "memory_enabled": bool(agent_state.get("memory_enabled", True)),
                "knowledge_enabled": bool(agent_state.get("knowledge_enabled", True)),
                "context_enabled": bool(agent_state.get("context_enabled", True)),
                "memories": len(agent_state.get("memories", [])),
                "knowledge": len(agent_state.get("knowledge", [])),
                "web_results": len(agent_state.get("web_results", [])),
                "history": len(agent_state.get("history", [])),
                "route": agent_state.get("route", "knowledge_assistant"),
                "web_mode": web_mode,
            }
            yield f"data: {json.dumps(trace, ensure_ascii=False)}\n\n".encode()
            async for piece in runtime.stream_prepared_answer(agent_state):
                if not full_answer:
                    status = {"type": "status", "phase": "streaming", "text": "✦ 正在生成回答…"}
                    yield f"data: {json.dumps(status, ensure_ascii=False)}\n\n".encode()
                full_answer += piece
                event = {"type": "delta", "content": piece}
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode()
            add_message(conversation_id, "assistant", full_answer)
            status = {"type": "status", "phase": "complete", "text": "✓ 回答已形成"}
            yield f"data: {json.dumps(status, ensure_ascii=False)}\n\n".encode()
            event = {"type": "done", "session_id": conversation_id}
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode()
        except Exception:
            status = {"type": "status", "phase": "error", "text": "连接中断，请稍后重试。"}
            yield f"data: {json.dumps(status, ensure_ascii=False)}\n\n".encode()
            raise

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
