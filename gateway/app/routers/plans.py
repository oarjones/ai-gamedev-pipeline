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

router = APIRouter()
plan_service = TaskPlanService()

class RefineRequest(BaseModel):
    instructions: str
    
class EditPlanRequest(BaseModel):
    add: Optional[List[Dict]] = None
    remove: Optional[List[str]] = None
    update: Optional[List[Dict]] = None

@router.get("", summary="List all plan versions for a project")
async def list_plans(projectId: str):
    """List all plan versions for a project."""
    with db.get_session() as session:
        from sqlmodel import select
        
        stmt = select(TaskPlanDB).where(
            TaskPlanDB.project_id == projectId
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

@router.get("/{planId}", summary="Get complete plan with tasks")
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

@router.post("/generate", summary="Generate initial plan from project manifest")
async def generate_plan(projectId: str):
    """Generate initial plan from project manifest."""
    # Leer manifest del proyecto
    manifest_path = Path(f"projects/{projectId}/.agp/project_manifest.yaml")
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
    cwd = Path("projects") / projectId
    await unified_agent.start(cwd, 'gemini')
    await unified_agent.send(prompt, correlation_id="plan-generation")
    
    return {"status": "generating", "correlation_id": "plan-generation"}

@router.post("/{planId}/refine", summary="Refine existing plan with AI (Not Implemented)")
async def refine_plan(planId: int, request: RefineRequest):
    """Refine existing plan with AI."""
    # Similar a generate pero incluyendo el plan actual
    # Crear nueva versión con los cambios
    pass

@router.patch("/{planId}/accept", summary="Accept plan and activate it")
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