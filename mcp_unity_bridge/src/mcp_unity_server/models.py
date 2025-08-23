
from typing import List, Dict, Any, Literal, Union, Optional
from pydantic import BaseModel

class CommandRequest(BaseModel):
    command: str
    additional_references: Optional[List[str]] = None

class QueryRequest(BaseModel):
    type: Literal['query']
    action: str
    params: Dict[str, Any]
    request_id: Optional[str] = None  # Added by the server

class UnityResponse(BaseModel):
    request_id: str
    status: Literal['success', 'error']
    payload: str

class BaseMessage(BaseModel):
    type: str

class Message(BaseModel):
    type: Literal['command', 'query']
    data: Union[CommandRequest, QueryRequest]

class UnityMessage(BaseModel):
    """
    Modelo genérico para la comunicación, compatible con el cliente C#.
    """
    type: str  # 'command' o 'query'
    action: Optional[str] = None
    payload: str # Un JSON string que contiene los datos específicos
    request_id: Optional[str] = None
