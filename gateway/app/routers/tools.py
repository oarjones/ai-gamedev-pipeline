"""Tools listing and action execution endpoints."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict

from app.services.tools import tools_registry
from app.services.projects import project_service
from app.services.actions import action_orchestrator


router = APIRouter()


@router.get("/tools")
async def list_tools() -> JSONResponse:
    items = [t.model_dump() for t in tools_registry.list_tools()]
    return JSONResponse(status_code=status.HTTP_200_OK, content={"items": items})


class ExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    toolId: str = Field(min_length=1)
    input: Dict[str, Any] = Field(default_factory=dict)


@router.post("/actions/execute")
async def execute_action(request: Request, project_id: str, payload: ExecuteRequest) -> JSONResponse:
    # Validate project
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")

    # Validate tool and input
    try:
        tools_registry.validate_input(payload.toolId, payload.input)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    corr_id = request.headers.get("X-Correlation-Id")
    # Size limit (64KB) for input payload
    try:
        import json as _json
        if len(_json.dumps(payload.input, ensure_ascii=False)) > 64 * 1024:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Input too large")
    except HTTPException:
        raise
    except Exception:
        pass
    # Delegate to orchestrator as a single-step plan
    try:
        res = await action_orchestrator.run_plan(project_id, [{"tool": payload.toolId, "args": payload.input}], correlation_id=corr_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return JSONResponse(status_code=status.HTTP_200_OK, content=res)
