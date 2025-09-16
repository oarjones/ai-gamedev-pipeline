"""Unified Agent runner endpoints.

Endpoints:
- POST /api/v1/agent/start?project_id=...
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
from app.services.context_service import context_service
from app.db import db
import json
import hashlib


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
async def start_agent(payload: dict | None = None, project_id: str | None = None) -> JSONResponse:
    """Start the agent using the specified project and agentType.

    Accepts either JSON body { project_id, agentType } or legacy query param project_id.
    """
    payload = payload or {}
    pid = project_id or payload.get("project_id")
    provider = (payload.get("provider") or "gemini_cli").lower()
    # Map provider to agent_type for current implementation
    agent_type = "gemini" if provider == "gemini_cli" else (payload.get("agentType") or "gemini").lower()
    if not pid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project_id is required")
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
        env = Envelope(type=EventType.UPDATE, project_id=project.id, payload={"source": "agent", "event": "started", "agentType": status_obj.agentType})
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
        # We don't know project_id; omit or use last known via status if needed
        env = Envelope(type=EventType.UPDATE, project_id=None, payload={"source": "agent", "event": "stopped"})
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
        # Build enriched prompt with project/task context
        project_id = payload.sessionId
        enriched = _build_enriched_prompt(project_id, payload.question)

        # Broadcast user message first so UI shows it immediately
        try:
            env_user = Envelope(type=EventType.CHAT, project_id=payload.sessionId, payload={"role": "user", "content": payload.question})
            await manager.broadcast_project(payload.sessionId, env_user.model_dump_json(by_alias=True))
        except Exception:
            pass

        # Send enriched prompt to the agent
        answer, error = unified_agent.ask_one_shot(payload.sessionId, enriched)

        # Broadcast agent answer if present
        if answer:
            try:
                env_ai = Envelope(type=EventType.CHAT, project_id=payload.sessionId, payload={"role": "agent", "content": answer})
                await manager.broadcast_project(payload.sessionId, env_ai.model_dump_json(by_alias=True))
            except Exception:
                pass
        # Broadcast error if no answer and error present
        elif error:
            try:
                env_err = Envelope(type=EventType.ERROR, project_id=payload.sessionId, payload={"message": error})
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


# --- Context injection helpers ---
_PROMPT_CACHE: dict[str, dict] = {}


def _to_json_s(obj: object, max_len: int) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        s = str(obj)
    if len(s) > max_len:
        return s[: max_len - 20] + "\n... [truncated]"
    return s


def _hash_obj(obj: object) -> str:
    try:
        data = json.dumps(obj, ensure_ascii=False, sort_keys=True)
    except Exception:
        data = str(obj)
    return hashlib.sha1(data.encode("utf-8", errors="ignore")).hexdigest()


def _build_enriched_prompt(project_id: str, user_question: str) -> str:
    # Defaults
    global_ctx: dict | None = None
    task_ctx: dict | None = None
    task_meta: dict | None = None

    try:
        proj = project_service.get_project(project_id)
        if proj is None:
            logger.info("[/agent/ask] project '%s' not found; sending raw question", project_id)
            return user_question

        # Contexts
        try:
            global_ctx = context_service.get_active_context(project_id, 'global')
        except Exception as e:
            logger.warning("[/agent/ask] failed to load global context: %s", e)

        current_task_id = getattr(proj, "current_task_id", None)
        if current_task_id:
            try:
                t = db.get_task(int(current_task_id))
                if t:
                    task_meta = {
                        "codigo": t.code or t.task_id,
                        "titulo": t.title,
                        "descripcion": t.description,
                        "criterios_aceptacion": t.acceptance,
                        "estado": t.status,
                    }
            except Exception as e:
                logger.warning("[/agent/ask] failed to load current task meta: %s", e)
            try:
                task_ctx = context_service.get_active_context(project_id, 'task', task_id=int(current_task_id))
            except Exception as e:
                logger.warning("[/agent/ask] failed to load task context: %s", e)

        # Caching key
        key = "|".join(
            [
                project_id,
                _hash_obj(global_ctx or {}),
                _hash_obj(task_ctx or {}),
                _hash_obj(task_meta or {}),
            ]
        )
        cached = _PROMPT_CACHE.get(project_id)
        if cached and cached.get("key") == key:
            prefix = cached.get("prefix") or ""
            logger.debug("[/agent/ask] using cached prompt prefix for project=%s", project_id)
        else:
            # Budgets for context length
            max_global = 3500
            max_task_ctx = 2500
            g_json = _to_json_s(global_ctx or {}, max_global) if global_ctx else "{}"
            t_json = _to_json_s(task_ctx or {}, max_task_ctx) if task_ctx else "{}"
            task_block = ""
            if task_meta:
                try:
                    task_block = (
                        f"codigo: {task_meta.get('codigo') or ''}\n"
                        f"titulo: {task_meta.get('titulo') or ''}\n"
                        f"descripcion: {task_meta.get('descripcion') or ''}\n"
                        f"criterios: {task_meta.get('criterios_aceptacion') or ''}\n"
                    )
                except Exception:
                    task_block = ""

            prefix = (
                "=== CONTEXTO GLOBAL DEL PROYECTO ===\n"
                f"{g_json}\n\n"
                "=== TAREA ACTUAL ===\n"
                f"{task_block if task_block else '(no hay tarea activa)'}\n\n"
                "=== CONTEXTO DE LA TAREA ===\n"
                f"{t_json if task_ctx else '(sin contexto de tarea activo)'}\n\n"
            )
            _PROMPT_CACHE[project_id] = {"key": key, "prefix": prefix}

        # Metrics/logging
        try:
            glen = len(json.dumps(global_ctx or {})) if global_ctx else 0
            tlen = len(json.dumps(task_ctx or {})) if task_ctx else 0
            logger.info(
                "[/agent/ask] injecting context: global_bytes=%s task_bytes=%s task_meta=%s",
                glen,
                tlen,
                bool(task_meta),
            )
        except Exception:
            pass

        # Final prompt
        final = (
            prefix
            + "=== PREGUNTA DEL USUARIO ===\n"
            + user_question
            + "\n\nPor favor responde considerando todo el contexto anterior."
        )
        return final
    except Exception as e:
        logger.warning("[/agent/ask] context injection failed; falling back to raw question: %s", e)
        return user_question
