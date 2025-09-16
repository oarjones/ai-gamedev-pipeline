"""Chat endpoints: send message and optional history retrieval."""

from __future__ import annotations

from pathlib import Path
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
async def chat_send(request: Request, project_id: str, payload: ChatSendRequest) -> JSONResponse:
    # Validate project exists
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")

    # Ensure agent is running
    from app.services.unified_agent import agent as unified_agent
    if not unified_agent.status().running:
        #raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent is not running for this project")
        cwd = Path("projects") / project_id
        unified_agent.start(cwd, 'gemini')

    corr_id = request.headers.get("X-Correlation-Id")
    try:
        ack = await chat_service.send_user_message(project_id, payload.text, correlation_id=corr_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "queued", **ack})


@router.get("/history")
async def chat_history(project_id: str, limit: Optional[int] = None) -> JSONResponse:
    # Validate project exists
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")

    try:
        items = await chat_service.get_history(project_id, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return JSONResponse(status_code=status.HTTP_200_OK, content={"items": items})
