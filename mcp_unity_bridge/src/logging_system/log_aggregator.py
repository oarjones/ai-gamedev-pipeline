from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse, Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import database_path
from .database import init_db, insert_log, query_logs, export_logs
from .models import LogEntry, QueryFilters


class ConnectionManager:
    def __init__(self) -> None:
        self.clients: Set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self.lock:
            self.clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self.lock:
            if websocket in self.clients:
                self.clients.remove(websocket)

    async def broadcast(self, message: Dict) -> None:
        payload = json.dumps(message)
        async with self.lock:
            dead: List[WebSocket] = []
            for ws in list(self.clients):
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                try:
                    await ws.close()
                except Exception:
                    pass
                self.clients.discard(ws)


app = FastAPI()
manager = ConnectionManager()
DB = database_path()
init_db(DB)

# Mount static files for the web viewer
_static_dir = Path(__file__).resolve().parents[2] / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/")
def index() -> HTMLResponse:
    # Minimal landing page with link to viewer
    html = """
    <html><body>
      <h3>AI GameDev Pipeline - Logs</h3>
      <p><a href="/static/log_viewer.html">Open Log Viewer</a></p>
    </body></html>
    """
    return HTMLResponse(html)


@app.post("/logs")
async def ingest(entry: LogEntry) -> JSONResponse:
    insert_log(DB, entry)
    await manager.broadcast({"type": "log", "payload": entry.model_dump()})
    return JSONResponse({"status": "ok"})


@app.get("/logs")
def get_logs(
    component: str | None = None,
    level: str | None = None,
    keyword: str | None = None,
    start_ts: float | None = None,
    end_ts: float | None = None,
    limit: int = 200,
):
    filters = QueryFilters(
        component=component,
        level=level,
        keyword=keyword,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    items = query_logs(DB, filters, limit=limit)
    return [i.model_dump() for i in items]


@app.get("/export")
def export(
    fmt: str = Query("json", pattern="^(json|csv)$"),
    component: str | None = None,
    level: str | None = None,
    keyword: str | None = None,
    start_ts: float | None = None,
    end_ts: float | None = None,
    limit: int = 1000,
):
    filters = QueryFilters(
        component=component,
        level=level,
        keyword=keyword,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    data = export_logs(DB, filters, fmt=fmt, limit=limit)
    media = "application/json" if fmt == "json" else "text/csv"
    return Response(content=data, media_type=media)


@app.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # This endpoint is broadcast-only; just keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)


def create_app() -> FastAPI:
    return app
