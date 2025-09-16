"""Core models for AI Gateway API contracts."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict


class EventType(str, Enum):
    """Event types for WebSocket communication."""
    CHAT = "chat"
    ACTION = "action" 
    UPDATE = "update"
    SCENE = "scene"
    TIMELINE = "timeline"
    LOG = "log"
    ERROR = "error"
    PROJECT = "project"

    # Plan events
    PLAN_GENERATED = "plan.generated"
    PLAN_REFINED = "plan.refined"
    PLAN_ACCEPTED = "plan.accepted"
    PLAN_EDITED = "plan.edited"
    
    # Task events
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_BLOCKED = "task.blocked"
    TASK_COMPLETED = "task.completed"
    
    # Context events
    CONTEXT_UPDATED = "context.updated"
    CONTEXT_GENERATED = "context.generated"
    
    # Artifact events
    ARTIFACT_CREATED = "artifact.created"
    ARTIFACT_VALIDATED = "artifact.validated"


class Envelope(BaseModel):
    """Event envelope for WebSocket messages.
    
    Provides a consistent wrapper for all event types sent between
    frontend and backend over WebSocket connections.
    
    Examples:
        Chat message:
        ```json
        {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "type": "chat",
            "project_id": "proj-456",
            "payload": {
                "message": "Hello, world!",
                "sender": "user"
            },
            "timestamp": "2024-01-01T12:00:00Z"
        }
        ```
        
        Error event:
        ```json
        {
            "id": "123e4567-e89b-12d3-a456-426614174001", 
            "type": "error",
            "project_id": null,
            "payload": {
                "error": "Connection failed",
                "code": 500
            },
            "timestamp": "2024-01-01T12:00:01Z"
        }
        ```
    """
    
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "type": "chat",
                    "project_id": "proj-456", 
                    "payload": {
                        "message": "Hello, world!",
                        "sender": "user"
                    },
                    "timestamp": "2024-01-01T12:00:00Z"
                }
            ]
        }
    )
    
    id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this event (UUID4)"
    )
    type: EventType = Field(
        description="Type of event being sent"
    )
    project_id: Optional[str] = Field(
        default=None,
        alias="project_id",
        description="ID of the project this event relates to"
    )
    payload: Dict[str, Any] = Field(
        description="Event-specific data payload (validated and serializable)"
    )
    correlation_id: Optional[str] = Field(
        default=None,
        alias="correlationId",
        description="Correlation identifier for tracing related events"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="UTC timestamp when the event was created (ISO-8601)"
    )


class Project(BaseModel):
    """Project model for game development projects.
    
    Represents a complete project with all metadata and configuration.
    
    Examples:
        ```json
        {
            "id": "proj-123e4567",
            "name": "My Awesome Game",
            "description": "A revolutionary RPG with AI-generated content",
            "status": "active",
            "createdAt": "2024-01-01T12:00:00Z",
            "updatedAt": "2024-01-02T14:30:00Z",
            "settings": {
                "genre": "RPG",
                "target_platform": "PC"
            }
        }
        ```
    """
    
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "id": "proj-123e4567",
                    "name": "My Awesome Game", 
                    "description": "A revolutionary RPG with AI-generated content",
                    "status": "active",
                    "createdAt": "2024-01-01T12:00:00Z",
                    "updatedAt": "2024-01-02T14:30:00Z",
                    "settings": {
                        "genre": "RPG",
                        "target_platform": "PC"
                    }
                }
            ]
        }
    )
    
    id: str = Field(
        description="Unique project identifier (e.g., 'proj-123abc')"
    )
    name: str = Field(
        min_length=1,
        max_length=100,
        description="Human-readable project name"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional project description"
    )
    status: str = Field(
        default="active",
        description="Project status (active, paused, archived)"
    )
    created_at: datetime = Field(
        alias="createdAt",
        description="UTC timestamp when project was created (ISO-8601)"
    )
    updated_at: datetime = Field(
        alias="updatedAt", 
        description="UTC timestamp when project was last updated (ISO-8601)"
    )
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Project-specific configuration and settings"
    )


class CreateProject(BaseModel):
    """Request model for creating new projects.
    
    Contains the minimal required information to create a new project.
    
    Examples:
        ```json
        {
            "name": "My New Game",
            "description": "An innovative puzzle platformer",
            "settings": {
                "genre": "Puzzle",
                "target_platform": "Mobile"
            }
        }
        ```
    """
    
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "name": "My New Game",
                    "description": "An innovative puzzle platformer", 
                    "settings": {
                        "genre": "Puzzle",
                        "target_platform": "Mobile"
                    }
                }
            ]
        }
    )
    
    name: str = Field(
        min_length=1,
        max_length=100,
        description="Human-readable project name"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional project description"
    )
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Initial project configuration and settings"
    )
