"""REST API endpoints for project management."""

from typing import List

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from app.models.core import CreateProject, Project
from app.services.projects import project_service


router = APIRouter()


@router.get("", response_model=List[Project])
async def list_projects() -> List[Project]:
    """List all projects.
    
    Returns a list of all projects with their current status.
    The active project will have status='active'.
    """
    try:
        projects = project_service.list_projects()
        return projects
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list projects: {str(e)}"
        )


@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: str) -> Project:
    """Get a specific project by ID.
    
    Args:
        project_id: Unique project identifier
        
    Returns:
        Project details
        
    Raises:
        HTTPException: 404 if project not found
    """
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found"
        )
    return project


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(create_data: CreateProject) -> Project:
    """Create a new project.
    
    Creates both the database entry and filesystem structure:
    - projects/{project_id}/
    - projects/{project_id}/.agp/project.json
    - projects/{project_id}/context/
    - projects/{project_id}/logs/
    
    Args:
        create_data: Project creation data
        
    Returns:
        Created project
        
    Raises:
        HTTPException: 400 if project name is invalid
    """
    try:
        project = project_service.create_project(create_data)
        return project
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {str(e)}"
        )


@router.patch("/{project_id}/select")
async def select_active_project(project_id: str) -> JSONResponse:
    """Set a project as the active project.
    
    Only one project can be active at a time. This endpoint will:
    1. Deactivate the currently active project (if any)
    2. Set the specified project as active
    
    Args:
        project_id: ID of project to activate
        
    Returns:
        Success confirmation
        
    Raises:
        HTTPException: 404 if project not found
    """
    success = project_service.select_active_project(project_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found"
        )
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": f"Project '{project_id}' is now active",
            "project_id": project_id
        }
    )


@router.get("/active/current", response_model=Project | None)
async def get_active_project() -> Project | None:
    """Get the currently active project.
    
    Returns:
        Active project if any, null otherwise
    """
    try:
        return project_service.get_active_project()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active project: {str(e)}"
        )


@router.delete("/{project_id}")
async def delete_project(project_id: str) -> JSONResponse:
    """Delete a project from the registry.
    
    Note: This only removes the project from the database.
    The filesystem structure is preserved for safety.
    
    Args:
        project_id: ID of project to delete
        
    Returns:
        Success confirmation
        
    Raises:
        HTTPException: 404 if project not found
    """
    success = project_service.delete_project(project_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found"
        )
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": f"Project '{project_id}' deleted from registry",
            "project_id": project_id,
            "note": "Filesystem structure preserved"
        }
    )