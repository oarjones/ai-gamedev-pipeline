"""Tests for the TaskExecutionService."""

import pytest
import json
import shutil
from pathlib import Path
from unittest.mock import patch, AsyncMock

from gateway.app.services.task_execution_service import task_execution_service
from gateway.app.db import db, ProjectDB, TaskDB

# A more complex task setup for testing scoring and dependency logic
TASKS_DATA = [
    # code, title, status, priority, story_points, deps
    ("A-1", "Highest Prio, No Deps", "pending", 1, 5, []),
    ("A-2", "High Prio, Met Deps", "pending", 1, 8, ["C-1"]),
    ("B-1", "Mid Prio, Unmet Deps", "pending", 2, 5, ["B-2"]),
    ("B-2", "Mid Prio, No Deps", "pending", 2, 5, []),
    ("C-1", "Low Prio, Done", "done", 3, 5, []),
]

@pytest.fixture(scope="function")
def project_with_task_mix():
    project_id = "test-exec-service-project"
    project_path = Path(f"projects/{project_id}")

    # Clean up previous runs
    if project_path.exists():
        shutil.rmtree(project_path)
    with db.get_session() as session:
        project_db = session.get(ProjectDB, project_id)
        if project_db:
            from sqlmodel import select
            for task in session.exec(select(TaskDB).where(TaskDB.project_id == project_id)).all():
                session.delete(task)
            session.commit()
            db.delete_project(project_id)

    # Create project and tasks
    project = ProjectDB(id=project_id, name="Exec Test Project", path=str(project_path))
    db.create_project(project)
    with db.get_session() as session:
        for idx, (code, title, status, prio, sp, deps) in enumerate(TASKS_DATA):
            task = TaskDB(
                project_id=project_id, code=code, task_id=code, title=title, status=status, 
                priority=prio, estimates=json.dumps({"story_points": sp}), 
                deps_json=json.dumps(deps), idx=idx
            )
            session.add(task)
        session.commit()

    yield project_id

    # Teardown
    if project_path.exists():
        shutil.rmtree(project_path)
    with db.get_session() as session:
        project_db = session.get(ProjectDB, project_id)
        if project_db:
            from sqlmodel import select
            for task in session.exec(select(TaskDB).where(TaskDB.project_id == project_id)).all():
                session.delete(task)
            session.commit()
            db.delete_project(project_id)

def test_get_next_task_scoring(project_with_task_mix):
    project_id = project_with_task_mix
    
    # Expected: A-2 (prio 1, sp 8) should be chosen over A-1 (prio 1, sp 5)
    # because it has higher story points (more value).
    next_task = task_execution_service.get_next_available_task(project_id)
    assert next_task is not None
    assert next_task.code == "A-2"

    # Mark A-2 as done
    with db.get_session() as session:
        from sqlmodel import select
        task_a2 = session.exec(select(TaskDB).where(TaskDB.code == "A-2")).one()
        task_a2.status = "done"
        session.add(task_a2)
        session.commit()

    # Expected: A-1 (prio 1, sp 5) should be next.
    next_task = task_execution_service.get_next_available_task(project_id)
    assert next_task is not None
    assert next_task.code == "A-1"

@pytest.mark.asyncio
async def test_start_and_complete_task_cycle(project_with_task_mix):
    project_id = project_with_task_mix

    # Get the first available task (A-2)
    task_to_start = task_execution_service.get_next_available_task(project_id)
    assert task_to_start.code == "A-2"

    with patch('gateway.app.services.task_execution_service.manager', new_callable=AsyncMock) as mock_manager:
        # Start the task
        started_task = await task_execution_service.start_task(task_to_start.id)
        assert started_task.status == "in_progress"
        assert started_task.started_at is not None

        # Check project's current task
        with db.get_session() as session:
            project = session.get(ProjectDB, project_id)
            assert project.current_task_id == task_to_start.id
        
        # Check for 'task.started' event
        mock_manager.broadcast_project.assert_called_once()
        call_args, _ = mock_manager.broadcast_project.call_args
        event_payload = json.loads(call_args[1])['payload']
        assert event_payload['event'] == 'task.started'

    with patch('gateway.app.services.task_execution_service.manager', new_callable=AsyncMock) as mock_manager, \
         patch.object(task_execution_service, 'start_task', new_callable=AsyncMock) as mock_start_next, \
         patch.object(task_execution_service.context_service, 'generate_context_after_task') as mock_gen_context:

        # Complete the task
        completed_task = await task_execution_service.complete_task(task_to_start.id)
        assert completed_task.status == "done"

        # Verify context was generated
        mock_gen_context.assert_called_once_with(project_id, task_to_start.id)

        # Verify next task was automatically started
        mock_start_next.assert_called_once()
        
        # Verify 'task.completed' event
        mock_manager.broadcast_project.assert_called_once()
        call_args, _ = mock_manager.broadcast_project.call_args
        event_payload = json.loads(call_args[1])['payload']
        assert event_payload['event'] == 'task.completed'
        assert event_payload['next_task'] is not None

@pytest.mark.asyncio
@patch('gateway.app.services.task_execution_service.unified_agent', new_callable=AsyncMock)
async def test_execute_task_with_agent(mock_agent, project_with_task_mix):
    project_id = project_with_task_mix
    task = task_execution_service.get_next_available_task(project_id)

    # Mock the agent status to prevent trying to start it
    mock_agent.status.return_value.running = True

    # Consume the async generator
    results = [res async for res in task_execution_service.execute_task_with_agent(task.id)]

    # Verify prompt was constructed and sent
    mock_agent.send.assert_called_once()
    call_args, _ = mock_agent.send.call_args
    prompt = call_args[0]
    assert "CONTEXTO GLOBAL DEL PROYECTO" in prompt
    assert f"TAREA ACTUAL: {task.code}" in prompt

    # Verify yielded messages
    assert results[0]["type"] == "started"