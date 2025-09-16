from typing import Optional, List, Dict, Any, AsyncGenerator
import json
import asyncio
from datetime import datetime

from gateway.app.db import db, TaskDB, ProjectDB
from gateway.app.services.context_service import ContextService
from gateway.app.services.unified_agent import agent as unified_agent
from gateway.app.ws.events import manager
from gateway.app.models.core import Envelope, EventType
import logging

logger = logging.getLogger(__name__)

class TaskExecutionService:
    """Service for intelligent task execution flow."""
    
    def __init__(self):
        self.db = db
        self.context_service = ContextService()
    
    def get_next_available_task(self, project_id: str) -> Optional[TaskDB]:
        """Get next task with all dependencies completed, based on a scoring system."""
        tasks = self.db.list_tasks(project_id)
        
        def task_score(t):
            try:
                estimates = json.loads(t.estimates or '{}')
            except (json.JSONDecodeError, TypeError):
                estimates = {}
            story_points = estimates.get('story_points', 5)
            # Score is a tuple: higher priority (lower number) is better,
            # then higher story points (more value) is better.
            return (t.priority, -story_points, t.idx)
        
        available_tasks = []
        done_task_codes = {t.code for t in tasks if t.status == 'done'}

        for task in tasks:
            if task.status != 'pending':
                continue
            
            deps_met = True
            if task.deps_json:
                try:
                    deps = json.loads(task.deps_json)
                    if not all(dep_code in done_task_codes for dep_code in deps):
                        deps_met = False
                except (json.JSONDecodeError, TypeError):
                    deps_met = False # Treat malformed deps as unmet
            
            if deps_met:
                available_tasks.append(task)
        
        if available_tasks:
            # Return the task with the lowest score (best priority, highest story points)
            return min(available_tasks, key=task_score)
        return None
    
    async def start_task(self, task_id: int) -> TaskDB:
        """Start a task execution."""
        task = self.db.update_task(
            task_id,
            status='in_progress',
            started_at=datetime.utcnow()
        )
        
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Update project
        with self.db.get_session() as session:
            project = session.get(ProjectDB, task.project_id)
            if project:
                project.current_task_id = task_id
                session.add(project)
                session.commit()
        
        # Emit event
        await self._emit_task_event(task, "task.started")
        
        return task
    
    async def complete_task(self, task_id: int, evidence: List[Dict] = None) -> TaskDB:
        """Complete a task and update context."""
        task = self.db.update_task(
            task_id,
            status='done',
            completed_at=datetime.utcnow(),
            evidence_json=json.dumps(evidence or [])
        )
        
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Generate new context
        try:
            self.context_service.generate_context_after_task(
                task.project_id, 
                task_id
            )
        except Exception as e:
            logger.error("Error generating context after task %s: %s", task_id, e)
        
        # Select and start the next task automatically
        next_task = self.get_next_available_task(task.project_id)
        if next_task and next_task.id is not None:
            await self.start_task(next_task.id)
        
        # Emit event
        await self._emit_task_event(task, "task.completed", {
            "next_task": next_task.code if next_task else None
        })
        
        return task
    
    async def execute_task_with_agent(self, task_id: int) -> AsyncGenerator[Dict, None]:
        """Execute task with agent assistance."""
        task = self.db.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Build context
        global_context = self.context_service.get_active_context(task.project_id, 'global')
        task_context = self.context_service.get_active_context(
            task.project_id, 
            'task', 
            task_id
        )
        
        mcp_tools = json.loads(task.mcp_tools or '[]')
        deliverables = json.loads(task.deliverables or '[]')
        
        prompt = f"""
        CONTEXTO GLOBAL DEL PROYECTO:
        {json.dumps(global_context, indent=2, ensure_ascii=False)}
        
        TAREA ACTUAL: {task.code} - {task.title}
        Descripción: {task.description}
        
        CRITERIOS DE ACEPTACIÓN:
        {task.acceptance}
        
        HERRAMIENTAS MCP SUGERIDAS: {', '.join(mcp_tools)}
        
        ENTREGABLES ESPERADOS:
        {json.dumps(deliverables, indent=2, ensure_ascii=False)}
        
        {f"CONTEXTO DE TAREA ANTERIOR: {json.dumps(task_context, indent=2, ensure_ascii=False)}" if task_context else ""}
        
        Por favor, ejecuta esta tarea paso a paso, usando las herramientas MCP necesarias.
        Documenta cada paso y verifica que se cumplan los criterios de aceptación.
        """
        
        from pathlib import Path
        cwd = Path("projects") / task.project_id
        
        if not unified_agent.status().running:
            await unified_agent.start(cwd, 'gemini')
        
        response = await unified_agent.send(prompt, correlation_id=f"task-{task_id}")
        
        yield {"type": "started", "task_id": task_id}
        yield {"type": "response", "content": response}
    
    async def verify_acceptance_criteria(self, task_id: int) -> Dict[str, Any]:
        """Use AI to verify if acceptance criteria are met."""
        task = self.db.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        evidence = json.loads(task.evidence_json or '[]')
        
        prompt = f"""
        Verifica si se cumplen los siguientes criterios de aceptación:
        
        TAREA: {task.title}
        CRITERIOS: {task.acceptance}
        
        EVIDENCIA DISPONIBLE:
        {json.dumps(evidence, indent=2, ensure_ascii=False)}
        
        Responde con JSON:
        {{
            "criteria_met": true/false,
            "details": [
                {{"criterion": "...", "met": true/false, "notes": "..."}}
            ],
            "recommendation": "..."
        }}
        """
        
        from pathlib import Path
        cwd = Path("projects") / task.project_id
        
        if not unified_agent.status().running:
            await unified_agent.start(cwd, 'gemini')
        
        await unified_agent.send(prompt, correlation_id=f"verify-{task_id}")
        
        return {"status": "verification_requested", "task_id": task_id}
    
    async def _emit_task_event(self, task: TaskDB, event_type: str, extra_data: Dict = None):
        """Emit task event via WebSocket."""
        payload = {
            "event": event_type,
            "task": {
                "id": task.id,
                "code": task.code or task.task_id,
                "title": task.title,
                "status": task.status
            }
        }
        if extra_data:
            payload.update(extra_data)
        
        envelope = Envelope(
            type=EventType.UPDATE,
            project_id=task.project_id, # Proactively corrected from project_id
            payload=payload
        )
        
        await manager.broadcast_project(
            task.project_id, 
            envelope.model_dump_json()
        )

# Global instance
task_execution_service = TaskExecutionService()
