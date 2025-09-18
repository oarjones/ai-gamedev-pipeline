import pytest
import json
import shutil
from pathlib import Path

from sqlmodel import select

from app.services.context_service import context_service
from app.db import TaskDB, ContextDB

# The 'session' and 'sample_project' fixtures are defined in conftest.py

@pytest.fixture
def project_with_tasks(session, sample_project):
    """Create tasks with dependencies for context testing."""
    tasks_data = [
        TaskDB(project_id=sample_project.id, code="T-001", task_id="T-001", title="Task 1", status="pending", priority=1, deps_json=json.dumps([])),
        TaskDB(project_id=sample_project.id, code="T-002", task_id="T-002", title="Task 2", status="pending", priority=2, deps_json=json.dumps(["T-001"])),
        TaskDB(project_id=sample_project.id, code="T-003", task_id="T-003", title="Task 3", status="done", priority=3, deps_json=json.dumps([])),
        TaskDB(project_id=sample_project.id, code="T-004", task_id="T-004", title="Task 4", status="pending", priority=4, deps_json=json.dumps(["T-003"])),
    ]
    for task in tasks_data:
        session.add(task)
    session.commit()
    return sample_project.id

def test_create_and_get_context(session, project_with_tasks):
    project_id = project_with_tasks
    context_service.db.get_session = lambda: session
    context_content = {"key": "value", "version": 1}

    # Create context
    created_context_db = context_service.create_context(project_id, context_content, created_by="test")
    assert created_context_db is not None
    assert created_context_db.version == 1

    # Get active context
    active_context = context_service.get_active_context(project_id)
    assert active_context is not None
    assert active_context["key"] == "value"

    # Clean up created files
    shutil.rmtree(f"projects/{project_id}", ignore_errors=True)

def test_get_next_available_task(session, project_with_tasks):
    project_id = project_with_tasks
    context_service.db.get_session = lambda: session

    # T-001 has top priority and no dependencies
    next_task = context_service._get_next_available_task(project_id)
    assert next_task is not None
    assert next_task.code == "T-001"

def test_generate_context_after_task(session, project_with_tasks):
    project_id = project_with_tasks
    context_service.db.get_session = lambda: session

    # Get task T-001 to mark it as done
    task_1 = session.exec(select(TaskDB).where(TaskDB.code == "T-001")).one()
    task_1.status = "done"
    session.add(task_1)
    session.commit()
    
    # Generate the new context
    new_context = context_service.generate_context_after_task(project_id, task_1.id)

    # With T-001 done, T-002 should be next
    assert new_context["current_task"] == "T-002"
    assert "T-001" in new_context["done_tasks"]

    # Clean up created files
    shutil.rmtree(f"projects/{project_id}", ignore_errors=True)