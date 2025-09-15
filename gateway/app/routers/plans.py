from typing import Dict, Any, List, Optional
import json
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import yaml

from gateway.app.services.task_plan_service import TaskPlanService
from gateway.app.services.unified_agent import agent as unified_agent
from gateway.app.db import db, TaskPlanDB, TaskDB
from gateway.app.ws.events import manager
from gateway.app.models.core import Envelope, EventType
from pathlib import Path
from gateway.app.models.api_responses import TaskPlanResponse

router = APIRouter()
plan_service = TaskPlanService()

class RefineRequest(BaseModel):
    instructions: str
    
class EditPlanRequest(BaseModel):
    add: Optional[List[Dict]] = None
    remove: Optional[List[str]] = None
    update: Optional[List[Dict]] = None

class ApplyChangesRequest(BaseModel):
    tasks: Optional[List[Dict]] = None
    add: Optional[List[Dict]] = None
    remove: Optional[List[str]] = None
    update: Optional[List[Dict]] = None

@router.get(
    "",
    summary="List plan versions",
    description="List all plan versions for a project, newest first.",
)
async def list_plans(project_id: str = Query(..., alias="projectId")):
    """List all plan versions for a project."""
    with db.get_session() as session:
        from sqlmodel import select
        
        stmt = select(TaskPlanDB).where(
            TaskPlanDB.project_id == project_id
        ).order_by(TaskPlanDB.version.desc())
        
        plans = session.exec(stmt).all()
        
        return [
            {
                "id": p.id,
                "version": p.version,
                "status": p.status,
                "summary": p.summary,
                "created_by": p.created_by,
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in plans
        ]

@router.get(
    "/{planId}",
    summary="Get plan details",
    description="Get a complete plan, including tasks and aggregate stats.",
    response_model=TaskPlanResponse,
)
async def get_plan_details(planId: int):
    """Get complete plan with tasks."""
    with db.get_session() as session:
        from sqlmodel import select
        
        plan = session.get(TaskPlanDB, planId)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        # Get tasks
        stmt = select(TaskDB).where(TaskDB.plan_id == planId).order_by(TaskDB.idx)
        tasks = session.exec(stmt).all()
        
        # Calculate stats
        total_tasks = len(tasks)
        completed_tasks = len([t for t in tasks if t.status == 'done'])
        blocked_tasks = len([t for t in tasks if t.status == 'blocked'])
        
        return {
            "id": plan.id,
            "version": plan.version,
            "status": plan.status,
            "summary": plan.summary,
            "created_by": plan.created_by,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "stats": {
                "total": total_tasks,
                "completed": completed_tasks,
                "blocked": blocked_tasks,
                "progress": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            },
            "tasks": [
                {
                    "id": t.id,
                    "code": t.code or t.task_id,
                    "title": t.title,
                    "description": t.description,
                    "status": t.status,
                    "dependencies": json.loads(t.deps_json or "[]"),
                    "priority": t.priority
                }
                for t in tasks
            ]
        }

@router.post(
    "/generate",
    summary="Generate initial plan",
    description="Generate a new plan proposal from the project manifest using AI.",
)
async def generate_plan(project_id: str = Query(..., alias="projectId")):
    """Generate initial plan from project manifest."""
    # Leer manifest del proyecto
    manifest_path = Path(f"projects/{project_id}/.agp/project_manifest.yaml")
    if not manifest_path.exists():
        # Si no hay manifest, usar uno básico
        manifest = {"type": "generic", "description": "Proyecto de desarrollo"}
    else:
        with open(manifest_path, encoding='utf-8') as f:
            manifest = yaml.safe_load(f)
    
    # Construir prompt
    prompt = f"""
    Eres un planificador de desarrollo de videojuegos.
    Genera un plan de tareas detallado para el siguiente proyecto:
    
    {json.dumps(manifest, indent=2, ensure_ascii=False)}
    
    REQUISITOS:
    - Entre 8 y 15 tareas concretas y ejecutables
    - Cada tarea debe incluir: code (T-001, T-002...), title, description, dependencies, mcp_tools, deliverables, acceptance_criteria, estimates (story_points, time_hours), priority
    - Las dependencias deben referenciar códigos de tareas anteriores
    - Usa herramientas MCP apropiadas: ["unity", "blender", "filesystem"]
    
    Responde SOLO con JSON válido en este formato:
    {{
        "tasks": [
            {{
                "code": "T-001",
                "title": "...",
                "description": "...",
                "dependencies": [],
                "mcp_tools": ["unity"],
                "deliverables": ["..."],
                "acceptance_criteria": "...",
                "estimates": {{"story_points": 3, "time_hours": 2}},
                "priority": 1
            }}
        ]
    }}
    """
    
    # Llamar al agente
    cwd = Path("projects") / project_id
    await unified_agent.start(cwd, 'gemini')
    await unified_agent.send(prompt, correlation_id="plan-generation")
    
    return {"status": "generating", "correlation_id": "plan-generation"}

@router.post(
    "/{planId}/refine",
    summary="Refine existing plan with AI (Not Implemented)",
    description="Refine an existing plan using AI and create a new version.",
)
async def refine_plan(planId: int, request: RefineRequest):
    """Refine existing plan with AI."""
    # Similar a generate pero incluyendo el plan actual
    # Crear nueva versión con los cambios
    pass

@router.patch(
    "/{planId}/accept",
    summary="Accept plan and activate it",
    description="Accepts the plan and marks it as active, superseding previous ones.",
)
async def accept_plan(planId: int):
    """Accept plan and activate it."""
    try:
        plan = plan_service.accept_plan(planId)
        
        # Emitir evento WebSocket
        envelope = Envelope(
            type=EventType.UPDATE,
            project_id=plan.project_id,
            payload={
                "event": "plan.accepted",
                "plan_id": plan.id,
                "version": plan.version
            }
        )
        await manager.broadcast_project(plan.project_id, envelope.model_dump_json())
        
        return {"status": "accepted", "plan_id": plan.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch(
    "/{planId}",
    summary="Update plan tasks order and fields",
    description="Update inline fields and order for tasks in a plan (minor edits).",
)
async def update_plan(planId: int, payload: EditPlanRequest):
    """Update tasks of a plan (reorder and inline edits).

    Accepts payload like:
    {
      "update": [
        {"id": 123, "idx": 0, "title": "...", "description": "...", "priority": 2, "dependencies": ["T-001"]}
      ]
    }
    Only fields present will be updated.
    """
    with db.get_session() as session:
        # Validate plan exists
        plan = session.get(TaskPlanDB, planId)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        updated = 0

        # Handle updates (order and fields)
        if payload.update:
            for upd in payload.update:
                try:
                    tid = int(upd.get("id"))
                except Exception:
                    continue
                task = session.get(TaskDB, tid)
                if not task or task.plan_id != planId:
                    continue

                if "idx" in upd:
                    try:
                        task.idx = int(upd.get("idx"))
                    except Exception:
                        pass
                title = upd.get("title")
                if isinstance(title, str):
                    task.title = title
                desc = upd.get("description")
                if isinstance(desc, str):
                    task.description = desc
                if "priority" in upd:
                    try:
                        task.priority = int(upd.get("priority"))
                    except Exception:
                        pass
                if "dependencies" in upd and isinstance(upd.get("dependencies"), list):
                    try:
                        task.deps_json = json.dumps(upd.get("dependencies"))
                    except Exception:
                        pass
                updated += 1

        # TODO: handle add/remove if needed by UI in the future

        session.commit()
        return {"updated": updated, "plan_id": planId}


@router.patch(
    "/{planId}/apply-changes",
    summary="Apply plan changes and create new version",
    description="Apply add/update/remove operations or a full task list to create a new plan version while preserving progress.",
)
async def apply_changes(planId: int, req: ApplyChangesRequest):
    """Apply a set of changes to an existing plan by creating a new version.

    Accepts either a full tasks array via `tasks`, or a partial set of operations
    (add/remove/update) applied to the current plan to construct the new tasks list.
    """
    # Build new tasks list
    if req.tasks is not None:
        new_tasks = list(req.tasks)
    else:
        # Load current plan tasks
        from sqlmodel import select
        with db.get_session() as session:
            stmt = select(TaskDB).where(TaskDB.plan_id == planId).order_by(TaskDB.idx)
            curr = session.exec(stmt).all()
        by_code = { (t.code or t.task_id): {
            "code": t.code or t.task_id,
            "title": t.title,
            "description": t.description,
            "dependencies": (json.loads(t.deps_json or "[]")),
            "mcp_tools": (json.loads(t.mcp_tools or "[]")),
            "deliverables": (json.loads(t.deliverables or "[]")),
            "estimates": (json.loads(t.estimates or "{}")),
            "priority": t.priority,
        } for t in curr }

        # apply updates
        if req.update:
            for u in req.update:
                c = str(u.get("code") or "").strip()
                if not c or c not in by_code:
                    continue
                by_code[c].update({k: v for k, v in u.items() if k != "code"})
        # apply removes
        if req.remove:
            for c in req.remove:
                by_code.pop(c, None)
        # apply adds (append at end)
        if req.add:
            for a in req.add:
                if not isinstance(a, dict):
                    continue
                code = str(a.get("code") or "").strip()
                if code and code in by_code:
                    continue
                by_code[code or f"T-{len(by_code)+1:03d}"] = a
        new_tasks = list(by_code.values())

    try:
        res = plan_service.apply_plan_changes(planId, new_tasks)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Emit WebSocket event
    try:
        envelope = Envelope(
            type=EventType.UPDATE,
            project_id=res.get("project_id"),
            payload={"event": "plan.changed", "old": planId, "new": res.get("new_plan_id"), "diff": res.get("diff")}
        )
        await manager.broadcast_project(res.get("project_id"), envelope.model_dump_json())
    except Exception:
        pass

    return res
