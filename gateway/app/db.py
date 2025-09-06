"""Database configuration and models for AI Gateway."""

from pathlib import Path
from typing import Optional

from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel import Field


class ProjectDB(SQLModel, table=True):
    """Database model for projects."""
    
    __tablename__ = "projects"
    
    id: str = Field(primary_key=True, description="Unique project identifier")
    name: str = Field(description="Human-readable project name") 
    path: str = Field(description="Relative path to project directory")
    active: bool = Field(default=False, description="Whether this project is currently active")


class DatabaseManager:
    """Manages SQLite database connection and operations."""
    
    def __init__(self, db_path: str = "data/gateway.db") -> None:
        """Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,  # Set to True for SQL debugging
            connect_args={"check_same_thread": False}
        )
        
        # Create tables
        SQLModel.metadata.create_all(self.engine)
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return Session(self.engine)
    
    def get_active_project(self) -> Optional[ProjectDB]:
        """Get the currently active project."""
        with self.get_session() as session:
            statement = select(ProjectDB).where(ProjectDB.active == True)
            return session.exec(statement).first()
    
    def set_active_project(self, project_id: str) -> bool:
        """Set a project as active, deactivating all others.
        
        Args:
            project_id: ID of project to activate
            
        Returns:
            True if project was found and activated, False otherwise
        """
        with self.get_session() as session:
            # First deactivate all projects
            all_projects = session.exec(select(ProjectDB)).all()
            for project in all_projects:
                project.active = False
            
            # Then activate the target project
            target_project = session.get(ProjectDB, project_id)
            if target_project:
                target_project.active = True
                session.commit()
                return True
            else:
                session.rollback()
                return False
    
    def create_project(self, project: ProjectDB) -> ProjectDB:
        """Create a new project in the database.
        
        Args:
            project: Project to create
            
        Returns:
            Created project
        """
        with self.get_session() as session:
            session.add(project)
            session.commit()
            session.refresh(project)
            return project
    
    def get_project(self, project_id: str) -> Optional[ProjectDB]:
        """Get a project by ID.
        
        Args:
            project_id: Project ID to lookup
            
        Returns:
            Project if found, None otherwise
        """
        with self.get_session() as session:
            return session.get(ProjectDB, project_id)
    
    def list_projects(self) -> list[ProjectDB]:
        """List all projects.
        
        Returns:
            List of all projects
        """
        with self.get_session() as session:
            statement = select(ProjectDB)
            return list(session.exec(statement).all())
    
    def delete_project(self, project_id: str) -> bool:
        """Delete a project from the database.
        
        Args:
            project_id: ID of project to delete
            
        Returns:
            True if project was found and deleted, False otherwise
        """
        with self.get_session() as session:
            project = session.get(ProjectDB, project_id)
            if project:
                session.delete(project)
                session.commit()
                return True
            return False


# Global database manager instance
db = DatabaseManager()