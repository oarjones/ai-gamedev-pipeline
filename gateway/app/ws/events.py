"""WebSocket event handling for AI Gateway with per-project rooms."""

import json
import logging
from typing import Dict, Set
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections segmented by projectId rooms."""

    def __init__(self) -> None:
        # projectId -> set of websockets
        self.rooms: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: str) -> None:
        await websocket.accept()
        self.rooms.setdefault(project_id, set()).add(websocket)
        logger.info("WS connected to project '%s' (room size=%d)", project_id, len(self.rooms[project_id]))

    def disconnect(self, websocket: WebSocket) -> None:
        # Remove from all rooms (client could be in one)
        empty_rooms = []
        for pid, conns in self.rooms.items():
            if websocket in conns:
                conns.discard(websocket)
                logger.info("WS disconnected from project '%s' (room size=%d)", pid, len(conns))
            if not conns:
                empty_rooms.append(pid)
        for pid in empty_rooms:
            self.rooms.pop(pid, None)

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error("Error sending personal message: %s", e)
            self.disconnect(websocket)

    async def broadcast_project(self, project_id: str, message: str) -> None:
        conns = self.rooms.get(project_id)
        if not conns:
            return
        disconnected: Set[WebSocket] = set()
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.error("Error broadcasting to project '%s': %s", project_id, e)
                disconnected.add(ws)
        for ws in disconnected:
            self.disconnect(ws)


# Global connection manager instance
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for per-project event streaming.

    Requires query param ?projectId=...; otherwise rejects the connection.
    """
    project_id = websocket.query_params.get("projectId")
    api_key = websocket.headers.get("X-API-Key") or websocket.query_params.get("apiKey")
    try:
        from app.config import settings as _settings
        if _settings.auth.require_api_key:
            if not api_key or api_key != _settings.auth.api_key:
                await websocket.accept()
                await websocket.send_text(json.dumps({"type": "error", "message": "unauthorized"}))
                await websocket.close()
                return
    except Exception:
        pass
    if not project_id:
        # Reject clients without projectId for now
        await websocket.accept()
        await websocket.send_text(json.dumps({"type": "error", "message": "projectId required"}))
        await websocket.close()
        return

    await manager.connect(websocket, project_id)
    try:
        while True:
            # We currently ignore client messages; this is a server-push channel.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        manager.disconnect(websocket)
