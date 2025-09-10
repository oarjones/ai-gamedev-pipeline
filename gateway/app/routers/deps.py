"""Dependencies and virtual environments endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from app.services import deps_manager


router = APIRouter()


@router.post("/venv/create")
async def venv_create(payload: Dict[str, Any]) -> Dict[str, Any]:
    path = str(payload.get("path") or "").strip()
    project_id = str(payload.get("projectId") or "system")
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    try:
        return deps_manager.createVenv(path, project_id=project_id)
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deps/install")
async def deps_install(payload: Dict[str, Any]) -> Dict[str, Any]:
    venv_path = str(payload.get("venvPath") or "").strip()
    req_path = payload.get("requirementsPath")
    packages = payload.get("packages")
    project_id = str(payload.get("projectId") or "system")
    if not venv_path:
        raise HTTPException(status_code=400, detail="venvPath is required")
    if not req_path and not packages:
        raise HTTPException(status_code=400, detail="requirementsPath or packages required")
    try:
        if req_path:
            return deps_manager.installFromRequirements(venv_path, str(req_path), project_id=project_id)
        else:
            return deps_manager.installPackages(venv_path, list(packages or []), project_id=project_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deps/check")
async def deps_check(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    venv_path = str(payload.get("venvPath") or "").strip()
    packages = list(payload.get("packages") or [])
    if not venv_path:
        raise HTTPException(status_code=400, detail="venvPath is required")
    if not packages:
        raise HTTPException(status_code=400, detail="packages is required")
    try:
        return deps_manager.checkInstalled(venv_path, packages)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

