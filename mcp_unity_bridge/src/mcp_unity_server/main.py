import uuid
import requests
import json
from fastapi import FastAPI, Request, Response, HTTPException
from .models import UnityCommandRequest, UnityCommandResponse
from .config import get_settings

app = FastAPI(
    title="MCP Unity Bridge",
    description="Un servidor intermediario para que un agente IA se comunique con el editor de Unity.",
    version="0.1.0",
)

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = request.headers.get('X-Correlation-ID') or str(uuid.uuid4())
    response = await call_next(request)
    response.headers['X-Correlation-ID'] = correlation_id
    return response

@app.get("/health", tags=["Monitoring"])
async def health_check():
    return {"status": "ok"}

@app.post("/unity/run-command", response_model=UnityCommandResponse, tags=["Unity Editor"])
async def run_unity_command(request: UnityCommandRequest):
    """
    Recibe un comando C#, lo envía al editor de Unity para su ejecución y devuelve el resultado.
    """
    settings = get_settings()
    unity_url = f"{settings['unity_editor_url'].strip('/')}/execute/"

    try:
        response = requests.post(
            unity_url,
            json={"command": request.command},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()

        # --- CORRECCIÓN AQUÍ ---
        # La respuesta de Unity es un string que contiene un JSON.
        # response.json() lo decodifica a un string. Necesitamos parsear ese string.
        command_result_data = json.loads(response.json())
        
        return UnityCommandResponse(
            success=command_result_data.get('Success', False),
            # El campo en C# es 'ReturnValue', asegúrate de que coincida aquí.
            output=command_result_data.get('ReturnValue'), 
            error=command_result_data.get('ErrorMessage')
        )

    except requests.exceptions.RequestException as e:
        return UnityCommandResponse(
            success=False,
            error=f"Error de comunicación con el editor de Unity: {str(e)}"
        )
    except json.JSONDecodeError as e:
        return UnityCommandResponse(
            success=False,
            error=f"Error al decodificar la respuesta de Unity: {str(e)}. Respuesta recibida: {response.text}"
        )