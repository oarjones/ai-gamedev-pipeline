import uuid
from fastapi import FastAPI, Request, Response
from .models import UnityCommandRequest, UnityCommandResponse

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
    Recibe un comando C# y (en el futuro) lo enviará al editor de Unity para su ejecución.
    """
    # --- Lógica Placeholder para el Módulo 1 ---
    # En el Módulo 4, esto será reemplazado por una llamada real al servidor de Unity.
    print(f"Comando recibido (simulado): {request.command}")
    
    return UnityCommandResponse(
        success=True,
        output=f"Comando '{request.command[:30]}...' recibido por el MCP. La ejecución real no está implementada aún."
    )