from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ContextResponse(BaseModel):
    version: int = Field(..., description="Context version number")
    current_task: Optional[str] = Field(default=None, description="Code of the current task, if any")
    done_tasks: List[str] = Field(default_factory=list, description="List of completed task codes")
    pending_tasks: int = Field(..., description="Number of remaining tasks")
    summary: str = Field(default="", description="High-level summary of project state")
    decisions: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    last_update: Optional[str] = Field(default=None, description="ISO timestamp of last update")

    class Config:
        json_schema_extra = {
            "example": {
                "version": 2,
                "current_task": "T-003",
                "done_tasks": ["T-001", "T-002"],
                "pending_tasks": 7,
                "summary": "Game prototype initialized; player controller implemented.",
                "decisions": ["Use URP", "Tilemap for levels"],
                "open_questions": ["Enemy AI complexity"],
                "risks": ["Scope creep"],
                "last_update": "2025-09-15T12:34:56Z",
            }
        }


class TaskItem(BaseModel):
    code: str
    title: str
    description: str = ""
    dependencies: List[str] = []
    priority: int = 1
    status: Optional[str] = None


class TaskPlanResponse(BaseModel):
    id: int
    version: int
    status: str
    summary: Optional[str] = None
    created_by: str
    created_at: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    tasks: List[TaskItem]

    class Config:
        json_schema_extra = {
            "example": {
                "id": 42,
                "version": 3,
                "status": "proposed",
                "summary": "Initial gameplay loop",
                "created_by": "ai",
                "created_at": "2025-09-15T10:00:00Z",
                "stats": {"total": 10, "completed": 2, "blocked": 1, "progress": 20.0},
                "tasks": [
                    {"code": "T-001", "title": "Bootstrap project", "description": "...", "dependencies": [], "priority": 1},
                    {"code": "T-002", "title": "Player controller", "description": "...", "dependencies": ["T-001"], "priority": 1},
                ],
            }
        }


class ArtifactResponse(BaseModel):
    id: int
    type: str
    category: Optional[str] = None
    path: str
    size_bytes: Optional[int] = None
    validation_status: str
    meta: Dict[str, Any] = {}
    created_at: str

    class Config:
        json_schema_extra = {
            "example": {
                "id": 101,
                "type": "png",
                "category": "screenshot",
                "path": "projects/demo/artifacts/snap.png",
                "size_bytes": 123456,
                "validation_status": "valid",
                "meta": {"source": "unity"},
                "created_at": "2025-09-15T12:00:00Z",
            }
        }

