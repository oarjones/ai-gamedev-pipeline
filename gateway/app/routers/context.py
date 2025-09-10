"""Context endpoints for scene state and screenshots per project."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, FileResponse

from app.services.projects import project_service
from app.services.mcp_client import mcp_client
from app.models import Envelope, EventType
from app.ws.events import manager


router = APIRouter()


def _project_context_dir(project_id: str) -> Path:
    p = Path("projects") / project_id / "context"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _sha256_file(path: Path) -> Optional[str]:
    try:
        if not path.exists() or not path.is_file():
            return None
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _screenshot_file(project_id: str) -> Path:
    return _project_context_dir(project_id) / "last_screenshot.png"


def _scene_file(project_id: str) -> Path:
    return _project_context_dir(project_id) / "last_scene.json"


@router.get("/context/state")
async def get_context_state(projectId: str) -> JSONResponse:
    project = project_service.get_project(projectId)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{projectId}' not found")

    scene_path = _scene_file(projectId)
    shot_path = _screenshot_file(projectId)
    scene_etag = _sha256_file(scene_path)
    shot_etag = _sha256_file(shot_path)

    data = {
        "projectId": projectId,
        "scene": {
            "exists": scene_etag is not None,
            "etag": scene_etag,
            "url": f"/api/v1/context/scene/file?projectId={projectId}" if scene_etag else None,
        },
        "screenshot": {
            "exists": shot_etag is not None,
            "etag": shot_etag,
            "url": f"/api/v1/context/screenshot/file?projectId={projectId}" if shot_etag else None,
        },
    }
    return JSONResponse(status_code=status.HTTP_200_OK, content=data)


@router.get("/context/screenshot")
async def get_screenshot_meta(projectId: str) -> JSONResponse:
    shot_path = _screenshot_file(projectId)
    etag = _sha256_file(shot_path)
    if etag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screenshot not found")
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "projectId": projectId,
            "etag": etag,
            "url": f"/api/v1/context/screenshot/file?projectId={projectId}",
        },
    )


@router.get("/context/screenshot/file")
async def get_screenshot_file(projectId: str) -> FileResponse:
    path = _screenshot_file(projectId)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screenshot not found")
    return FileResponse(path, media_type="image/png")


@router.get("/context/scene/file")
async def get_scene_file(projectId: str) -> FileResponse:
    path = _scene_file(projectId)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")
    return FileResponse(path, media_type="application/json")


_PNG_1x1 = bytes.fromhex(
    "89504E470D0A1A0A0000000D4948445200000001000000010802000000907753DE0000000A49444154789C6360000002000154AFA64A0000000049454E44AE426082"
)


@router.post("/context/screenshot")
async def request_screenshot(request: Request, projectId: str) -> JSONResponse:
    project = project_service.get_project(projectId)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{projectId}' not found")

    corr = request.headers.get("X-Correlation-Id")
    # Ask Unity to capture a screenshot via MCP
    try:
        res = await mcp_client.capture_screenshot(project_id=projectId)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to request screenshot: {e}")

    # Try to locate the produced file path in response
    src_path: Optional[Path] = None
    try:
        # common locations: result.path, payload.path, path
        for key in ("result", "payload"):
            if isinstance(res.get(key), dict) and isinstance(res[key].get("path"), str):
                src_path = Path(res[key]["path"]).resolve()
                break
        if src_path is None and isinstance(res.get("path"), str):
            src_path = Path(res["path"]).resolve()
    except Exception:
        src_path = None

    dst = _screenshot_file(projectId)
    dst.parent.mkdir(parents=True, exist_ok=True)

    wrote = False
    if src_path and src_path.exists():
        try:
            data = src_path.read_bytes()
            dst.write_bytes(data)
            wrote = True
        except Exception:
            wrote = False

    if not wrote:
        # Fallback: create a tiny placeholder PNG so UI can refresh
        try:
            dst.write_bytes(_PNG_1x1)
            wrote = True
        except Exception:
            pass

    etag = _sha256_file(dst) if wrote else None
    payload = {
        "kind": "screenshot",
        "etag": etag,
        "url": f"/api/v1/context/screenshot/file?projectId={projectId}" if etag else None,
        "raw": res,
    }

    # Broadcast scene/context update (avoid binary payloads)
    try:
        env = Envelope(type=EventType.SCENE, projectId=projectId, payload=payload, correlationId=corr)
        await manager.broadcast_project(projectId, env.model_dump_json(by_alias=True))
    except Exception:
        pass

    code = status.HTTP_200_OK if wrote else status.HTTP_202_ACCEPTED
    return JSONResponse(status_code=code, content={"status": "updated" if wrote else "pending", **payload})

