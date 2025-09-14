"""Unified Agent runner endpoints.

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
import logging
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict

from app.services.unified_agent import agent as unified_agent
from app.ws.events import manager
from app.models import Envelope, EventType
from app.services.projects import project_service
from app.services.adapter_lock import status as adapter_status


router = APIRouter()
logger = logging.getLogger(__name__)


class SendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=0, description="Text payload to send to the agent CLI")


class AskOneShotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sessionId: str = Field(min_length=1, description="Session identifier used to create/select the working directory")
    question: str = Field(min_length=1, description="Prompt to send to the provider in one-shot mode")


@router.post("/start")
async def start_agent(payload: dict | None = None, projectId: str | None = None) -> JSONResponse:
    """Start the agent using the specified project and agentType.

    Accepts either JSON body { projectId, agentType } or legacy query param projectId.
    """
    payload = payload or {}
    pid = projectId or payload.get("projectId")
    provider = (payload.get("provider") or "gemini_cli").lower()
    # Map provider to agent_type for current implementation
    agent_type = "gemini" if provider == "gemini_cli" else (payload.get("agentType") or "gemini").lower()
    if not pid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="projectId is required")
    # Validate project exists via registry and derive the folder
    project = project_service.get_project(pid)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{pid}' not found"
        )
    cwd = Path("projects") / project.id
    try:
        logger.info("[/agent/start] project=%s provider=%s agentType=%s cwd=%s", project.id, provider, agent_type, str(cwd))
        status_obj = await unified_agent.start(cwd, agent_type)
    except FileNotFoundError as e:
        logger.error("[/agent/start] FileNotFoundError: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("[/agent/start] Failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # Broadcast update event (best-effort)
    try:
        env = Envelope(type=EventType.UPDATE, projectId=project.id, payload={"source": "agent", "event": "started", "agentType": status_obj.agentType})
        await manager.broadcast_project(project.id, env.model_dump_json(by_alias=True))
    except Exception:
        pass

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": f"Agent started in '{cwd}'",
            "pid": status_obj.pid,
            "running": status_obj.running,
            "cwd": status_obj.cwd,
            "agentType": status_obj.agentType,
            "provider": provider,
            "lastError": status_obj.lastError,
        },
    )


@router.post("/stop")
async def stop_agent() -> JSONResponse:
    """Stop the agent process if running."""
    try:
        logger.info("[/agent/stop] request received")
        status_obj = await unified_agent.stop()
    except Exception as e:
        logger.error("[/agent/stop] Failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # Broadcast update event (best-effort)
    try:
        # We don't know projectId; omit or use last known via status if needed
        env = Envelope(type=EventType.UPDATE, projectId=None, payload={"source": "agent", "event": "stopped"})
        # No room to broadcast if no project; ignore
    except Exception:
        pass

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": "Agent stopped",
            "pid": status_obj.pid,
            "running": status_obj.running,
            "cwd": status_obj.cwd,
            "agentType": status_obj.agentType,
            "provider": None,
            "lastError": status_obj.lastError,
        },
    )


@router.get("/status")
async def agent_status() -> JSONResponse:
    """Return agent running status and pid."""
    status_obj = unified_agent.status()
    ad = adapter_status()
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "running": status_obj.running,
            "pid": status_obj.pid,
            "cwd": status_obj.cwd,
            "agentType": status_obj.agentType,
            "provider": "gemini_cli" if status_obj.agentType == "gemini" else None,
            "lastError": status_obj.lastError,
            "adapter": {"running": bool(ad.get("running")), "pid": ad.get("pid"), "startedAt": ad.get("startedAt")},
        },
    )


@router.post("/send")
async def send_to_agent(payload: SendRequest, request: Request) -> JSONResponse:
    """Send text to the agent and return the CLI response (echo for now)."""
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    try:
        out = await unified_agent.send(payload.text, correlation_id=correlation_id)
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


@router.post("/ask")
async def ask_one_shot(payload: AskOneShotRequest) -> JSONResponse:
    """Execute a single-turn prompt using the gemini_cli provider (one-shot architecture)."""
    try:
        # Broadcast user message first so UI shows it immediately
        try:
            env_user = Envelope(type=EventType.CHAT, projectId=payload.sessionId, payload={"role": "user", "content": payload.question})
            await manager.broadcast_project(payload.sessionId, env_user.model_dump_json(by_alias=True))
        except Exception:
            pass

        answer, error = unified_agent.ask_one_shot(payload.sessionId, payload.question)

        # Broadcast agent answer if present
        if answer:
            try:
                env_ai = Envelope(type=EventType.CHAT, projectId=payload.sessionId, payload={"role": "agent", "content": answer})
                await manager.broadcast_project(payload.sessionId, env_ai.model_dump_json(by_alias=True))
            except Exception:
                pass
        # Broadcast error if no answer and error present
        elif error:
            try:
                env_err = Envelope(type=EventType.ERROR, projectId=payload.sessionId, payload={"message": error})
                await manager.broadcast_project(payload.sessionId, env_err.model_dump_json(by_alias=True))
            except Exception:
                pass
    except Exception as e:
        logger.exception("[/agent/ask] Failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "sessionId": payload.sessionId,
            "answer": answer,
            "stderr": error,  # treat as warning if answer is present
        },
    )
