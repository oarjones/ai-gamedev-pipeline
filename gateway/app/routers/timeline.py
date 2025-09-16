"""Timeline endpoints for listing and revert stub."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import JSONResponse

from app.services.timeline import timeline_service
from app.services.projects import project_service


router = APIRouter()


@router.get("")
async def list_timeline(project_id: str = Query(..., alias="project_id"), limit: Optional[int] = 100) -> JSONResponse:
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")

    items = await timeline_service.list(project_id, limit=int(limit or 100))
    return JSONResponse(status_code=status.HTTP_200_OK, content={"items": items})


@router.post("/{event_id}/revert")
async def revert_timeline(event_id: int) -> JSONResponse:
    res = await timeline_service.revert(event_id)
    if res.get("status") == "error":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=res.get("error", "unknown"))

    code = status.HTTP_200_OK if res.get("status") == "reverted" else status.HTTP_202_ACCEPTED
    return JSONResponse(status_code=code, content=res)

