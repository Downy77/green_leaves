from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.core.config import STATIC_DIR
from backend.core.db import lifespan
from backend.routers import (
    auth,
    chat,
    history,
    knowledge,
    memory,
    productivity,
    settings,
    system,
)


app = FastAPI(
    title="Coupling Life Clone",
    version="1.2.0",
    description=(
        "A local-first AI workspace powered by FastAPI, LangGraph and LangChain. "
        "HTTP routes are split by product capability."
    ),
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.include_router(system.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(history.router)
app.include_router(memory.router)
app.include_router(settings.router)
app.include_router(knowledge.router)
app.include_router(productivity.router)


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )
