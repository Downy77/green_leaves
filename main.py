"""Canonical ASGI entrypoint.

Run with:

    uvicorn main:app --host 0.0.0.0 --port 8000

The legacy ``app:app`` import path remains available for compatibility.
"""

import os

import uvicorn

from app import app

__all__ = ["app"]


def run() -> None:
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )


if __name__ == "__main__":
    run()
