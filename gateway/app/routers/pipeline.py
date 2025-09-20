"""Pipeline orchestration endpoints: start and cancel."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from app.services import config_service, deps_manager, health_service
from app.services.process_manager import process_manager
from app.services.unified_agent import agent as unified_agent
from app.ws.events import manager
from app.models import Envelope, EventType


router = APIRouter()


def _venv_python_path(venv_path: Path) -> Path:
    from sys import platform
    if platform.startswith("win"):
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def _broadcast(project_id: Optional[str], payload: Dict[str, Any]) -> None:
    try:
        env = Envelope(type=EventType.UPDATE, project_id=project_id or "", payload={"source": "pipeline", **payload})
        # Fire-and-forget
        import asyncio
        asyncio.create_task(manager.broadcast_project(project_id or "", env.model_dump_json(by_alias=True)))
    except Exception:
        pass


@router.post("/pipeline/start")
async def pipeline_start(payload: Dict[str, Any]) -> Dict[str, Any]:
    project_id = str(payload.get("project_id") or "").strip()
    agent_type = (payload.get("agentType") or "").strip().lower() or None
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    steps: List[Dict[str, Any]] = []
    def step(name: str, ok: bool, detail: str = "") -> None:
        steps.append({"name": name, "ok": bool(ok), "detail": detail})
        _broadcast(project_id, {"event": name, "status": "completed" if ok else "error", "detail": detail})

    # 1) Validate config
    cfg = config_service.get_all(mask_secrets=False)
    ok, errors = config_service.validate(cfg)
    if not ok:
        step("validate-config", False, f"errors: {errors}")
        raise HTTPException(status_code=400, detail=str(errors))
    step("validate-config", True, "ok")

    # 2) Venv + minimal deps
    deps_cfg = cfg.get("dependencies", {}) or {}
    venv_path = Path(str(deps_cfg.get("venvDefault") or "venvs/agp"))
    py_path = _venv_python_path(venv_path)
    created = False
    if not py_path.exists():
        try:
            deps_manager.createVenv(str(venv_path), project_id)
            created = True
        except Exception as e:
            step("create-venv", False, str(e))
            raise HTTPException(status_code=500, detail=f"venv error: {e}")
    step("create-venv", True, "exists" if not created else "created")

    # Minimal packages
    pkgs = list(deps_cfg.get("minimalPackages") or ["fastapi", "uvicorn", "websockets"])
    try:
        status = deps_manager.checkInstalled(str(venv_path), pkgs)
        missing = [s["name"] for s in status if not s.get("installed")]
        if missing:
            deps_manager.installPackages(str(venv_path), missing, project_id)
            step("install-minimal", True, f"installed: {missing}")
        else:
            step("install-minimal", True, "already installed")
    except Exception as e:
        step("install-minimal", False, str(e))
        raise HTTPException(status_code=500, detail=f"deps error: {e}")

    # 3) Start system sequence (idempotent)
    try:
        statuses = process_manager.start_sequence(project_id)
        step("system-start", True, "ok")
    except Exception as e:
        step("system-start", False, str(e))
        raise HTTPException(status_code=500, detail=f"system error: {e}")

    # 4) Self-test (non-blocking for final ok)
    health = await health_service.get_health()
    step("health-check", bool(health.get("ok")), "ok" if health.get("ok") else "issues")
    selftest = await health_service.run_selftest(project_id)
    step("self-test", bool(selftest.get("passed")), "ok" if selftest.get("passed") else "failed")

    # 5) Start agent
    try:
        default_agent = (cfg.get("agents", {}) or {}).get("default") or "gemini"
        agent = agent_type or default_agent
        cwd = Path("gateway/projects") / project_id
        st = await unified_agent.start(cwd, agent)
        step("agent-start", bool(st.running), f"{agent}")
    except Exception as e:
        step("agent-start", False, str(e))
        raise HTTPException(status_code=500, detail=f"agent error: {e}")

    return {"ok": all(s.get("ok") for s in steps), "steps": steps, "health": health, "selftest": selftest}


@router.post("/pipeline/cancel")
async def pipeline_cancel() -> Dict[str, Any]:
    try:
        await unified_agent.stop()
    except Exception:
        pass
    try:
        process_manager.stopAll()
    except Exception:
        pass
    _broadcast(None, {"event": "cancelled"})
    return {"cancelled": True}

