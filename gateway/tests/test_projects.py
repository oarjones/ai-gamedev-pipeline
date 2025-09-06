"""Tests for project management functionality."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import DatabaseManager, ProjectDB
from app.main import app
from app.services.projects import ProjectService


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    # Cleanup
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def test_db(temp_dir):
    """Create a test database."""
    db_path = temp_dir / "test.db"
    return DatabaseManager(str(db_path))


@pytest.fixture
def test_project_service(temp_dir):
    """Create a project service with test database and temp directory."""
    projects_root = temp_dir / "test_projects"
    # Create test database instance
    db_path = temp_dir / "test.db"
    test_db_instance = DatabaseManager(str(db_path))
    # Create service with test database
    service = ProjectService(str(projects_root), test_db_instance)
    return service


@pytest.fixture
def client(temp_dir):
    """Create test client with isolated database."""
    # Override global project service with test instance
    from app.services.projects import project_service
    from app.services.projects import ProjectService
    from app.db import DatabaseManager
    
    # Create test database and service
    db_path = temp_dir / "api_test.db"
    test_db = DatabaseManager(str(db_path))
    projects_root = temp_dir / "api_test_projects"
    test_service = ProjectService(str(projects_root), test_db)
    
    # Patch the global service
    import app.routers.projects
    original_service = app.routers.projects.project_service
    app.routers.projects.project_service = test_service
    
    yield TestClient(app)
    
    # Restore original service
    app.routers.projects.project_service = original_service


class TestProjectService:
    """Test ProjectService functionality."""
    
    def test_sanitize_name(self, test_project_service):
        """Test name sanitization."""
        service = test_project_service
        
        # Basic sanitization
        assert service._sanitize_name("My Game Project") == "my-game-project"
        assert service._sanitize_name("Test_Game_123") == "test-game-123"
        
        # Special characters removal
        assert service._sanitize_name("Game@2024!") == "game2024"
        
        # Multiple hyphens collapse
        assert service._sanitize_name("My---Game") == "my-game"
        
        # Leading/trailing hyphens removed
        assert service._sanitize_name("-Game-") == "game"
        
        # Empty result raises error
        with pytest.raises(ValueError):
            service._sanitize_name("!@#$%")
    
    def test_generate_project_id_unique(self, test_project_service):
        """Test unique project ID generation."""
        service = test_project_service
        
        # First project gets base name
        id1 = service._generate_project_id("Test Game")
        assert id1 == "test-game"
        
        # Create project with that ID
        project_db = ProjectDB(id=id1, name="Test Game", path=id1)
        service.db.create_project(project_db)
        
        # Second project with same name gets suffix
        id2 = service._generate_project_id("Test Game")
        assert id2 == "test-game-1"
    
    def test_create_project_structure(self, test_project_service):
        """Test filesystem structure creation."""
        service = test_project_service
        project_dir = service._create_project_structure("test-project", "Test Project")
        
        # Check directory structure
        assert project_dir.exists()
        assert (project_dir / ".agp").exists()
        assert (project_dir / ".agp" / "project.json").exists()
        assert (project_dir / "context").exists()
        assert (project_dir / "logs").exists()
        
        # Check project.json content
        with open(project_dir / ".agp" / "project.json", "r") as f:
            project_data = json.load(f)
            assert project_data["id"] == "test-project"
            assert project_data["name"] == "Test Project"
            assert project_data["type"] == "ai-gamedev-project"
            assert "created_at" in project_data
            assert "settings" in project_data
    
    def test_create_project_full_flow(self, test_project_service):
        """Test complete project creation flow."""
        from app.models.core import CreateProject
        
        service = test_project_service
        
        create_data = CreateProject(
            name="My Amazing Game",
            description="A test game project",
            settings={"genre": "RPG"}
        )
        
        project = service.create_project(create_data)
        
        # Check returned project
        assert project.id == "my-amazing-game"
        assert project.name == "My Amazing Game"
        assert project.status == "inactive"
        assert project.settings.get("genre") == "RPG"
        
        # Check database
        db_project = service.db.get_project("my-amazing-game")
        assert db_project is not None
        assert db_project.name == "My Amazing Game"
        assert db_project.active == False
        
        # Check filesystem
        project_dir = service.projects_root / "my-amazing-game"
        assert project_dir.exists()
        assert (project_dir / ".agp" / "project.json").exists()
    
    def test_select_active_project(self, test_project_service):
        """Test project activation."""
        from app.models.core import CreateProject
        
        service = test_project_service
        
        # Create two projects
        project1 = service.create_project(CreateProject(name="Project 1"))
        project2 = service.create_project(CreateProject(name="Project 2"))
        
        # Initially no project is active
        assert service.get_active_project() is None
        
        # Activate first project
        success = service.select_active_project(project1.id)
        assert success == True
        
        active = service.get_active_project()
        assert active is not None
        assert active.id == project1.id
        assert active.status == "active"
        
        # Activate second project (should deactivate first)
        success = service.select_active_project(project2.id)
        assert success == True
        
        active = service.get_active_project()
        assert active.id == project2.id
        
        # First project should no longer be active
        project1_current = service.get_project(project1.id)
        assert project1_current.status == "inactive"
    
    def test_list_projects(self, test_project_service):
        """Test project listing."""
        from app.models.core import CreateProject
        
        service = test_project_service
        
        # Initially empty
        projects = service.list_projects()
        assert len(projects) == 0
        
        # Create projects
        project1 = service.create_project(CreateProject(name="Game 1"))
        project2 = service.create_project(CreateProject(name="Game 2"))
        service.select_active_project(project1.id)
        
        # List should show both with correct status
        projects = service.list_projects()
        assert len(projects) == 2
        
        active_projects = [p for p in projects if p.status == "active"]
        inactive_projects = [p for p in projects if p.status == "inactive"]
        
        assert len(active_projects) == 1
        assert len(inactive_projects) == 1
        assert active_projects[0].id == project1.id


class TestProjectAPI:
    """Test project REST API endpoints."""
    
    def test_health_check(self, client):
        """Test basic health check still works."""
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_list_projects_empty(self, client):
        """Test listing projects when none exist."""
        response = client.get("/api/v1/projects")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_create_project(self, client):
        """Test project creation via API."""
        import uuid
        unique_name = f"Test API Project {uuid.uuid4().hex[:8]}"
        expected_id = unique_name.lower().replace(" ", "-").replace("-", "-")[:20]  # Truncate for predictability
        
        project_data = {
            "name": unique_name,
            "description": "Created via API",
            "settings": {"test": True}
        }
        
        response = client.post("/api/v1/projects", json=project_data)
        assert response.status_code == 201
        
        project = response.json()
        assert project["name"] == unique_name
        assert project["status"] == "inactive"
        assert project["settings"]["test"] == True
        
        # Verify filesystem was created
        project_dir = Path("projects") / project["id"]
        assert project_dir.exists()
        assert (project_dir / ".agp" / "project.json").exists()
    
    def test_create_project_invalid_name(self, client):
        """Test project creation with invalid name."""
        project_data = {"name": "!@#$%"}
        
        response = client.post("/api/v1/projects", json=project_data)
        assert response.status_code == 400
        assert "alphanumeric character" in response.json()["detail"]
    
    def test_get_project(self, client):
        """Test getting specific project."""
        # Create project first
        create_data = {"name": "Get Test Project"}
        create_response = client.post("/api/v1/projects", json=create_data)
        project_id = create_response.json()["id"]
        
        # Get project
        response = client.get(f"/api/v1/projects/{project_id}")
        assert response.status_code == 200
        
        project = response.json()
        assert project["id"] == project_id
        assert project["name"] == "Get Test Project"
    
    def test_get_project_not_found(self, client):
        """Test getting non-existent project."""
        response = client.get("/api/v1/projects/nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_select_active_project(self, client):
        """Test setting active project."""
        # Create project
        create_data = {"name": "Active Test Project"}
        create_response = client.post("/api/v1/projects", json=create_data)
        project_id = create_response.json()["id"]
        
        # Set as active
        response = client.patch(f"/api/v1/projects/{project_id}/select")
        assert response.status_code == 200
        assert "now active" in response.json()["message"]
        
        # Verify it's active
        get_response = client.get(f"/api/v1/projects/{project_id}")
        assert get_response.json()["status"] == "active"
    
    def test_select_active_project_not_found(self, client):
        """Test setting non-existent project as active."""
        response = client.patch("/api/v1/projects/nonexistent/select")
        assert response.status_code == 404
    
    def test_get_active_project(self, client):
        """Test getting currently active project."""
        # Initially no active project
        response = client.get("/api/v1/projects/active/current")
        assert response.status_code == 200
        assert response.json() is None
        
        # Create and activate project
        create_data = {"name": "Current Active Project"}
        create_response = client.post("/api/v1/projects", json=create_data)
        project_id = create_response.json()["id"]
        
        client.patch(f"/api/v1/projects/{project_id}/select")
        
        # Should return the active project
        response = client.get("/api/v1/projects/active/current")
        assert response.status_code == 200
        
        active_project = response.json()
        assert active_project["id"] == project_id
        assert active_project["status"] == "active"
    
    def test_full_workflow(self, client):
        """Test complete project management workflow."""
        # 1. List projects (should be empty)
        response = client.get("/api/v1/projects")
        assert len(response.json()) == 0
        
        # 2. Create first project
        project1_data = {"name": "Workflow Project 1", "description": "First project"}
        response = client.post("/api/v1/projects", json=project1_data)
        project1 = response.json()
        
        # 3. Create second project
        project2_data = {"name": "Workflow Project 2", "description": "Second project"}
        response = client.post("/api/v1/projects", json=project2_data)
        project2 = response.json()
        
        # 4. List projects (should show 2, both inactive)
        response = client.get("/api/v1/projects")
        projects = response.json()
        assert len(projects) == 2
        assert all(p["status"] == "inactive" for p in projects)
        
        # 5. Set first project as active
        response = client.patch(f"/api/v1/projects/{project1['id']}/select")
        assert response.status_code == 200
        
        # 6. Verify first is active, second is inactive
        response = client.get("/api/v1/projects")
        projects = response.json()
        active_projects = [p for p in projects if p["status"] == "active"]
        assert len(active_projects) == 1
        assert active_projects[0]["id"] == project1["id"]
        
        # 7. Switch active to second project
        response = client.patch(f"/api/v1/projects/{project2['id']}/select")
        assert response.status_code == 200
        
        # 8. Verify only second is now active
        response = client.get("/api/v1/projects/active/current")
        active_project = response.json()
        assert active_project["id"] == project2["id"]