"""System process orchestration endpoints (/api/v1/system)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.services.process_manager import process_manager
from app.ws.events import manager
from app.models import Envelope, EventType
from app.services.projects import project_service



router = APIRouter()


@router.post("/system/start")
async def system_start(payload: Dict[str, Any]) -> Dict[str, Any]:
    project_id: Optional[str] = payload.get("project_id")
    # If project_id not provided, try active project
    if not project_id:
        active = project_service.get_active_project()
        project_id = active.id if active else None
    try:
        statuses = process_manager.start_sequence(project_id)
        # Broadcast update
        try:
            env = Envelope(type=EventType.UPDATE, project_id=project_id or "", payload={"source": "system", "event": "started", "statuses": statuses})
            await manager.broadcast_project(project_id or "", env.model_dump_json(by_alias=True))
        except Exception:
            pass
        return {"ok": True, "statuses": statuses}
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/system/stop")
async def system_stop(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    try:
        process_manager.stopAll()
        try:
            env = Envelope(type=EventType.UPDATE, project_id=payload.get("project_id") if payload else None, payload={"source": "system", "event": "stopped"})
            await manager.broadcast_project((payload or {}).get("project_id") or "", env.model_dump_json(by_alias=True))
        except Exception:
            pass
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/status")
async def system_status() -> List[Dict[str, Any]]:
    return process_manager.status()
