"""Configuration endpoints.

- GET /config: returns current (masked) config
- POST /config: validates and persists partial config
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.services import config_service


router = APIRouter()


@router.get("/config")
async def get_config() -> Dict[str, Any]:
    return config_service.get_all(mask_secrets=True)


@router.post("/config")
async def update_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return config_service.update(payload or {})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

