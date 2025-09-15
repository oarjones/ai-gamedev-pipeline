"""Service for managing versioned task plans."""

from typing import List, Optional, Dict, Any
import json
from datetime import datetime
from pathlib import Path

from sqlmodel import select, func

from gateway.app.db import db, TaskPlanDB, TaskDB, ProjectDB
from gateway.app.models.core import Project

class TaskPlanService:
    """Service for managing versioned task plans."""
    
    def __init__(self):
        self.db = db  # Use the global db instance
    
    def create_plan(self, project_id: str, tasks_json: List[Dict], created_by: str = 'ai') -> TaskPlanDB:
        """Create new plan version with tasks."""
        # 1. Get the current highest version
        with self.db.get_session() as session:
            stmt = select(func.max(TaskPlanDB.version)).where(TaskPlanDB.project_id == project_id)
            max_version = session.exec(stmt).first() or 0
        
        # 2. Create the new plan
        plan = TaskPlanDB(
            project_id=project_id,
            version=max_version + 1,
            status="proposed",
            summary=f"Plan v{max_version + 1} generated",
            created_by=created_by,
            created_at=datetime.utcnow() # Explicitly set for consistency
        )
        plan = self.db.create_task_plan(plan)
        
        # 3. Create associated tasks
        for idx, task_data in enumerate(tasks_json):
            task = TaskDB(
                project_id=project_id,
                plan_id=plan.id,
                idx=idx,
                code=task_data.get('code', f'T-{idx+1:03d}'),
                task_id=task_data.get('code', f'T-{idx+1:03d}'),  # Maintain compatibility
                title=task_data.get('title', 'Untitled'),
                description=task_data.get('description', ''),
                acceptance=task_data.get('acceptance_criteria', ''),
                status='pending',
                deps_json=json.dumps(task_data.get('dependencies', [])),
                mcp_tools=json.dumps(task_data.get('mcp_tools', [])),
                deliverables=json.dumps(task_data.get('deliverables', [])),
                estimates=json.dumps(task_data.get('estimates', {})),
                priority=task_data.get('priority', 1)
            )
            self.db.add_task(task)
        
        # 4. Export to JSON (disk synchronization)
        self._export_plan_to_json(project_id, plan)
        
        return plan
    
    def accept_plan(self, plan_id: int) -> TaskPlanDB:
        """Accept a plan and mark previous plans as superseded."""
        with self.db.get_session() as session:
            # Get the plan
            plan = session.get(TaskPlanDB, plan_id)
            if not plan:
                raise ValueError(f"Plan {plan_id} not found")
            
            # Mark other accepted plans for the project as superseded
            stmt = select(TaskPlanDB).where(
                TaskPlanDB.project_id == plan.project_id,
                TaskPlanDB.id != plan_id,
                TaskPlanDB.status == "accepted"
            )
            for old_plan in session.exec(stmt):
                old_plan.status = "superseded"
                session.add(old_plan)
            
            # Accept the current plan
            plan.status = "accepted"
            session.add(plan)
            
            # Update the project
            project = session.get(ProjectDB, plan.project_id)
            if project:
                project.active_plan_id = plan_id
                if project.status == "draft" or project.status == "consensus":
                    project.status = "active"
                session.add(project)
            
            session.commit()
            session.refresh(plan)
            
        # Export the newly accepted plan to reflect status change
        self._export_plan_to_json(plan.project_id, plan)

        return plan
    
    def _export_plan_to_json(self, project_id: str, plan: TaskPlanDB):
        """Export plan to JSON file for inspection."""
        # Note: This assumes the gateway is run from the root of the ai-gamedev-pipeline directory
        project_dir = Path(f"projects/{project_id}")
        plans_dir = project_dir / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        
        # Get tasks for the plan
        with self.db.get_session() as session:
            stmt = select(TaskDB).where(TaskDB.plan_id == plan.id).order_by(TaskDB.idx)
            tasks = session.exec(stmt).all()
        
        plan_data = {
            "version": plan.version,
            "status": plan.status,
            "summary": plan.summary,
            "created_by": plan.created_by,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "tasks": [
                {
                    "code": t.code or t.task_id,
                    "title": t.title,
                    "description": t.description,
                    "dependencies": json.loads(t.deps_json or '[]'),
                    "mcp_tools": json.loads(t.mcp_tools or '[]'),
                    "deliverables": json.loads(t.deliverables or '[]'),
                    "estimates": json.loads(t.estimates or '{}'),
                    "priority": t.priority
                }
                for t in tasks
            ]
        }
        
        plan_file = plans_dir / f"plan_v{plan.version}.json"
        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(plan_data, f, indent=2, ensure_ascii=False)

    def _has_circular_dependencies(self, tasks: List[Dict]) -> bool:
        """Check for circular dependencies in a list of tasks."""
        task_map = {task['code']: task.get('dependencies', []) for task in tasks}
        visiting = set()
        visited = set()

        def visit(task_code):
            visiting.add(task_code)
            for dep_code in task_map.get(task_code, []):
                if dep_code in visiting:
                    return True  # Cycle detected
                if dep_code not in visited:
                    if visit(dep_code):
                        return True
            visiting.remove(task_code)
            visited.add(task_code)
            return False

        for task_code in task_map:
            if task_code not in visited:
                if visit(task_code):
                    return True
        return False

# Global instance of the service
task_plan_service = TaskPlanService()
