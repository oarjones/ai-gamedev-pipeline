
"""Service for managing versioned project context."""

from typing import Optional, Dict, Any, List
import json
from datetime import datetime
from pathlib import Path

from sqlmodel import select, func

from gateway.app.db import db, ContextDB, TaskDB, ProjectDB, SessionDB, AgentMessageDB, ArtifactDB

class ContextService:
    """Service for managing versioned context."""
    
    def __init__(self):
        self.db = db  # Use the global db instance
    
    def get_active_context(self, project_id: str, scope: str = 'global', task_id: Optional[int] = None) -> Optional[Dict]:
        """Get active context content as a dictionary."""
        context_db = self.db.get_active_context(project_id, scope)
        if context_db:
            try:
                return json.loads(context_db.content)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    def list_context_history(self, project_id: str, scope: str = 'global', limit: int = 20) -> List[ContextDB]:
        """List all context versions for a given scope."""
        with self.db.get_session() as session:
            stmt = select(ContextDB).where(
                ContextDB.project_id == project_id,
                ContextDB.scope == scope
            ).order_by(ContextDB.version.desc()).limit(limit)
            return list(session.exec(stmt).all())
    
    def create_context(self, 
                      project_id: str, 
                      content: Dict[str, Any], 
                      scope: str = 'global',
                      task_id: Optional[int] = None,
                      created_by: str = 'system') -> ContextDB:
        """Create a new context version."""
        
        # Get the current highest version for the given scope
        with self.db.get_session() as session:
            stmt = select(func.max(ContextDB.version)).where(
                ContextDB.project_id == project_id,
                ContextDB.scope == scope
            )
            if scope == 'task' and task_id:
                stmt = stmt.where(ContextDB.task_id == task_id)
            
            max_version = session.exec(stmt).first() or 0
        
        # Create the new context object
        context = ContextDB(
            project_id=project_id,
            scope=scope,
            task_id=task_id if scope == 'task' else None,
            content=json.dumps(content, ensure_ascii=False, indent=2),
            created_by=created_by,
            source='manual-edit' if created_by == 'user' else 'ai-generate',
            version=max_version + 1,
            is_active=True,
            created_at=datetime.utcnow()
        )
        
        # Use the DB manager to handle deactivation of old contexts and saving the new one
        context = self.db.create_context(context)
        
        # Sync the new context to the filesystem
        self._sync_context_to_files(project_id, scope, content, task_id)
        
        return context
    
    def generate_context_after_task(self, project_id: str, task_id: int) -> Dict[str, Any]:
        """Generate a new global context after a task is completed."""
        
        task = self.db.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        global_context = self.get_active_context(project_id, 'global') or {}
        
        done_tasks = global_context.get('done_tasks', [])
        if task.code and task.code not in done_tasks:
            done_tasks.append(task.code)
        
        next_task = self._get_next_available_task(project_id)
        
        all_tasks = self.db.list_tasks(project_id)
        pending_count = len([t for t in all_tasks if t.status != 'done'])
        
        new_global_context = {
            "version": global_context.get('version', 0) + 1,
            "current_task": next_task.code if next_task else None,
            "done_tasks": done_tasks,
            "pending_tasks": pending_count,
            "summary": global_context.get('summary', '') + f"\nCompleted task {task.code}: {task.title}",
            "decisions": global_context.get('decisions', []),
            "open_questions": global_context.get('open_questions', []),
            "risks": global_context.get('risks', []),
            "last_update": datetime.utcnow().isoformat()
        }
        
        self.create_context(project_id, new_global_context, scope='global', created_by='system')
        
        return new_global_context

    def generate_context_from_session(self, session_id: int) -> Dict[str, Any]:
        """Generate a context summary from session messages."""
        messages = self.db.list_agent_messages(session_id, limit=50) # Get last 50 messages
        
        summary = "Summary of recent conversation:\n"
        for msg in reversed(messages): # Chronological order
            summary += f"- {msg.role}: {msg.content[:100]}...\n"

        context_content = {
            "type": "session_summary",
            "session_id": session_id,
            "summary": summary,
            "message_count": len(messages),
            "generated_at": datetime.utcnow().isoformat()
        }
        return context_content

    def _get_next_available_task(self, project_id: str) -> Optional[TaskDB]:
        """Get the next pending task whose dependencies are all completed."""
        tasks = self.db.list_tasks(project_id)
        done_task_codes = {t.code for t in tasks if t.status == 'done'}
        
        for task in sorted(tasks, key=lambda t: t.priority):
            if task.status != 'pending':
                continue
            
            if task.deps_json:
                try:
                    deps = json.loads(task.deps_json)
                    if not deps: # Empty dependency list
                        return task
                    
                    # Check if all dependency codes are in the set of done tasks
                    if all(dep_code in done_task_codes for dep_code in deps):
                        return task

                except (json.JSONDecodeError, TypeError):
                    continue # Skip task if deps are malformed
            else:
                # No dependencies, so it's available
                return task
        
        return None
    
    def _sync_context_to_files(self, project_id: str, scope: str, content: Dict, task_id: Optional[int] = None):
        """Sync context to the filesystem."""
        project_dir = Path(f"projects/{project_id}")

        if scope == 'global':
            context_dir = project_dir / "context"
            context_dir.mkdir(parents=True, exist_ok=True)
            
            active_file = context_dir / "active_context.json"
            with open(active_file, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
            
            history_dir = context_dir / "history"
            history_dir.mkdir(exist_ok=True)
            version = content.get('version', 1)
            history_file = history_dir / f"context_v{version}.json"
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
        
        elif scope == 'task' and task_id:
            task = self.db.get_task(task_id)
            if task and task.code:
                task_dir = project_dir / "context" / "tasks" / task.code
                task_dir.mkdir(parents=True, exist_ok=True)
                
                active_file = task_dir / "active.json"
                with open(active_file, 'w', encoding='utf-8') as f:
                    json.dump(content, f, indent=2, ensure_ascii=False)

# Global instance of the service
context_service = ContextService()
