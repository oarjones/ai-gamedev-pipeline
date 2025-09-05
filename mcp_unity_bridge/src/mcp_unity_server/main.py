# En: mcp_unity_bridge/src/mcp_unity_server/main.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Dict, Any
import json
import uuid

app = FastAPI()
try:
    from ..logging_system import LogManager  # type: ignore
    _srv_logger = LogManager(component="mcp_server").get_logger()
except Exception:
    import logging as _logging
    _srv_logger = _logging.getLogger("mcp_server")
    if not _srv_logger.handlers:
        _srv_logger.addHandler(_logging.StreamHandler())
    _srv_logger.setLevel(_logging.INFO)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.unity_client_id: str = "unity_editor"

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        _srv_logger.info(f"Cliente conectado: {client_id}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        _srv_logger.info(f"Cliente desconectado: {client_id}")

    async def send_json_to_client(self, message: Any, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)
        else:
            _srv_logger.warning(f"Error: Intento de enviar a cliente desconectado: {client_id}")

    async def route_message_to_unity(self, message: dict, sender_id: str):
        if self.unity_client_id in self.active_connections:
            message["request_id"] = sender_id
            await self.send_json_to_client(message, self.unity_client_id)
        else:
            error_payload = json.dumps({"error": "Unity Editor no está conectado."})
            error_response = {"request_id": sender_id, "status": "error", "payload": error_payload}
            await self.send_json_to_client(error_response, sender_id)
            _srv_logger.error(f"Error: Mensaje de {sender_id} no enviado (Unity desconectado).")

manager = ConnectionManager()


class ImportFBXRequest(BaseModel):
    path: str


@app.post("/import_fbx")
async def import_fbx(req: ImportFBXRequest):
    if manager.unity_client_id not in manager.active_connections:
        return {"status": "error", "message": "Unity Editor no está conectado."}

    request_id = str(uuid.uuid4())
    message = {
        "type": "command",
        "action": "ImportFBX",
        "payload": {"path": req.path},
        "request_id": request_id,
    }
    await manager.send_json_to_client(message, manager.unity_client_id)

    ensure_request_id = str(uuid.uuid4())
    ensure_message = {
        "type": "command",
        "action": "EnsureCameraAndLight",
        "payload": {},
        "request_id": ensure_request_id,
    }
    await manager.send_json_to_client(ensure_message, manager.unity_client_id)

    return {"status": "ok", "request_id": request_id}

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            _srv_logger.debug(f"Mensaje de '{client_id}': {data}")

            if client_id == manager.unity_client_id:
                ai_client_to_respond = data.get("request_id")
                if ai_client_to_respond:
                    # CORRECCIÓN: Usar la función de envío del manager
                    await manager.send_json_to_client(data, ai_client_to_respond)
                else:
                    _srv_logger.warning("Respuesta de Unity sin 'request_id'. No se puede enrutar.")
            else:
                await manager.route_message_to_unity(data, client_id)

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        _srv_logger.error(f"Error con el cliente {client_id}: {e}")
        if client_id in manager.active_connections:
            manager.disconnect(client_id)


# El bloque __main__ está bien, pero asegúrate de que config.py tiene el puerto correcto.
if __name__ == "__main__":
    import uvicorn
    from .config import get_settings

    settings = get_settings()
    uvicorn.run(
        "mcp_unity_server.main:app",
        host=settings["mcp_host"],
        port=settings["mcp_port"],
        reload=True
    )
