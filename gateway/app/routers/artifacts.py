from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from gateway.app.services.artifact_service import artifact_service
from gateway.app.models.api_responses import ArtifactResponse

router = APIRouter()

class RegisterArtifactRequest(BaseModel):
    artifact_type: str = Field(..., description="Type of the artifact (e.g., 'png', 'fbx', 'log')")
    path: str = Field(..., description="Absolute path to the artifact file")
    meta: Dict[str, Any] = Field(default_factory=dict, description="Optional metadata")
    category: str = None

@router.get(
    "/tasks/{task_id}/artifacts",
    summary="List artifacts for a task",
    description="Returns all artifacts registered for a given task.",
    response_model=List[ArtifactResponse],
)
async def list_task_artifacts(task_id: int):
    return artifact_service.list_task_artifacts(task_id)

@router.post(
    "/tasks/{task_id}/artifacts",
    summary="Register a new artifact for a task",
    description="Registers a new artifact and returns its identifier.",
)
async def register_artifact(task_id: int, request: RegisterArtifactRequest):
    try:
        artifact = artifact_service.register_artifact(
            task_id=task_id,
            artifact_type=request.artifact_type,
            path=request.path,
            meta=request.meta,
            category=request.category
        )
        return {"id": artifact.id, "path": artifact.path}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post(
    "/artifacts/{artifact_id}/validate",
    summary="Validate an artifact",
    description="Validates file existence and basic format.",
)
async def validate_artifact(artifact_id: int):
    is_valid = artifact_service.validate_artifact(artifact_id)
    return {"artifact_id": artifact_id, "is_valid": is_valid}

@router.post(
    "/tasks/{task_id}/capture/unity",
    summary="Capture artifacts from Unity",
    description="Captures a screenshot and scene data from Unity for the task.",
)
async def capture_unity_artifacts(task_id: int):
    try:
        artifacts = artifact_service.capture_from_unity(task_id)
        return {"captured_artifacts": [a.id for a in artifacts]}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to capture from Unity: {e}")

@router.get(
    "/tasks/{task_id}/report",
    summary="Generate a markdown report for a task",
    description="Generates a markdown report summarizing task details and artifacts.",
)
async def get_task_report(task_id: int):
    report = artifact_service.generate_task_report(task_id)
    return {"task_id": task_id, "report": report}
