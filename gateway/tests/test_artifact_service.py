import pytest
import json
import shutil
from pathlib import Path

from gateway.app.services.artifact_service import artifact_service
from gateway.app.db import TaskDB, ArtifactDB

# The 'session' and 'sample_project' fixtures are defined in conftest.py

@pytest.fixture
def sample_task(session, sample_project):
    """Create a sample task for artifact tests."""
    task = TaskDB(project_id=sample_project.id, code="ART-01", task_id="ART-01", title="Artifact Task", acceptance="Criteria")
    session.add(task)
    session.commit()
    session.refresh(task)
    return task

def test_register_and_list_artifact(session, sample_task):
    # The artifact_service uses the global `db` object.
    # The conftest client fixture patches this, but these are not API tests.
    # For this service test, we need to patch the db used by the service instance.
    artifact_service.db.get_session = lambda: session

    # Create a dummy artifact file
    dummy_file = Path("dummy_artifact.txt")
    dummy_file.write_text("hello world")

    # Register it
    artifact = artifact_service.register_artifact(
        task_id=sample_task.id,
        artifact_type="txt",
        path=str(dummy_file),
        category="document"
    )

    assert artifact is not None
    assert artifact.task_id == sample_task.id
    assert artifact.category == "document"
    assert artifact.size_bytes == 11

    # List artifacts for the task
    artifacts_list = artifact_service.list_task_artifacts(sample_task.id)
    assert len(artifacts_list) == 1
    assert artifacts_list[0]["id"] == artifact.id

    # Clean up dummy file
    dummy_file.unlink()
    shutil.rmtree(f"projects/{sample_task.project_id}", ignore_errors=True)

def test_generate_task_report(session, sample_task):
    artifact_service.db.get_session = lambda: session

    # Create a dummy artifact file and register it
    dummy_file = Path("dummy_report_artifact.log")
    dummy_file.write_text("log message")
    artifact_service.register_artifact(sample_task.id, "log", str(dummy_file))

    # Generate report
    report = artifact_service.generate_task_report(sample_task.id)

    assert f"# Reporte de Tarea: {sample_task.code}" in report
    assert f"## {sample_task.title}" in report
    assert "### Criterios de Aceptación" in report
    assert "dummy_report_artifact.log" in report

    # Clean up
    dummy_file.unlink()
    shutil.rmtree(f"projects/{sample_task.project_id}", ignore_errors=True)