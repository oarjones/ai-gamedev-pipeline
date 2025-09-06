"""Project management service layer."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.db import DatabaseManager, ProjectDB, db
from app.models.core import CreateProject, Project


class ProjectService:
    """Service for managing projects with filesystem and database operations."""
    
    def __init__(self, projects_root: str = "projects", db_instance: Optional[DatabaseManager] = None) -> None:
        """Initialize project service.
        
        Args:
            projects_root: Root directory for all projects
            db_instance: Database instance to use (defaults to global db)
        """
        self.projects_root = Path(projects_root)
        self.projects_root.mkdir(exist_ok=True)
        self.db = db_instance or db
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize project name to create valid directory name.
        
        Args:
            name: Original project name
            
        Returns:
            Sanitized name containing only [a-z0-9-]
        """
        # Convert to lowercase and replace spaces/underscores with hyphens
        sanitized = re.sub(r'[_\s]+', '-', name.lower())
        # Remove all non-alphanumeric characters except hyphens
        sanitized = re.sub(r'[^a-z0-9-]', '', sanitized)
        # Remove leading/trailing hyphens and collapse multiple hyphens
        sanitized = re.sub(r'-+', '-', sanitized).strip('-')
        
        if not sanitized:
            raise ValueError("Project name must contain at least one alphanumeric character")
        
        return sanitized
    
    def _generate_project_id(self, name: str) -> str:
        """Generate unique project ID from name.
        
        Args:
            name: Project name
            
        Returns:
            Unique project ID
        """
        base_id = self._sanitize_name(name)
        
        # Check if this ID already exists
        if not self.db.get_project(base_id):
            return base_id
        
        # If it exists, append a number
        counter = 1
        while True:
            candidate_id = f"{base_id}-{counter}"
            if not self.db.get_project(candidate_id):
                return candidate_id
            counter += 1
    
    def _create_project_structure(self, project_id: str, project_name: str, settings: dict = None) -> Path:
        """Create filesystem structure for a new project.
        
        Args:
            project_id: Project ID (used as directory name)
            project_name: Human-readable project name
            settings: Project settings to include in project.json
            
        Returns:
            Path to created project directory
        """
        project_dir = self.projects_root / project_id
        
        # Create main project directory
        project_dir.mkdir(exist_ok=True)
        
        # Create .agp directory for project metadata
        agp_dir = project_dir / ".agp"
        agp_dir.mkdir(exist_ok=True)
        
        # Create context and logs directories
        (project_dir / "context").mkdir(exist_ok=True)
        (project_dir / "logs").mkdir(exist_ok=True)
        
        # Merge user settings with defaults
        default_settings = {
            "version_schema": "1.0",
            "default_context_path": "context",
            "default_logs_path": "logs"
        }
        if settings:
            default_settings.update(settings)
        
        # Create project.json file
        project_data = {
            "id": project_id,
            "name": project_name,
            "version": "1.0.0",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "type": "ai-gamedev-project",
            "settings": default_settings,
            "agent": {
                "executable": "python",
                "args": ["-u", "-m", "mcp_unity_bridge.mcp_adapter"],
                "env": {},
                "default_timeout": 5.0,
                "terminate_grace": 3.0
            }
        }
        
        project_json_path = agp_dir / "project.json"
        with open(project_json_path, "w", encoding="utf-8") as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)
        
        return project_dir
    
    def _project_db_to_model(self, project_db: ProjectDB) -> Project:
        """Convert database model to API model.
        
        Args:
            project_db: Database project model
            
        Returns:
            API project model
        """
        # Read additional data from project.json if available
        project_dir = self.projects_root / project_db.path
        project_json_path = project_dir / ".agp" / "project.json"
        
        created_at = datetime.utcnow()
        updated_at = datetime.utcnow()
        settings = {}
        
        if project_json_path.exists():
            try:
                with open(project_json_path, "r", encoding="utf-8") as f:
                    project_data = json.load(f)
                    created_at = datetime.fromisoformat(project_data.get("created_at", "").replace("Z", "+00:00"))
                    updated_at = datetime.fromisoformat(project_data.get("updated_at", "").replace("Z", "+00:00"))
                    settings = project_data.get("settings", {})
            except (json.JSONDecodeError, ValueError, KeyError):
                # If project.json is corrupted, use defaults
                pass
        
        return Project(
            id=project_db.id,
            name=project_db.name,
            status="active" if project_db.active else "inactive",
            createdAt=created_at,
            updatedAt=updated_at,
            settings=settings
        )
    
    def list_projects(self) -> List[Project]:
        """List all projects.
        
        Returns:
            List of all projects
        """
        projects_db = self.db.list_projects()
        return [self._project_db_to_model(project) for project in projects_db]
    
    def get_project(self, project_id: str) -> Optional[Project]:
        """Get a project by ID.
        
        Args:
            project_id: Project ID
            
        Returns:
            Project if found, None otherwise
        """
        project_db = self.db.get_project(project_id)
        if project_db:
            return self._project_db_to_model(project_db)
        return None
    
    def create_project(self, create_data: CreateProject) -> Project:
        """Create a new project.
        
        Args:
            create_data: Project creation data
            
        Returns:
            Created project
            
        Raises:
            ValueError: If project name is invalid
        """
        # Generate unique project ID
        project_id = self._generate_project_id(create_data.name)
        
        # Create filesystem structure
        project_path = self._create_project_structure(project_id, create_data.name, create_data.settings)
        
        # Create database entry
        project_db = ProjectDB(
            id=project_id,
            name=create_data.name,
            path=project_id,  # Relative path from projects root
            active=False
        )
        
        created_project = self.db.create_project(project_db)
        
        return self._project_db_to_model(created_project)
    
    def select_active_project(self, project_id: str) -> bool:
        """Set a project as active.
        
        Args:
            project_id: ID of project to activate
            
        Returns:
            True if project was activated successfully, False if not found
        """
        return self.db.set_active_project(project_id)
    
    def get_active_project(self) -> Optional[Project]:
        """Get the currently active project.
        
        Returns:
            Active project if any, None otherwise
        """
        active_project = self.db.get_active_project()
        if active_project:
            return self._project_db_to_model(active_project)
        return None
    
    def delete_project(self, project_id: str) -> bool:
        """Delete a project (database only, filesystem is preserved).
        
        Args:
            project_id: Project ID to delete
            
        Returns:
            True if project was deleted, False if not found
        """
        return self.db.delete_project(project_id)


# Global project service instance
project_service = ProjectService()
