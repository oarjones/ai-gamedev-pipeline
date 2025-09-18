"""Service for managing versioned task plans."""

from typing import List, Optional, Dict, Any, Tuple
import json
from datetime import datetime
from pathlib import Path

from sqlmodel import select, func

from app.db import db, TaskPlanDB, TaskDB, ProjectDB
from app.models.core import Project
from app.models.schemas import TaskPlanSchema, TaskSchema
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
                description=task_data.get('description') or task_data.get('desc', ''),
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

    def apply_plan_changes(self, old_plan_id: int, new_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply a set of task changes to an existing plan by creating a new version.

        - Preserves status for completed tasks (done) with timestamps/evidence.
        - Marks removed tasks as 'dropped'.
        - Validates dependencies and rejects on cycles or broken deps.
        - Returns a diff summary and the new plan id/version.
        """
        from sqlmodel import select
        # Load old plan and project
        with self.db.get_session() as session:
            old_plan = session.get(TaskPlanDB, old_plan_id)
            if not old_plan:
                raise ValueError(f"Plan {old_plan_id} not found")
            project = session.get(ProjectDB, old_plan.project_id)
            if not project:
                raise ValueError("Associated project not found")

        # Validate/repair incoming tasks
        repaired, warnings = self._validate_and_repair(new_tasks)
        if self._has_circular_dependencies(repaired):
            raise ValueError("Plan changes rejected: circular dependencies detected")

        # Build maps
        with self.db.get_session() as session:
            stmt = select(TaskDB).where(TaskDB.plan_id == old_plan_id).order_by(TaskDB.idx)
            old_rows = session.exec(stmt).all()
        old_by_code = { (r.code or r.task_id): r for r in old_rows }
        new_by_code = { t['code']: t for t in repaired }

        # Determine diff
        old_codes = set(old_by_code.keys())
        new_codes = set(new_by_code.keys())
        added = sorted(new_codes - old_codes)
        removed = sorted(old_codes - new_codes)
        modified: List[str] = []
        for c in sorted(old_codes & new_codes):
            o = old_by_code[c]
            n = new_by_code[c]
            # Compare relevant fields
            if any([
                (o.title or '') != (n.get('title') or ''),
                (o.description or '') != (n.get('description') or ''),
                (o.priority or 1) != int(n.get('priority') or 1),
                json.loads(o.deps_json or '[]') != (n.get('dependencies') or []),
            ]):
                modified.append(c)

        # Validate dependencies exist and do not point to removed/dropped tasks
        for c, t in new_by_code.items():
            for dep in t.get('dependencies') or []:
                if dep not in new_codes:
                    raise ValueError(f"Broken dependency: {c} depends on missing {dep}")

        # Create new plan version and tasks in a transaction
        with self.db.get_session() as session:
            # determine next version
            from sqlmodel import func as _func
            max_v = session.exec(select(_func.max(TaskPlanDB.version)).where(TaskPlanDB.project_id == old_plan.project_id)).first() or 0
            new_plan = TaskPlanDB(
                project_id=old_plan.project_id,
                version=int(max_v) + 1,
                status="proposed",
                summary=f"Applied changes to plan {old_plan_id}",
                created_by="user",
                created_at=datetime.utcnow(),
            )
            session.add(new_plan)
            session.commit(); session.refresh(new_plan)

            # Insert tasks (preserve done status)
            for idx, code in enumerate([t['code'] for t in repaired]):
                t = new_by_code[code]
                prev = old_by_code.get(code)
                status = 'pending'
                started_at = None
                completed_at = None
                evidence_json = None
                if prev and prev.status == 'done':
                    status = 'done'
                    started_at = prev.started_at
                    completed_at = prev.completed_at
                    evidence_json = prev.evidence_json
                row = TaskDB(
                    project_id=new_plan.project_id,
                    plan_id=new_plan.id,
                    idx=idx,
                    code=code,
                    task_id=code,
                    title=t.get('title') or (prev.title if prev else f"Task {code}"),
                    description=t.get('description') or (prev.description if prev else ''),
                    acceptance='\n'.join(t.get('acceptance_criteria') or (prev.acceptance.split('\n') if prev and prev.acceptance else [])),
                    status=status,
                    deps_json=json.dumps(t.get('dependencies') or []),
                    mcp_tools=json.dumps(t.get('mcp_tools') or []),
                    deliverables=json.dumps(t.get('deliverables') or []),
                    estimates=json.dumps(t.get('estimates') or {}),
                    priority=int(t.get('priority') or (prev.priority if prev else 1)),
                    started_at=started_at,
                    completed_at=completed_at,
                    evidence_json=evidence_json,
                )
                session.add(row)

            # Add dropped tasks from old plan
            drop_start_idx = len(repaired)
            for i, code in enumerate(removed):
                prev = old_by_code[code]
                row = TaskDB(
                    project_id=new_plan.project_id,
                    plan_id=new_plan.id,
                    idx=drop_start_idx + i,
                    code=code,
                    task_id=code,
                    title=prev.title,
                    description=prev.description,
                    acceptance=prev.acceptance,
                    status='dropped',
                    deps_json=prev.deps_json,
                    mcp_tools=prev.mcp_tools,
                    deliverables=prev.deliverables,
                    estimates=prev.estimates,
                    priority=prev.priority,
                    started_at=prev.started_at,
                    completed_at=prev.completed_at,
                    evidence_json=prev.evidence_json,
                )
                session.add(row)

            session.commit()
            session.refresh(new_plan)

        # Export snapshot for new plan
        self._export_plan_to_json(old_plan.project_id, new_plan)

        return {
            "project_id": old_plan.project_id,
            "old_plan_id": old_plan_id,
            "new_plan_id": new_plan.id,
            "version": new_plan.version,
            "diff": {
                "added": added,
                "removed": removed,
                "modified": modified,
                "warnings": warnings,
            },
        }

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
