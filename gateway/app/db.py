"""Database configuration and models for AI Gateway."""

from pathlib import Path
from typing import Optional, List

from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel import Field
from datetime import datetime


class ProjectDB(SQLModel, table=True):
    """Database model for projects."""
    
    __tablename__ = "projects"
    
    id: str = Field(primary_key=True, description="Unique project identifier")
    name: str = Field(description="Human-readable project name") 
    path: str = Field(description="Relative path to project directory")
    active: bool = Field(default=False, description="Whether this project is currently active")


class ChatMessageDB(SQLModel, table=True):
    """Database model for chat messages."""

    __tablename__ = "chat_messages"

    id: int | None = Field(default=None, primary_key=True)
    msg_id: str = Field(index=True, description="Unique message identifier (UUID4)")
    project_id: str = Field(index=True, description="Project ID")
    role: str = Field(description="Message role: user|agent|system")
    content: str = Field(description="Message content")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="UTC timestamp")


class TimelineEventDB(SQLModel, table=True):
    """Timeline of orchestrated action steps."""

    __tablename__ = "timeline_events"

    id: int | None = Field(default=None, primary_key=True)
    project_id: str = Field(index=True, description="Project ID")
    step_index: int = Field(description="Step index within the plan")
    tool: str = Field(description="Tool identifier")
    args_json: str = Field(description="JSON-serialized arguments")
    status: str = Field(description="success|error")
    result_json: str | None = Field(default=None, description="JSON-serialized result or error details")
    correlation_id: str | None = Field(default=None, description="Correlation ID if provided")
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Step start UTC time")
    finished_at: datetime | None = Field(default=None, description="Step finish UTC time")


class SessionDB(SQLModel, table=True):
    """Agent session per project/provider with optional summary."""

    __tablename__ = "sessions"

    id: int | None = Field(default=None, primary_key=True)
    project_id: str = Field(index=True, description="Project ID")
    provider: str = Field(default="gemini_cli", description="Provider name")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: datetime | None = Field(default=None)
    summary_text: str | None = Field(default=None, description="Latest session summary (markdown)")


class AgentMessageDB(SQLModel, table=True):
    """Stored conversation messages for sessions."""

    __tablename__ = "agent_messages"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(index=True)
    role: str = Field(description="user|assistant|tool")
    content: str = Field(default="", description="Message content")
    ts: datetime = Field(default_factory=datetime.utcnow)
    tool_name: str | None = Field(default=None)
    tool_args_json: str | None = Field(default=None)
    tool_result_json: str | None = Field(default=None)


class ArtifactDB(SQLModel, table=True):
    """References to generated artifacts tied to a session."""

    __tablename__ = "artifacts"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(index=True)
    type: str = Field(description="Kind of artifact (fbx,image,etc)")
    path: str = Field(description="Filesystem path")
    meta_json: str | None = Field(default=None)
    ts: datetime = Field(default_factory=datetime.utcnow)


class TaskDB(SQLModel, table=True):
    """Project task persisted from plan_of_record or UI."""

    __tablename__ = "tasks"

    id: int | None = Field(default=None, primary_key=True)
    project_id: str = Field(index=True)
    task_id: str = Field(index=True, description="Stable task identifier, e.g., T-001")
    title: str = Field()
    description: str = Field(default="")
    acceptance: str = Field(default="")
    status: str = Field(default="pending")  # pending|in_progress|done
    deps_json: str | None = Field(default=None)
    evidence_json: str | None = Field(default=None)


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

    # Chat messages operations
    def add_chat_message(self, message: ChatMessageDB) -> ChatMessageDB:
        with self.get_session() as session:
            session.add(message)
            session.commit()
            session.refresh(message)
            return message

    def list_chat_messages(self, project_id: str, limit: int = 50) -> List[ChatMessageDB]:
        with self.get_session() as session:
            statement = (
                select(ChatMessageDB)
                .where(ChatMessageDB.project_id == project_id)
                .order_by(ChatMessageDB.created_at.desc())
                .limit(limit)
            )
            return list(session.exec(statement).all())

    # Timeline operations
    def add_timeline_event(self, event: TimelineEventDB) -> TimelineEventDB:
        with self.get_session() as session:
            session.add(event)
            session.commit()
            session.refresh(event)
            return event

    def list_timeline_events(self, project_id: str, limit: int = 100) -> List[TimelineEventDB]:
        with self.get_session() as session:
            statement = (
                select(TimelineEventDB)
                .where(TimelineEventDB.project_id == project_id)
                .order_by(TimelineEventDB.started_at.desc())
                .limit(limit)
            )
            return list(session.exec(statement).all())

    def get_timeline_event(self, event_id: int) -> Optional[TimelineEventDB]:
        with self.get_session() as session:
            return session.get(TimelineEventDB, event_id)

    # Sessions
    def create_session(self, project_id: str, provider: str = "gemini_cli") -> SessionDB:
        with self.get_session() as session:
            s = SessionDB(project_id=project_id, provider=provider)
            session.add(s)
            session.commit()
            session.refresh(s)
            return s

    def end_session(self, session_id: int) -> None:
        with self.get_session() as session:
            s = session.get(SessionDB, session_id)
            if s:
                s.ended_at = datetime.utcnow()
                session.add(s)
                session.commit()

    def update_session_summary(self, session_id: int, summary_text: str) -> None:
        with self.get_session() as session:
            s = session.get(SessionDB, session_id)
            if s:
                s.summary_text = summary_text
                session.add(s)
                session.commit()

    def list_sessions(self, project_id: str, limit: int = 20) -> List[SessionDB]:
        with self.get_session() as session:
            stmt = (
                select(SessionDB)
                .where(SessionDB.project_id == project_id)
                .order_by(SessionDB.started_at.desc())
                .limit(limit)
            )
            return list(session.exec(stmt).all())

    def get_last_session(self, project_id: str) -> Optional[SessionDB]:
        rows = self.list_sessions(project_id, limit=1)
        return rows[0] if rows else None

    def get_session(self, session_id: Optional[int]) -> Optional[SessionDB]:
        if not session_id:
            return None
        with self.get_session() as session:
            return session.get(SessionDB, session_id)

    # Messages
    def add_agent_message(self, msg: AgentMessageDB) -> AgentMessageDB:
        with self.get_session() as session:
            session.add(msg)
            session.commit()
            session.refresh(msg)
            return msg

    def list_agent_messages(self, session_id: int, limit: int = 50) -> List[AgentMessageDB]:
        with self.get_session() as session:
            stmt = (
                select(AgentMessageDB)
                .where(AgentMessageDB.session_id == session_id)
                .order_by(AgentMessageDB.ts.desc())
                .limit(limit)
            )
            return list(session.exec(stmt).all())

    # Artifacts
    def add_artifact(self, art: ArtifactDB) -> ArtifactDB:
        with self.get_session() as session:
            session.add(art)
            session.commit()
            session.refresh(art)
            return art

    def list_artifacts(self, session_id: int, limit: int = 50) -> List[ArtifactDB]:
        with self.get_session() as session:
            stmt = (
                select(ArtifactDB)
                .where(ArtifactDB.session_id == session_id)
                .order_by(ArtifactDB.ts.desc())
                .limit(limit)
            )
            return list(session.exec(stmt).all())

    # Tasks
    def add_task(self, task: TaskDB) -> TaskDB:
        with self.get_session() as session:
            session.add(task)
            session.commit()
            session.refresh(task)
            return task

    def get_task(self, id_: int) -> Optional[TaskDB]:
        with self.get_session() as session:
            return session.get(TaskDB, id_)

    def list_tasks(self, project_id: str) -> List[TaskDB]:
        with self.get_session() as session:
            stmt = select(TaskDB).where(TaskDB.project_id == project_id).order_by(TaskDB.id.asc())
            return list(session.exec(stmt).all())

    def find_task_by_task_id(self, project_id: str, task_id: str) -> Optional[TaskDB]:
        with self.get_session() as session:
            stmt = select(TaskDB).where(TaskDB.project_id == project_id).where(TaskDB.task_id == task_id)
            return session.exec(stmt).first()

    def update_task(self, id_: int, **fields) -> Optional[TaskDB]:
        with self.get_session() as session:
            t = session.get(TaskDB, id_)
            if not t:
                return None
            for k, v in fields.items():
                if hasattr(t, k):
                    setattr(t, k, v)
            session.add(t)
            session.commit()
            session.refresh(t)
            return t
    
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
