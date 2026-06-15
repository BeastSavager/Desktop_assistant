"""
Jarvis AI Assistant — Web backend (FastAPI)

Serves the single-page web UI and exposes the assistant over HTTP + WebSocket.
Wraps the existing JarvisBrain / tools / memory — it does NOT reimplement them.

SECURITY: bind to 127.0.0.1 only (see config.WEB_HOST). The assistant can touch
local apps and files, so the port must never be exposed to the network.
"""

import asyncio
import logging
import sys
import threading
from pathlib import Path

from fastapi import FastAPI, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from brain import JarvisBrain
from config import (
    ALLOW_DANGEROUS_TOOLS,
    LLM_MODEL,
    LLM_PROVIDER,
    MAX_UPLOAD_BYTES,
    WAKE_WORD_ALTERNATIVES,
)
from memory import MemoryManager
from tools import _safe_path, _workspace_root

logger = logging.getLogger("jarvis.server")

# Under a PyInstaller bundle, data files live in sys._MEIPASS.
_BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
WEBAPP_DIR = _BASE_DIR / "webapp"

app = FastAPI(title="Jarvis AI Assistant")

# One shared memory + brain for the process. MemoryManager is thread-local
# SQLite-safe, so it is fine to use from the threadpool and WebSocket workers.
_memory = MemoryManager()
_brain = JarvisBrain(_memory)


class ChatRequest(BaseModel):
    message: str


# ── Health & info ─────────────────────────────────────────────────────────────


@app.get("/health")
def health() -> dict:
    """Readiness probe used by the launcher before opening the browser."""
    return {
        "status": "ok",
        "provider": LLM_PROVIDER,
        "model": LLM_MODEL,
        "dangerous_tools_enabled": ALLOW_DANGEROUS_TOOLS,
        "wake_words": WAKE_WORD_ALTERNATIVES,
    }


# ── Chat (non-streaming fallback) ─────────────────────────────────────────────


@app.post("/chat")
def chat(req: ChatRequest) -> dict:
    message = (req.message or "").strip()
    if not message:
        return {"reply": "Please say something."}
    reply = _brain.think(message)
    return {"reply": reply}


# ── Chat (streaming with live tool-activity events) ───────────────────────────


@app.websocket("/stream")
async def stream(ws: WebSocket) -> None:
    await ws.accept()
    loop = asyncio.get_event_loop()
    try:
        while True:
            data = await ws.receive_json()
            message = (data or {}).get("message", "").strip()
            if not message:
                continue

            queue: asyncio.Queue = asyncio.Queue()
            sentinel = object()

            # Defaults bind the per-iteration objects into the thread closure.
            def worker(msg=message, q=queue, end=sentinel, lp=loop) -> None:
                try:
                    for event in _brain.stream_turn(msg):
                        lp.call_soon_threadsafe(q.put_nowait, event)
                except Exception as e:  # noqa: BLE001
                    lp.call_soon_threadsafe(
                        q.put_nowait,
                        {"type": "final", "text": f"Error: {e}"},
                    )
                finally:
                    lp.call_soon_threadsafe(q.put_nowait, end)

            threading.Thread(target=worker, daemon=True).start()

            while True:
                event = await queue.get()
                if event is sentinel:
                    break
                await ws.send_json(event)
    except WebSocketDisconnect:
        return


# ── Memory panel ──────────────────────────────────────────────────────────────


@app.get("/memory/facts")
def list_facts() -> dict:
    return {"facts": _memory.get_all_facts()}


@app.delete("/memory/facts/{key}")
def delete_fact(key: str) -> dict:
    removed = _memory.delete_fact(key)
    return {"deleted": removed}


@app.post("/memory/clear")
def clear_history() -> dict:
    _memory.clear_short_term()
    return {"cleared": True}


# ── File workspace ────────────────────────────────────────────────────────────


@app.get("/files")
def files() -> dict:
    root = _workspace_root()
    return {
        "files": [
            {"name": p.name, "size": p.stat().st_size}
            for p in sorted(root.iterdir())
            if p.is_file()
        ]
    }


@app.post("/files/upload")
async def upload(file: UploadFile) -> JSONResponse:
    try:
        path = _safe_path(file.filename or "")
    except ValueError:
        return JSONResponse({"error": "invalid filename"}, status_code=400)

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        return JSONResponse({"error": "file too large"}, status_code=413)
    path.write_bytes(content)
    return JSONResponse({"name": path.name, "size": len(content)})


@app.get("/files/{name}", response_model=None)
def download(name: str) -> FileResponse | JSONResponse:
    try:
        path = _safe_path(name)
    except ValueError:
        return JSONResponse({"error": "invalid filename"}, status_code=400)
    if not path.exists() or not path.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(str(path), filename=path.name)


# ── Static SPA (mounted last so API routes take precedence) ────────────────────

if WEBAPP_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEBAPP_DIR), html=True), name="spa")
