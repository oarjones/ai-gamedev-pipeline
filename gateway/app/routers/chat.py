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

class ChatNewRequest(BaseModel):
    session_id: str = Field(description="The session ID to clean up")


@router.post("/send")
async def chat_send(request: Request, project_id: str, session_id: str, payload: ChatSendRequest) -> JSONResponse:
    # Validate project exists
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")

    # The chat_service worker will now handle starting the wrapper service if needed.

    corr_id = request.headers.get("X-Correlation-Id")
    try:
        # Pass both project_id (for persistence) and session_id (for context)
        ack = await chat_service.send_user_message(
            project_id=project_id, 
            session_id=session_id, 
            text=payload.text, 
            correlation_id=corr_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "queued", **ack})


@router.post("/new")
async def chat_new(payload: ChatNewRequest) -> JSONResponse:
    """Cleans up a chat session to allow starting a new one."""
    try:
        await chat_service.cleanup_session(payload.session_id)
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "session_cleaned"})
    except Exception as e:
        # It's not critical if this fails (e.g., session already gone)
        # Log it and return success.
        logging.warning(f"Could not clean up session {payload.session_id}: {e}")
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "session_cleanup_failed_but_ok"})


@router.get("/history")
async def chat_history(project_id: str, limit: Optional[int] = None, task_id: Optional[int] = None) -> JSONResponse:
    """Get chat history for active task or specific task_id."""
    # Validate project exists
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")

    try:
        items = await chat_service.get_history(project_id, limit=limit, task_id=task_id)

        # Get active task info for response
        from app.db import db
        active_task_id = db.get_active_task_id(project_id)

        return JSONResponse(status_code=status.HTTP_200_OK, content={
            "items": items,
            "active_task_id": active_task_id,
            "filtered_by_task": task_id or active_task_id
        })
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/history/all")
async def chat_history_all(project_id: str, limit: Optional[int] = None) -> JSONResponse:
    """Get complete chat history for all tasks (read-only)."""
    # Validate project exists
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")

    try:
        items = await chat_service.get_all_history(project_id, limit=limit)
        return JSONResponse(status_code=status.HTTP_200_OK, content={
            "items": items,
            "read_only": True,
            "note": "Complete history across all tasks"
        })
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/active-context")
async def get_active_context(project_id: str) -> JSONResponse:
    """Get information about active task and chat context."""
    # Validate project exists
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")

    try:
        from app.db import db

        # Get active task
        active_task_id = db.get_active_task_id(project_id)
        active_task = None

        if active_task_id:
            active_task = db.get_task(active_task_id)

        return JSONResponse(status_code=status.HTTP_200_OK, content={
            "project_id": project_id,
            "active_task_id": active_task_id,
            "active_task": {
                "id": active_task.id,
                "code": active_task.code,
                "title": active_task.title,
                "status": active_task.status,
                "description": active_task.description
            } if active_task else None,
            "chat_context": "Messages are associated with the active task",
            "note": "Chat will show messages for the active task only"
        })
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))