"""Web dashboard backend: serves the UI and streams assistant events over a WebSocket.

Security: the server binds to 127.0.0.1 by default and rejects requests whose
Origin header is not this dashboard. Without that check, any website open in
the browser could connect to ws://127.0.0.1:8765 and run commands on the PC
and phone.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from jarvis import __version__
from jarvis.core.assistant import Assistant
from jarvis.core.events import EventBus
from jarvis.services.reminders import format_when

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def create_app(assistant: Assistant, bus: EventBus, port: int) -> FastAPI:
    ctx = assistant.ctx
    clients: set[tuple[WebSocket, asyncio.Queue]] = set()
    allowed_origins = {f"http://{host}:{port}" for host in ("127.0.0.1", "localhost")}

    def origin_ok(origin: str | None) -> bool:
        return origin is None or origin in allowed_origins

    def check_origin(request: Request) -> None:
        if not origin_ok(request.headers.get("origin")):
            raise HTTPException(status_code=403, detail="Cross-origin request blocked")

    # ---------------------------------------------------------------- events

    loop_holder: dict = {}

    def forward(event: dict) -> None:
        loop = loop_holder.get("loop")
        if loop is None:
            return
        for _, q in list(clients):
            loop.call_soon_threadsafe(q.put_nowait, event)

    @asynccontextmanager
    async def lifespan(_app):
        loop_holder["loop"] = asyncio.get_running_loop()
        unsubscribe = bus.subscribe(forward)
        yield
        unsubscribe()

    app = FastAPI(
        title="J.A.R.V.I.S", version=__version__, docs_url=None, redoc_url=None, lifespan=lifespan
    )

    # ---------------------------------------------------------------- routes

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/status")
    async def status():
        info = await asyncio.to_thread(ctx.health) if ctx.health else {}
        return {**info, "version": __version__}

    @app.get("/api/reminders")
    async def reminders():
        return [
            {"id": r.id, "task": r.task, "time": r.time, "when": format_when(r.when)}
            for r in ctx.reminders.pending()
        ]

    @app.post("/api/reminders/{reminder_id}/done")
    async def complete(reminder_id: str, request: Request):
        check_origin(request)
        if not ctx.reminders.complete(reminder_id):
            raise HTTPException(status_code=404, detail="Reminder not found")
        return {"ok": True}

    @app.delete("/api/reminders/{reminder_id}")
    async def delete(reminder_id: str, request: Request):
        check_origin(request)
        if not ctx.reminders.delete(reminder_id):
            raise HTTPException(status_code=404, detail="Reminder not found")
        return {"ok": True}

    @app.post("/api/listen")
    async def listen(request: Request):
        check_origin(request)
        assistant.listen_async()
        return {"ok": True}

    @app.websocket("/ws")
    async def websocket(ws: WebSocket):
        if not origin_ok(ws.headers.get("origin")):
            await ws.close(code=1008)
            return

        await ws.accept()
        q: asyncio.Queue = asyncio.Queue()
        entry = (ws, q)
        clients.add(entry)

        await ws.send_json({"type": "history", "events": bus.history()})

        async def sender():
            while True:
                await ws.send_json(await q.get())

        send_task = asyncio.create_task(sender())

        try:
            while True:
                data = await ws.receive_json()
                if data.get("type") == "command":
                    text = str(data.get("text", ""))[:1000]
                    assistant.submit(text, source="web")
        except WebSocketDisconnect:
            pass
        except Exception:
            log.exception("WebSocket error")
        finally:
            send_task.cancel()
            clients.discard(entry)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


def serve(assistant: Assistant, bus: EventBus, host: str, port: int, background: bool) -> None:
    import uvicorn

    app = create_app(assistant, bus, port)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    log.info("Web dashboard on http://%s:%s", host, port)

    if background:
        threading.Thread(target=server.run, name="jarvis-web", daemon=True).start()
    else:
        server.run()
