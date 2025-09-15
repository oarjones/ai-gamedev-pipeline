import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from sqlmodel.pool import StaticPool

# Import the main app and the global db object we want to patch
from gateway.app.main import app
import gateway.app.db as db_module

@pytest.fixture(scope="function")
def session() -> Generator[Session, None, None]:
    """Create a new in-memory database session for each test function."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(scope="function")
def client(session: Session, monkeypatch) -> Generator[TestClient, None, None]:
    """Create a test client that uses the in-memory database."""
    
    # Create a DatabaseManager instance that uses the in-memory engine
    in_memory_db_manager = db_module.DatabaseManager(db_path=":memory:")
    in_memory_db_manager.engine = session.get_bind()

    # Monkeypatch the global 'db' instance in the db module
    monkeypatch.setattr(db_module, "db", in_memory_db_manager)

    with TestClient(app) as c:
        yield c

@pytest.fixture
def sample_project(session: Session):
    """Create a sample project for tests."""
    from gateway.app.db import ProjectDB
    project = ProjectDB(
        id="test-project",
        name="Test Project",
        path="test-project",
        active=True,
        status="active"
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project

@pytest.fixture
def sample_task_plan(session: Session, sample_project):
    """Create sample task plan."""
    from gateway.app.db import TaskPlanDB
    plan = TaskPlanDB(
        project_id=sample_project.id,
        version=1,
        status="accepted",
        summary="Test plan"
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan