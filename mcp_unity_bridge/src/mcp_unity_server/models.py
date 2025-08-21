from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List

class UnityCommandRequest(BaseModel):
    command: str = Field(..., description="El fragmento de código C# a ejecutar en el editor de Unity.")
    additional_references: Optional[List[str]] = Field(None, description="Lista de nombres de ensamblados (ej. 'UnityEngine.UI.dll') para incluir en la compilación.")
    context: Optional[Dict[str, Any]] = Field(None, description="Datos de contexto opcionales para seguimiento.")

class UnityCommandResponse(BaseModel):
    success: bool = Field(..., description="Indica si la ejecución del comando tuvo éxito.")
    output: Optional[str] = Field(None, description="La salida de la consola o el valor de retorno del comando.")
    error: Optional[str] = Field(None, description="Mensaje de error si la ejecución falló.")