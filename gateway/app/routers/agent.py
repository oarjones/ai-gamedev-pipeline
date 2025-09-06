"""Agent CLI runner endpoints.

Endpoints:
- POST /api/v1/agent/start?projectId=...
- POST /api/v1/agent/stop
- GET  /api/v1/agent/status
- POST /api/v1/agent/send

Notes:
- Uses a temporary echo CLI. Replace in AgentRunner._build_command() when real CLI is ready.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict

from app.services.agent_runner import agent_runner
from app.services.projects import project_service


router = APIRouter()


class SendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=0, description="Text payload to send to the agent CLI")


@router.post("/start")
async def start_agent(projectId: str) -> JSONResponse:  # query param required
    """Start the agent process using the specified project as cwd."""
    # Validate project exists via registry and derive the folder
    project = project_service.get_project(projectId)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{projectId}' not found"
        )
    cwd = Path("projects") / project.id
    try:
        status_obj = await agent_runner.start(cwd)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": f"Agent started in '{cwd}'",
            "pid": status_obj.pid,
            "running": status_obj.running,
            "cwd": status_obj.cwd,
        },
    )


@router.post("/stop")
async def stop_agent() -> JSONResponse:
    """Stop the agent process if running."""
    try:
        status_obj = await agent_runner.stop()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": "Agent stopped",
            "pid": status_obj.pid,
            "running": status_obj.running,
            "cwd": status_obj.cwd,
        },
    )


@router.get("/status")
async def agent_status() -> JSONResponse:
    """Return agent running status and pid."""
    status_obj = agent_runner.status()
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "running": status_obj.running,
            "pid": status_obj.pid,
            "cwd": status_obj.cwd,
        },
    )


@router.post("/send")
async def send_to_agent(payload: SendRequest, request: Request) -> JSONResponse:
    """Send text to the agent and return the CLI response (echo for now)."""
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    try:
        out = await agent_runner.send(payload.text, correlation_id=correlation_id)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "correlationId": correlation_id,
            "output": out,
        },
    )
