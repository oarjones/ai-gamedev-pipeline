
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from .models import CommandRequest, QueryRequest, UnityResponse, Message
import json
import asyncio
import uuid

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.unity_connection: WebSocket | None = None
        self.pending_queries: dict[str, WebSocket] = {}

    async def connect_unity(self, websocket: WebSocket):
        await websocket.accept()
        self.unity_connection = websocket

    def disconnect_unity(self):
        self.unity_connection = None

    async def send_to_unity(self, message: dict):
        if self.unity_connection:
            await self.unity_connection.send_json(message)
        else:
            raise HTTPException(status_code=503, detail="Unity Editor no está conectado.")

    async def route_response_to_ai_client(self, request_id: str, payload: str):
        if request_id in self.pending_queries:
            ai_client_websocket = self.pending_queries.pop(request_id)
            await ai_client_websocket.send_text(payload)
        else:
            print(f"[Server] Advertencia: request_id {request_id} no encontrado en pending_queries.")

manager = ConnectionManager()

@app.websocket("/ws/unity")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect_unity(websocket)
    print("Unity Editor Conectado.")
    try:
        while True:
            message = await websocket.receive_text()
            try:
                data = json.loads(message)
                if "request_id" in data and "status" in data and "payload" in data:
                    # Es una respuesta de Unity a una query
                    unity_response = UnityResponse(**data)
                    await manager.route_response_to_ai_client(unity_response.request_id, unity_response.payload)
                elif data.get("type") == "log":
                    print(f"LOG de Unity [{data.get('level')}]: {data.get('message')}")
                else:
                    print(f"[Server] Mensaje desconocido de Unity: {message}")
            except json.JSONDecodeError:
                print(f"[Server] Mensaje no JSON de Unity: {message}")
            except Exception as e:
                print(f"[Server] Error procesando mensaje de Unity: {e} - Mensaje: {message}")

    except WebSocketDisconnect:
        manager.disconnect_unity()
        print("Unity Editor Desconectado.")

@app.websocket("/ws/ai")
async def ai_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("AI Client Conectado.")
    try:
        while True:
            message_str = await websocket.receive_text()
            try:
                message_data = json.loads(message_str)
                msg_type = message_data.get("type")

                if msg_type == "command":
                    command_request = CommandRequest(**message_data.get("data"))
                    await manager.send_to_unity({"type": "command", "data": command_request.dict()})
                    await websocket.send_text(json.dumps({"status": "success", "message": "Command sent to Unity"}))
                elif msg_type == "query":
                    query_data = message_data.get("data")
                    query_request = QueryRequest(**query_data)
                    
                    request_id = str(uuid.uuid4())
                    query_request.request_id = request_id
                    manager.pending_queries[request_id] = websocket
                    
                    await manager.send_to_unity({"type": "query", "data": query_request.dict()})

                else:
                    await websocket.send_text(json.dumps({"status": "error", "message": "Unknown message type"}))

            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"status": "error", "message": "Invalid JSON format"}))
            except Exception as e:
                await websocket.send_text(json.dumps({"status": "error", "message": f"Server error: {str(e)}"}))

    except WebSocketDisconnect:
        print("AI Client Desconectado.")


# This endpoint is now deprecated as AI clients will use the /ws/ai websocket
@app.post("/unity/run-command")
async def run_command_in_unity():
    raise HTTPException(status_code=405, detail="This endpoint is deprecated. Please use the /ws/ai WebSocket for communication.")
