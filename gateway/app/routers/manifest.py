"""Project manifest and plan endpoints (wizard + plan propose/approve)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

from app.services.unified_agent import agent as unified_agent

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


router = APIRouter()


def _manifest_path(project_id: str) -> Path:
    return Path("projects") / project_id / ".agp" / "project_manifest.yaml"


def _plan_path(project_id: str) -> Path:
    return Path("projects") / project_id / "plan_of_record.yaml"


@router.get("/{project_id}/manifest")
async def get_manifest(project_id: str) -> Dict[str, Any]:
    p = _manifest_path(project_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail="manifest not found")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) if yaml else {}
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(e))
    return data or {}


@router.post("/{project_id}/manifest")
async def save_manifest(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    # Basic validation
    mf = payload or {}
    required = ["pitch", "genre", "mechanics", "visual_style"]
    missing = [k for k in required if not str(mf.get(k, "")).strip()]
    if missing:
        raise HTTPException(status_code=400, detail=f"missing fields: {', '.join(missing)}")
    # Add version field
    mf.setdefault("version", "1.0")
    p = _manifest_path(project_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        if yaml:
            p.write_text(yaml.safe_dump(mf, sort_keys=False, allow_unicode=True), encoding="utf-8")
        else:  # pragma: no cover
            p.write_text(json.dumps(mf, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"saved": True, "path": str(p)}


def _build_plan_prompt(manifest: Dict[str, Any]) -> str:
    def g(key: str) -> str:
        v = manifest.get(key)
        return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    header = (
        "Eres un AI GameDev Lead. Usa únicamente tools vía MCP cuando lo indiques. "
        "Propón un Plan de Desarrollo estructurado y seguro. Responde SOLO con JSON válido."
    )
    spec = {
        "phases": ["..."],
        "tasks": [{"id": "T-001", "title": "...", "desc": "...", "deps": ["T-000"], "acceptance": "..."}],
        "risks": ["..."],
        "deliverables": ["..."]
    }
    manifest_txt = json.dumps(manifest, ensure_ascii=False, indent=2)
    return (
        f"{header}\n\n"
        f"Manifest:\n{manifest_txt}\n\n"
        f"Formato requerido (ejemplo):\n{json.dumps(spec, ensure_ascii=False, indent=2)}\n\n"
        "Devuelve SOLO el JSON con el plan (sin texto adicional)."
    )


@router.post("/{project_id}/plan/propose")
async def propose_plan(project_id: str) -> Dict[str, Any]:
    p = _manifest_path(project_id)
    if not p.exists():
        raise HTTPException(status_code=400, detail="manifest not found; save it first")
    try:
        manifest = yaml.safe_load(p.read_text(encoding="utf-8")) if yaml else {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    prompt = _build_plan_prompt(manifest or {})
    # Ensure agent running in project's cwd
    from pathlib import Path as P
    cwd = P("projects") / project_id
    try:
        await unified_agent.start(cwd, "gemini")
        corr = "plan-proposal"
        await unified_agent.send(prompt, correlation_id=corr)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"queued": True, "correlationId": "plan-proposal"}


@router.post("/{project_id}/plan")
async def save_plan(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    # Accepts already-parsed JSON plan; saves as YAML plan_of_record.yaml
    plan = payload.get("plan")
    if not isinstance(plan, dict):
        raise HTTPException(status_code=400, detail="plan must be an object")
    plan.setdefault("version", "1.0")
    out = _plan_path(project_id)
    try:
        if yaml:
            out.write_text(yaml.safe_dump(plan, sort_keys=False, allow_unicode=True), encoding="utf-8")
        else:
            out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"saved": True, "path": str(out)}

