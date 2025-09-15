"""Service for managing versioned task plans."""

from typing import List, Optional, Dict, Any, Tuple
import json
from datetime import datetime
from pathlib import Path

from sqlmodel import select, func

from gateway.app.db import db, TaskPlanDB, TaskDB, ProjectDB
from gateway.app.models.core import Project
from gateway.app.models.schemas import TaskPlanSchema, TaskSchema
import re
import logging

log = logging.getLogger(__name__)

class TaskPlanService:
    """Service for managing versioned task plans."""
    
    def __init__(self):
        self.db = db  # Use the global db instance
    
    def create_plan(self, project_id: str, tasks_json: List[Dict], created_by: str = 'ai') -> TaskPlanDB:
        """Create new plan version with tasks.

        Validates and repairs incoming tasks before persisting. Rejects on critical errors.
        """
        # Validate/repair
        repaired_tasks, warnings = self._validate_and_repair(tasks_json)
        if self._has_circular_dependencies(repaired_tasks):
            raise ValueError("Plan rejected: circular dependencies detected")
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
        for idx, task_data in enumerate(repaired_tasks):
            task = TaskDB(
                project_id=project_id,
                plan_id=plan.id,
                idx=idx,
                code=task_data.get('code', f'T-{idx+1:03d}'),
                task_id=task_data.get('code', f'T-{idx+1:03d}'),  # Maintain compatibility
                title=task_data.get('title', 'Untitled'),
                description=task_data.get('description', ''),
                acceptance='\n'.join(task_data.get('acceptance_criteria') or []),
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

    def _validate_and_repair(self, tasks_json: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Validate tasks using Pydantic schemas, attempting auto-repair for minor issues.

        Returns (repaired_tasks, warnings). Raises ValueError for critical errors.
        """
        warnings: List[str] = []
        tasks: List[Dict[str, Any]] = []

        # 1) Normalize inputs and ensure dicts
        norm: List[Dict[str, Any]] = []
        for i, t in enumerate(tasks_json):
            if not isinstance(t, dict):
                raise ValueError(f"Task at index {i} is not an object")
            norm.append(dict(t))

        # 2) Assign/repair codes and titles
        def mk_code(n: int) -> str:
            return f"T-{n:03d}"
        code_set = set()
        for i, t in enumerate(norm, start=1):
            raw_code = str(t.get('code') or '').strip()
            code = raw_code if re.match(r'^T-\d{3}$', raw_code) else mk_code(i)
            # ensure unique
            while code in code_set:
                i += 1
                code = mk_code(i)
            code_set.add(code)
            t['code'] = code
            # Title default and clamp
            title = str(t.get('title') or '').strip() or f"Task {code}"
            if len(title) < 3:
                title = (title + '...') if title else f"Task {code}"
            t['title'] = title[:200]
            # acceptance_criteria as list
            acc = t.get('acceptance_criteria')
            if acc is None:
                t['acceptance_criteria'] = []
            elif isinstance(acc, str):
                t['acceptance_criteria'] = [acc]
            # Optional fields defaults
            t['description'] = t.get('description') or ''
            t['dependencies'] = list(dict.fromkeys([str(x) for x in (t.get('dependencies') or []) if x]))
            t['mcp_tools'] = list(t.get('mcp_tools') or [])
            t['deliverables'] = list(t.get('deliverables') or [])
            t['estimates'] = dict(t.get('estimates') or {})
            try:
                pr = int(t.get('priority') or 1)
                if pr < 1 or pr > 5:
                    warnings.append(f"Task {code}: priority out of range -> set to 1")
                    pr = 1
            except Exception:
                warnings.append(f"Task {code}: invalid priority -> set to 1")
                pr = 1
            t['priority'] = pr

        # 3) Normalize dependencies to known codes and drop self-refs
        code_list = list(code_set)
        for t in norm:
            deps = []
            for d in t.get('dependencies') or []:
                if d == t['code']:
                    continue
                if d in code_set:
                    deps.append(d)
            t['dependencies'] = list(dict.fromkeys(deps))

        # 4) Pydantic validation (strict)
        try:
            _ = [TaskSchema(**t) for t in norm]
        except Exception as e:
            # Capture first error for user
            raise ValueError(f"Plan validation failed: {e}")

        return norm, warnings

# Global instance of the service
task_plan_service = TaskPlanService()
