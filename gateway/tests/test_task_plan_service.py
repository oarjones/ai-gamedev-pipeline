import pytest
import json
from gateway.app.services.task_plan_service import TaskPlanService

def test_create_plan(session, sample_project):
    """Test creating a new plan."""
    service = TaskPlanService()
    
    tasks = [
        {
            "code": "T-001",
            "title": "Setup project",
            "description": "Initialize Unity project",
            "dependencies": [],
            "mcp_tools": ["unity"],
            "deliverables": ["ProjectSettings/*"],
            "estimates": {"story_points": 3, "time_hours": 2},
            "priority": 1
        }
    ]
    
    # We need to use the session from the fixture
    service.db.get_session = lambda: session

    plan = service.create_plan(sample_project.id, tasks)
    
    assert plan.version == 1
    assert plan.status == "proposed"
    assert plan.project_id == sample_project.id

def test_accept_plan(session, sample_task_plan):
    """Test accepting a plan."""
    service = TaskPlanService()
    service.db.get_session = lambda: session

    accepted = service.accept_plan(sample_task_plan.id)
    
    assert accepted.status == "accepted"

def test_detect_circular_dependencies():
    """Test circular dependency detection."""
    service = TaskPlanService()
    
    tasks = [
        {"code": "T-001", "dependencies": ["T-002"]},
        {"code": "T-002", "dependencies": ["T-001"]}
    ]
    
    has_circular = service._has_circular_dependencies(tasks)
    assert has_circular == True
