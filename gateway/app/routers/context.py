from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from gateway.app.services.context_service import context_service
from gateway.app.utils.params import normalize_project_id

router = APIRouter()

class CreateContextRequest(BaseModel):
    content: Dict[str, Any]
    scope: str = 'global'
    task_id: int | None = None

@router.get("/context", summary="Get active context for a scope")
async def get_active_context(
    project_id: str = Query(..., alias="projectId"),
    scope: str = 'global'
):
    context = context_service.get_active_context(project_id=project_id, scope=scope)
    if not context:
        raise HTTPException(status_code=404, detail=f"{scope.capitalize()} context not found for project {project_id}")
    return context

@router.post("/context", summary="Create a new context version")
async def create_context(
    request: CreateContextRequest,
    project_id: str = Query(..., alias="projectId"),
):
    try:
        new_context = context_service.create_context(
            project_id=project_id,
            content=request.content,
            scope=request.scope,
            task_id=request.task_id,
            created_by="user"
        )
        return {"version": new_context.version, "scope": new_context.scope}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/context/history", summary="Get context history for a scope")
async def get_context_history(
    project_id: str = Query(..., alias="projectId"),
    scope: str = 'global'
):
    history = context_service.list_context_history(project_id=project_id, scope=scope)
    return [{ "version": h.version, "created_at": h.created_at, "created_by": h.created_by } for h in history]

@router.post("/context/generate", summary="Trigger automatic context generation")
async def generate_context(
    project_id: str = Query(..., alias="projectId"),
    last_task_id: int | None = None
):
    # This is a simplified version. A real implementation might need more info.
    if not last_task_id:
        raise HTTPException(status_code=400, detail="last_task_id is required for generation")
    try:
        new_context = context_service.generate_context_after_task(project_id, last_task_id)
        return new_context
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
