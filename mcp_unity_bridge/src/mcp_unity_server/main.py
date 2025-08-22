# En: mcp_unity_bridge/src/mcp_unity_server/main.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from .models import UnityCommandRequest, UnityCommandResponse
import json
import asyncio # Importar asyncio

app = FastAPI()

# Gestor de conexión mejorado con un sistema de eventos para las respuestas
class ConnectionManager:
    def __init__(self):
        self.active_connection: WebSocket | None = None
        self.response_event = asyncio.Event()
        self.last_response: str | None = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connection = websocket

    def disconnect(self):
        self.active_connection = None

    async def send_to_unity(self, message: str):
        if self.active_connection:
            await self.active_connection.send_text(message)
        else:
            raise HTTPException(status_code=503, detail="Unity Editor no está conectado.")
            
    def set_response(self, response: str):
        self.last_response = response
        self.response_event.set()

manager = ConnectionManager()

@app.websocket("/ws/unity")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    print("Unity Editor Conectado.")
    try:
        while True:
            # Este es el ÚNICO lugar que escucha mensajes de Unity
            message = await websocket.receive_text()
            
            # Comprobamos si es un log o una respuesta a un comando
            try:
                data = json.loads(message)
                if data.get("type") == "log":
                    print(f"LOG de Unity [{data.get('level')}]: {data.get('message')}")
                else:
                    # Es una respuesta a un comando, la guardamos y notificamos al otro endpoint
                    manager.set_response(message)
            except json.JSONDecodeError:
                # Si no es un JSON válido, probablemente es una respuesta a un comando
                manager.set_response(message)

    except WebSocketDisconnect:
        manager.disconnect()
        print("Unity Editor Desconectado.")


@app.post("/unity/run-command", response_model=UnityCommandResponse)
async def run_command_in_unity(command_request: UnityCommandRequest):
    if manager.active_connection is None:
        return UnityCommandResponse(success=False, error="Unity Editor no está conectado.")

    try:
        # 1. Preparamos el evento para esperar una nueva respuesta
        manager.response_event.clear()
        manager.last_response = None

        # 2. Enviamos el comando a Unity
        await manager.send_to_unity(command_request.json())
        
        # 3. Esperamos a que el evento se active (timeout de 30 segundos)
        await asyncio.wait_for(manager.response_event.wait(), timeout=30.0)

        # 4. Una vez que el evento se activa, la respuesta está en last_response
        if manager.last_response:
            response_data = json.loads(manager.last_response)
            return UnityCommandResponse(**response_data)
        else:
            return UnityCommandResponse(success=False, error="No se recibió respuesta de Unity.")
        
    except asyncio.TimeoutError:
        return UnityCommandResponse(success=False, error="Timeout: Unity no respondió en 30 segundos.")
    except Exception as e:
        return UnityCommandResponse(success=False, error=f"Error de comunicación: {str(e)}")