from typing import List, Optional, Dict, Any
from pathlib import Path
import json
import shutil
from datetime import datetime
import imghdr

from gateway.app.db import db, ArtifactDB, TaskDB

class ArtifactService:
    """Service for managing task artifacts."""
    
    def __init__(self):
        self.db = db
    
    def register_artifact(self, 
                         task_id: int,
                         artifact_type: str,
                         path: str,
                         meta: Dict[str, Any] = None,
                         category: str = None) -> ArtifactDB:
        """Register a new artifact for a task."""
        
        task = self.db.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        session = self.db.get_last_session(task.project_id)
        session_id = session.id if session else None
        
        file_path = Path(path)
        size_bytes = file_path.stat().st_size if file_path.exists() else None
        
        artifact = ArtifactDB(
            session_id=session_id,
            task_id=task_id,
            type=artifact_type,
            path=path,
            category=category or self._infer_category(artifact_type),
            meta_json=json.dumps(meta or {}),
            size_bytes=size_bytes,
            validation_status="pending",
            ts=datetime.utcnow()
        )
        
        artifact = self.db.add_artifact(artifact)
        
        self._organize_artifact(task, artifact)
        
        return artifact
    
    def list_task_artifacts(self, task_id: int) -> List[Dict[str, Any]]:
        """List all artifacts for a task."""
        with self.db.get_session() as session:
            from sqlmodel import select
            stmt = select(ArtifactDB).where(ArtifactDB.task_id == task_id)
            artifacts = session.exec(stmt).all()
            
            return [
                {
                    "id": a.id,
                    "type": a.type,
                    "category": a.category,
                    "path": a.path,
                    "size_bytes": a.size_bytes,
                    "validation_status": a.validation_status,
                    "meta": json.loads(a.meta_json or "{}"),
                    "created_at": a.ts.isoformat()
                }
                for a in artifacts
            ]
    
    def validate_artifact(self, artifact_id: int) -> bool:
        """Validate artifact exists and format is correct."""
        with self.db.get_session() as session:
            artifact = session.get(ArtifactDB, artifact_id)
            if not artifact:
                return False
            
            file_path = Path(artifact.path)
            
            if not file_path.exists():
                artifact.validation_status = "invalid"
                session.add(artifact)
                session.commit()
                return False
            
            valid = self._validate_format(artifact.type, file_path)
            
            artifact.validation_status = "valid" if valid else "invalid"
            session.add(artifact)
            session.commit()
            
            return valid
    
    def capture_from_unity(self, task_id: int) -> List[ArtifactDB]:
        """Capture Unity artifacts for current task."""
        from gateway.app.services.mcp_client import mcp_client
        
        task = self.db.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        artifacts = []
        
        try:
            screenshot_result = mcp_client.capture_screenshot(task.project_id)
            if screenshot_result and 'path' in screenshot_result:
                artifact = self.register_artifact(
                    task_id=task_id,
                    artifact_type="image",
                    path=screenshot_result['path'],
                    category="screenshot",
                    meta={"source": "unity", "timestamp": datetime.utcnow().isoformat()}
                )
                artifacts.append(artifact)
        except Exception as e:
            print(f"Error capturing screenshot: {e}")
        
        try:
            scene_result = mcp_client.get_scene_hierarchy(task.project_id)
            if scene_result:
                scene_path = Path(f"projects/{task.project_id}/artifacts/scene_{task_id}.json")
                scene_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(scene_path, 'w') as f:
                    json.dump(scene_result, f, indent=2)
                
                artifact = self.register_artifact(
                    task_id=task_id,
                    artifact_type="json",
                    path=str(scene_path),
                    category="scene",
                    meta={"source": "unity", "objects_count": len(scene_result.get('objects', []))}
                )
                artifacts.append(artifact)
        except Exception as e:
            print(f"Error capturing scene: {e}")
        
        return artifacts
    
    def generate_task_report(self, task_id: int) -> str:
        """Generate markdown report for task."""
        task = self.db.get_task(task_id)
        if not task:
            return "Task not found"
        
        artifacts = self.list_task_artifacts(task_id)
        
        time_spent = ""
        if task.started_at and task.completed_at:
            delta = task.completed_at - task.started_at
            hours = delta.total_seconds() / 3600
            time_spent = f"{hours:.1f} horas"
        
        report = f"# Reporte de Tarea: {task.code or task.task_id}\n\n## {task.title}\n\n**Estado**: {task.status}\n**Tiempo empleado**: {time_spent}\n\n### Descripción\n{task.description}\n\n### Criterios de Aceptación\n{task.acceptance}\n\n### Artefactos Generados ({len(artifacts)})\n"
        
        for artifact in artifacts:
            report += f"- **{artifact['type'].upper()}** ({artifact['category']})\n  - Archivo: `{Path(artifact['path']).name}`\n  - Tamaño: {artifact['size_bytes'] / 1024:.1f} KB\n  - Estado: {artifact['validation_status']}\n"
        
        if task.evidence_json:
            evidence = json.loads(task.evidence_json)
            if evidence:
                report += "\n### Evidencia\n"
                for item in evidence:
                    report += f"- {item}\n"
        
        return report
    
    def _infer_category(self, artifact_type: str) -> str:
        mapping = {
            "fbx": "asset", "obj": "asset", "blend": "asset",
            "png": "screenshot", "jpg": "screenshot",
            "cs": "code", "py": "code",
            "json": "document", "yaml": "document", "md": "document"
        }
        return mapping.get(artifact_type.lower(), "other")
    
    def _validate_format(self, artifact_type: str, path: Path) -> bool:
        if not path.exists():
            return False
        
        if artifact_type in ["png", "jpg", "jpeg"]:
            try:
                return imghdr.what(path) is not None
            except:
                return True
        
        elif artifact_type == "json":
            try:
                with open(path) as f:
                    json.load(f)
                return True
            except:
                return False
        
        return True
    
    def _organize_artifact(self, task: TaskDB, artifact: ArtifactDB):
        if not task.code:
            return
        
        source = Path(artifact.path)
        if not source.exists():
            return
        
        artifacts_dir = Path(f"projects/{task.project_id}/artifacts/{task.code}")
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        if artifacts_dir not in source.parents:
            dest = artifacts_dir / source.name
            try:
                shutil.copy2(source, dest)
            except Exception as e:
                print(f"Error organizing artifact: {e}")

artifact_service = ArtifactService()
