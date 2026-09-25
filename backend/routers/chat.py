from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import StreamingResponse

from backend.services.agent_service import get_agent_runtime
from backend.services.storage import add_message, ensure_conversation, save_upload

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(request: Request) -> StreamingResponse:
    form = await request.form()
    message = str(form.get("message") or "")
    session_id = str(form.get("session_id") or "") or None
    web_mode = str(form.get("web_search_mode") or "auto")
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
        async for piece in runtime.stream_answer(
            conversation_id=conversation_id,
            user_message=message,
            web_mode=web_mode,
            attachments=attachments,
        ):
            full_answer += piece
            event = {"type": "delta", "content": piece}
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode()
        add_message(conversation_id, "assistant", full_answer)
        event = {"type": "done", "session_id": conversation_id}
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode()

    return StreamingResponse(generate(), media_type="text/event-stream")
