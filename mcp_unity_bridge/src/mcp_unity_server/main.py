# En: mcp_unity_bridge/src/mcp_unity_server/main.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, Any
import json
import uuid

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.unity_client_id: str = "unity_editor"

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"Cliente conectado: {client_id}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        print(f"Cliente desconectado: {client_id}")

    async def send_json_to_client(self, message: Any, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)
        else:
            print(f"Error: Intento de enviar a cliente desconectado: {client_id}")

    async def route_message_to_unity(self, message: dict, sender_id: str):
        if self.unity_client_id in self.active_connections:
            message["request_id"] = sender_id
            await self.send_json_to_client(message, self.unity_client_id)
        else:
            error_payload = json.dumps({"error": "Unity Editor no está conectado."})
            error_response = {"request_id": sender_id, "status": "error", "payload": error_payload}
            await self.send_json_to_client(error_response, sender_id)
            print(f"Error: Mensaje de {sender_id} no enviado (Unity desconectado).")

manager = ConnectionManager()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            print(f"Mensaje de '{client_id}': {data}")

            if client_id == manager.unity_client_id:
                ai_client_to_respond = data.get("request_id")
                if ai_client_to_respond:
                    # CORRECCIÓN: Usar la función de envío del manager
                    await manager.send_json_to_client(data, ai_client_to_respond)
                else:
                    print("Advertencia: Respuesta de Unity sin 'request_id'. No se puede enrutar.")
            else:
                await manager.route_message_to_unity(data, client_id)

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        print(f"Error con el cliente {client_id}: {e}")
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