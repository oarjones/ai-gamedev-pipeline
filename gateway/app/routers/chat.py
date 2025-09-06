"""Chat endpoints: send message and optional history retrieval."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict

from app.services.chat import chat_service
from app.services.projects import project_service


router = APIRouter()


class ChatSendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, description="User message to send to agent")


@router.post("/send")
async def chat_send(request: Request, projectId: str, payload: ChatSendRequest) -> JSONResponse:
    # Validate project exists
    project = project_service.get_project(projectId)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{projectId}' not found")

    # Ensure agent is running
    from app.services.agent_runner import agent_runner
    if not agent_runner.status().running:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent is not running for this project")

    corr_id = request.headers.get("X-Correlation-Id")
    try:
        ack = await chat_service.send_user_message(projectId, payload.text, correlation_id=corr_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "queued", **ack})


@router.get("/history")
async def chat_history(projectId: str, limit: Optional[int] = None) -> JSONResponse:
    # Validate project exists
    project = project_service.get_project(projectId)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{projectId}' not found")

    try:
        items = await chat_service.get_history(projectId, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return JSONResponse(status_code=status.HTTP_200_OK, content={"items": items})

