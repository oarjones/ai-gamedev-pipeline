import uuid
import requests
import json
from fastapi import FastAPI, Request, Response
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
        
        # Ahora enviamos el objeto completo de la petición (incluyendo las referencias)
        response = requests.post(
            unity_url,
            json=request.dict(), # Usamos .dict() para serializar el modelo Pydantic completo
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()

        # --- CORRECCIÓN ---
        # response.json() ya decodifica el JSON a un diccionario de Python.
        # No es necesario usar json.loads() de nuevo.
        command_result_data = response.json()
        
        return UnityCommandResponse(
            success=command_result_data.get('Success', False),
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