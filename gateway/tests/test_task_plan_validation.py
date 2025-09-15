import json

from gateway.app.services.task_plan_service import TaskPlanService


def _make_service():
    return TaskPlanService()


def test_valid_plan_passes():
    s = _make_service()
    tasks = [
        {
            "code": "T-001",
            "title": "Setup project",
            "description": "Create scaffolding",
            "dependencies": [],
            "mcp_tools": ["filesystem"],
            "deliverables": ["project skeleton"],
            "acceptance_criteria": ["Project builds"],
            "estimates": {"story_points": 3, "time_hours": 1},
            "priority": 1,
        },
        {
            "code": "T-002",
            "title": "Add feature",
            "description": "Implement X",
            "dependencies": ["T-001"],
            "mcp_tools": ["unity"],
            "deliverables": ["working feature"],
            "acceptance_criteria": ["All tests pass"],
            "estimates": {"story_points": 5, "time_hours": 3},
            "priority": 2,
        },
    ]
    repaired, warnings = s._validate_and_repair(tasks)
    assert len(repaired) == 2
    assert warnings == []
    assert repaired[1]["dependencies"] == ["T-001"]


def test_repairable_missing_codes():
    s = _make_service()
    tasks = [
        {
            "title": "First",
            "description": "...",
            "acceptance_criteria": "ok",
        },
        {
            "title": "Second",
            "dependencies": ["T-999"],  # will be normalized out
            "acceptance_criteria": ["done"],
        },
    ]
    repaired, warnings = s._validate_and_repair(tasks)
    assert len(repaired) == 2
    assert repaired[0]["code"].startswith("T-")
    assert repaired[1]["dependencies"] == []


def test_reject_on_cycle():
    s = _make_service()
    tasks = [
        {"code": "T-001", "title": "A", "acceptance_criteria": ["a"], "dependencies": ["T-002"]},
        {"code": "T-002", "title": "B", "acceptance_criteria": ["b"], "dependencies": ["T-001"]},
    ]
    repaired, warnings = s._validate_and_repair(tasks)
    assert s._has_circular_dependencies(repaired) is True

