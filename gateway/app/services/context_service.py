
"""Service for managing versioned project context."""

from typing import Optional, Dict, Any, List, Tuple
import json
from datetime import datetime
from pathlib import Path

from sqlmodel import select, func

from app.db import db, ContextDB, TaskDB, ProjectDB, SessionDB, AgentMessageDB, ArtifactDB
from app.services.unified_agent import agent as unified_agent
from app.ws.events import manager
from app.models.core import Envelope, EventType
import logging
import time

logger = logging.getLogger(__name__)

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
        """Generate a new context snapshot (global + optional task) after completing a task.

        Uses AI (one-shot) to summarize and update the context. Falls back to heuristic update
        if AI fails or times out. Emits an event when context is generated.
        """
        task = self.db.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Collect artifacts tied to this task
        artifacts: List[Dict[str, Any]] = []
        try:
            with self.db.get_session() as session:
                from sqlmodel import select as _select
                rows = session.exec(
                    _select(ArtifactDB).where(ArtifactDB.task_id == task_id).order_by(ArtifactDB.ts.desc())
                ).all()
                for a in rows:
                    artifacts.append({
                        "type": a.type,
                        "path": a.path,
                        "category": a.category,
                        "ts": a.ts.isoformat() if a.ts else None,
                        "meta": json.loads(a.meta_json) if a.meta_json else None,
                    })
        except Exception:
            pass

        old_global = self.get_active_context(project_id, 'global') or {}

        # Baseline values
        all_tasks = self.db.list_tasks(project_id)
        done_codes = [t.code for t in all_tasks if t.status == 'done' and t.code]
        pending_count = len([t for t in all_tasks if t.status != 'done'])
        next_task = self._get_next_available_task(project_id)

        # Build AI prompt
        task_info = {
            "id": task.id,
            "code": task.code or task.task_id,
            "title": task.title,
            "description": task.description,
            "acceptance": task.acceptance,
            "status": task.status,
        }
        prompt = (
            "Tarea completada: " + json.dumps(task_info, ensure_ascii=False) + "\n\n"
            + "Artefactos generados: " + json.dumps(artifacts, ensure_ascii=False) + "\n\n"
            + "Contexto global anterior: " + json.dumps(old_global, ensure_ascii=False) + "\n\n"
            + "Genera un nuevo contexto actualizado en JSON:\n"
            + "{\n  \"version\": n+1,\n  \"current_task\": \"siguiente_codigo\",\n  \"done_tasks\": [...],\n  \"pending_tasks\": n,\n  \"summary\": \"resumen actualizado\",\n  \"decisions\": [\"nuevas decisiones tomadas\"],\n  \"open_questions\": [\"preguntas pendientes\"],\n  \"risks\": [\"riesgos identificados\"]\n}"
        )

        def _fallback() -> Dict[str, Any]:
            return {
                "version": int(old_global.get("version", 0)) + 1,
                "current_task": (next_task.code if next_task else None),
                "done_tasks": sorted({*(old_global.get("done_tasks") or []), *(done_codes or [])}),
                "pending_tasks": int(pending_count),
                "summary": (old_global.get("summary") or "") + f"\nCompleted {task_info['code']}: {task_info['title']}",
                "decisions": old_global.get("decisions", []),
                "open_questions": old_global.get("open_questions", []),
                "risks": old_global.get("risks", []),
                "last_update": datetime.utcnow().isoformat(),
            }

        # Try AI up to 2 attempts with simple backoff
        new_global_context: Dict[str, Any]
        answer: Optional[str] = None
        error: Optional[str] = None
        for attempt in range(2):
            try:
                answer, error = unified_agent.ask_one_shot(project_id, prompt)
                if answer:
                    try:
                        parsed = json.loads(answer)
                        # Basic validation and normalization
                        parsed["version"] = int(old_global.get("version", 0)) + 1
                        if "current_task" not in parsed:
                            parsed["current_task"] = next_task.code if next_task else None
                        if "done_tasks" not in parsed:
                            parsed["done_tasks"] = sorted({*(old_global.get("done_tasks") or []), *(done_codes or [])})
                        if "pending_tasks" not in parsed:
                            parsed["pending_tasks"] = int(pending_count)
                        parsed["last_update"] = datetime.utcnow().isoformat()
                        new_global_context = parsed
                        break
                    except Exception as pe:
                        logger.warning("parse context JSON failed (attempt %s): %s", attempt + 1, pe)
                if error:
                    logger.warning("AI context generation error (attempt %s): %s", attempt + 1, error)
            except Exception as e:
                logger.warning("ask_one_shot failed (attempt %s): %s", attempt + 1, e)
            time.sleep(1 + attempt)
        else:
            new_global_context = _fallback()

        # Persist contexts (global) and minimal task snapshot
        created = self.create_context(project_id, new_global_context, scope='global', created_by='ai')

        # Optional: store a brief task context snapshot for the completed task
        try:
            task_context = {
                "summary": f"Task {task_info['code']} completed",
                "artifacts": artifacts[:10],
                "completed_at": datetime.utcnow().isoformat(),
            }
            self.create_context(project_id, task_context, scope='task', task_id=task_id, created_by='ai')
        except Exception:
            pass

        # Emit event
        try:
            env = Envelope(
                type=EventType.UPDATE,
                project_id=project_id,
                payload={
                    "event": "context.generated",
                    "scope": "global",
                    "version": created.version,
                },
            )
            # type: ignore[arg-type]
            import asyncio
            if asyncio.get_event_loop().is_running():
                # fire-and-forget
                asyncio.create_task(manager.broadcast_project(project_id, env.model_dump_json()))
            else:
                # In non-async context, best-effort ignore
                pass
        except Exception:
            pass

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
