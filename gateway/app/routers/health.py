"""Health endpoints: GET /health, POST /health/selftest."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from app.services import health_service


router = APIRouter()


@router.get("/health")
async def get_health() -> Dict[str, Any]:
    return await health_service.get_health()


@router.post("/health/selftest")
async def post_selftest(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    try:
        project_id = (payload or {}).get("project_id")
        return await health_service.run_selftest(project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

