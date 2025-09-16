"""Smoke tests for model serialization/deserialization."""

import json
from datetime import datetime
from uuid import uuid4

import pytest

from app.models import CreateProject, Envelope, EventType, Project


class TestEventType:
    """Test EventType enum."""
    
    def test_all_event_types(self) -> None:
        """Test all event types are defined correctly."""
        expected_types = {
            "chat", "action", "update", "scene", "timeline", "log", "error", "project"
        }
        actual_types = {et.value for et in EventType}
        assert actual_types == expected_types
    
    def test_event_type_serialization(self) -> None:
        """Test EventType can be serialized to JSON."""
        event_type = EventType.CHAT
        assert event_type.value == "chat"
        assert json.dumps(event_type.value) == '"chat"'


class TestEnvelope:
    """Test Envelope model."""
    
    def test_envelope_creation_with_defaults(self) -> None:
        """Test Envelope creates with default values."""
        envelope = Envelope(
            type=EventType.CHAT,
            payload={"message": "Hello"}
        )
        
        assert envelope.type == EventType.CHAT
        assert envelope.payload == {"message": "Hello"}
        assert envelope.project_id is None
        assert isinstance(envelope.id, type(uuid4()))
        assert isinstance(envelope.timestamp, datetime)
    
    def test_envelope_serialization(self) -> None:
        """Test Envelope serializes to JSON correctly."""
        envelope = Envelope(
            type=EventType.ERROR,
            project_id="proj-123",  # Use alias directly
            payload={"error": "Something went wrong", "code": 500}
        )
        
        # Test model_dump with alias
        data = envelope.model_dump(by_alias=True)
        assert "project_id" in data
        assert data["project_id"] == "proj-123"
        assert data["type"] == "error"
        
        # Test JSON serialization
        json_str = envelope.model_dump_json(by_alias=True)
        parsed = json.loads(json_str)
        assert parsed["project_id"] == "proj-123"
        assert parsed["type"] == "error"
        assert parsed["payload"]["error"] == "Something went wrong"
    
    def test_envelope_deserialization(self) -> None:
        """Test Envelope can be created from JSON."""
        data = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "type": "action",
            "project_id": "proj-456",
            "payload": {"action": "click", "target": "button"},
            "timestamp": "2024-01-01T12:00:00Z"
        }
        
        envelope = Envelope.model_validate(data)
        assert envelope.type == EventType.ACTION
        assert envelope.project_id == "proj-456"
        assert envelope.payload == {"action": "click", "target": "button"}
    
    def test_envelope_validation_strict(self) -> None:
        """Test Envelope validates strictly."""
        with pytest.raises(ValueError):
            Envelope(
                type="invalid_type",  # type: ignore
                payload={"test": "data"}
            )


class TestProject:
    """Test Project model."""
    
    def test_project_serialization(self) -> None:
        """Test Project serializes correctly."""
        now = datetime.utcnow()
        project = Project(
            id="proj-123",
            name="Test Game",
            description="A test game",
            status="active",
            createdAt=now,  # Use alias directly
            updatedAt=now,  # Use alias directly
            settings={"genre": "RPG"}
        )
        
        data = project.model_dump(by_alias=True)
        assert data["id"] == "proj-123"
        assert data["name"] == "Test Game"
        assert "createdAt" in data
        assert "updatedAt" in data
        assert data["settings"]["genre"] == "RPG"
    
    def test_project_deserialization(self) -> None:
        """Test Project can be created from JSON."""
        data = {
            "id": "proj-456", 
            "name": "My Game",
            "description": "Cool game",
            "status": "active",
            "createdAt": "2024-01-01T12:00:00Z",
            "updatedAt": "2024-01-01T12:00:00Z",
            "settings": {"platform": "PC"}
        }
        
        project = Project.model_validate(data)
        assert project.id == "proj-456"
        assert project.name == "My Game"
        assert project.settings["platform"] == "PC"


class TestCreateProject:
    """Test CreateProject model."""
    
    def test_create_project_minimal(self) -> None:
        """Test CreateProject with minimal data."""
        create_data = CreateProject(name="New Game")
        
        assert create_data.name == "New Game"
        assert create_data.description is None
        assert create_data.settings == {}
    
    def test_create_project_full(self) -> None:
        """Test CreateProject with all fields."""
        create_data = CreateProject(
            name="Full Game",
            description="A complete game description",
            settings={"genre": "Action", "platform": "Multi"}
        )
        
        assert create_data.name == "Full Game"
        assert create_data.description == "A complete game description"
        assert create_data.settings["genre"] == "Action"
    
    def test_create_project_validation(self) -> None:
        """Test CreateProject validation."""
        with pytest.raises(ValueError):
            CreateProject(name="")  # Empty name should fail
        
        with pytest.raises(ValueError):
            CreateProject(name="x" * 101)  # Too long name should fail


class TestModelsIntegration:
    """Integration tests for models working together."""
    
    def test_envelope_with_project_event(self) -> None:
        """Test Envelope containing project-related event."""
        envelope = Envelope(
            type=EventType.UPDATE,
            project_id="proj-789",  # Use alias directly
            payload={
                "project": {
                    "id": "proj-789",
                    "name": "Updated Game",
                    "status": "active"
                },
                "changes": ["name", "status"]
            }
        )
        
        # Serialize and deserialize
        json_str = envelope.model_dump_json(by_alias=True)
        restored = Envelope.model_validate_json(json_str)
        
        assert restored.type == EventType.UPDATE
        assert restored.project_id == "proj-789"
        assert restored.payload["project"]["name"] == "Updated Game"
