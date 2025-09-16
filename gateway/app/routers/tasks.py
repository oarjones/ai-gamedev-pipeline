"""Task Runner endpoints: list/import, propose steps, execute, complete."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.db import db, TaskDB
from app.services.unified_agent import agent as unified_agent

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


router = APIRouter()


@router.get("")
async def list_tasks(project_id: str = Query(..., alias="project_id")) -> List[Dict[str, Any]]:
    rows = db.list_tasks(project_id)
    return [
        {
            "id": t.id,
            "taskId": t.task_id,
            "project_id": t.project_id,
            "title": t.title,
            "description": t.description,
            "acceptance": t.acceptance,
            "status": t.status,
            "deps": json.loads(t.deps_json) if t.deps_json else [],
            "evidence": json.loads(t.evidence_json) if t.evidence_json else [],
        }
        for t in rows
    ]


@router.post("/import")
async def import_tasks(project_id: str = Query(..., alias="project_id")) -> Dict[str, Any]:
    por = Path("projects") / project_id / "plan_of_record.yaml"
    if not por.exists():
        raise HTTPException(status_code=404, detail="plan_of_record.yaml not found")
    try:
        plan = yaml.safe_load(por.read_text(encoding="utf-8")) if yaml else {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    tasks = plan.get("tasks") or []
    created = 0
    for item in tasks:
        try:
            tid = str(item.get("id") or "").strip() or f"T-{created+1:03d}"
            if db.find_task_by_task_id(project_id, tid):
                continue
            t = TaskDB(
                project_id=project_id,
                task_id=tid,
                title=str(item.get("title") or "Untitled"),
                description=str(item.get("desc") or ""),
                acceptance=str(item.get("acceptance") or ""),
                status="pending",
                deps_json=json.dumps(item.get("deps") or []),
                evidence_json=json.dumps([]),
            )
            db.add_task(t)
            created += 1
        except Exception:
            continue
    return {"imported": created}


@router.post("/{id}/propose_steps")
async def propose_steps(id: int) -> Dict[str, Any]:
    t = db.get_task(id)
    if not t:
        raise HTTPException(status_code=404, detail="task not found")
    # Build concise prompt to propose steps
    manifest_p = Path("projects") / t.project_id / ".agp" / "project_manifest.yaml"
    manifest = {}
    if manifest_p.exists() and yaml:
        try:
            manifest = yaml.safe_load(manifest_p.read_text(encoding="utf-8")) or {}
        except Exception:
            manifest = {}
    prompt = (
        "Proponer sub-pasos concretos para la tarea dada, sin ejecutar nada. "
        "Devuelve SOLO JSON: { steps: [{title, desc, tool?, args?}], sensitive: boolean }\n\n"
        f"Tarea: {json.dumps({'id': t.task_id, 'title': t.title, 'desc': t.description, 'acceptance': t.acceptance}, ensure_ascii=False)}\n\n"
        f"Manifest: {json.dumps(manifest, ensure_ascii=False)}"
    )
    cwd = Path("projects") / t.project_id
    corr = f"task-steps-{t.task_id}"
    try:
        await unified_agent.start(cwd, "gemini")
        await unified_agent.send(prompt, correlation_id=corr)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"queued": True, "correlationId": corr}


def _is_sensitive(tool: str, title: str) -> bool:
    s = f"{tool} {title}".lower()
    return any(k in s for k in ["export", "delete", "remove", "rename", "erase", "drop"])  # basic heuristic


@router.post("/{id}/execute_tool")
async def execute_tool(id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    t = db.get_task(id)
    if not t:
        raise HTTPException(status_code=404, detail="task not found")
    tool = str(payload.get("tool") or "")
    args = payload.get("args") or {}
    confirmed = bool(payload.get("confirmed"))
    if _is_sensitive(tool, t.title) and not confirmed:
        raise HTTPException(status_code=403, detail="sensitive action requires confirmation")
    # Execute via MCP
    try:
        from app.services.mcp_client import mcp_client
        res = await mcp_client.run_tool(t.project_id, tool, args)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    # Attach evidence
    try:
        ev = json.loads(t.evidence_json) if t.evidence_json else []
        ev.append({"type": "tool", "tool": tool, "args": args, "result": res})
        db.update_task(id, evidence_json=json.dumps(ev, ensure_ascii=False), status="in_progress")
    except Exception:
        pass
    return {"ok": True, "result": res}


@router.post("/{id}/complete")
async def complete_task(id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    t = db.get_task(id)
    if not t:
        raise HTTPException(status_code=404, detail="task not found")
    if not bool(payload.get("acceptanceConfirmed")):
        raise HTTPException(status_code=400, detail="acceptance must be confirmed by user")
    db.update_task(id, status="done")
    return {"done": True}


@router.post("/{id}/verify")
async def verify_acceptance(id: int) -> Dict[str, Any]:
    t = db.get_task(id)
    if not t:
        raise HTTPException(status_code=404, detail="task not found")
    prompt = (
        "Verifica si se han cumplido los criterios de aceptación de la tarea. "
        "Responde SOLO JSON: { acceptance_met: boolean, notes: string }\n\n"
        f"Tarea: {json.dumps({'id': t.task_id, 'title': t.title, 'desc': t.description, 'acceptance': t.acceptance}, ensure_ascii=False)}"
    )
    cwd = Path("projects") / t.project_id
    corr = f"task-verify-{t.task_id}"
    try:
        await unified_agent.start(cwd, "gemini")
        await unified_agent.send(prompt, correlation_id=corr)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"queued": True, "correlationId": corr}
