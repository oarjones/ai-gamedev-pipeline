"""REST API endpoints for project management."""

from typing import List

from fastapi import APIRouter, HTTPException, status, Query
import logging
from fastapi.responses import JSONResponse

from app.models.core import CreateProject, Project
from app.services.projects import project_service
from app.services.unified_agent import agent as unified_agent
from app.ws.events import manager
from app.models import Envelope, EventType
from pathlib import Path


router = APIRouter()


@router.get("", response_model=List[Project])
async def list_projects() -> List[Project]:
    """List all projects.
    
    Returns a list of all projects with their current status.
    The active project will have status='active'.
    """
    logger = logging.getLogger(__name__)
    try:
        projects = project_service.list_projects()
        logger.debug("Returning %d projects", len(projects))
        return projects
    except Exception as e:
        logger.exception("List projects failed: %s", e)
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
    prev = project_service.get_active_project()
    success = project_service.select_active_project(project_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found"
        )
    # Start/stop runner according to new selection
    start_ok = True
    start_error: str | None = None
    # Also ensure local processes (Unity, Unity Bridge, Blender optional)
    system_status: list[dict] | None = None
    try:
        await unified_agent.stop()
    except Exception:
        pass
    new_proj = project_service.get_project(project_id)
    if new_proj:
        try:
            # Ensure baseline Unity files (version, packages, plugins)
            try:
                from app.services.projects import project_service as _ps
                _ps.ensure_unity_baseline(Path("projects") / new_proj.id)
            except Exception:
                pass
            # Start Unity + Bridges before agent to ensure connectivity
            try:
                from app.services.process_manager import process_manager
                system_status = process_manager.start_sequence(new_proj.id)
            except Exception as _sys_err:
                # Non-fatal: continue but include error in broadcast
                system_status = [{"name": "system", "running": False, "error": str(_sys_err)}]
            # Ensure MCP adapter is up (without starting the agent)
            try:
                from app.services.agent_runner import agent_runner
                import asyncio
                await agent_runner.ensure_mcp_adapter_public()  # type: ignore[attr-defined]
            except Exception:
                pass
            # Do NOT start the agent automatically; manual start from UI
            start_ok = True
        except Exception as e:
            start_ok = False
            start_error = str(e)

    # Broadcast project change event
    try:
        payload = {
            "status": "active-changed",
            "previous": prev.model_dump(by_alias=True) if prev else None,
            "current": new_proj.model_dump(by_alias=True) if new_proj else None,
            "runner": {"started": False, "error": None},
            "system": system_status,
        }
        env = Envelope(type=EventType.PROJECT, projectId=project_id, payload=payload)
        await manager.broadcast_project(project_id, env.model_dump_json(by_alias=True))
        # Also notify previous room if different
        if prev and prev.id != project_id:
            await manager.broadcast_project(prev.id, env.model_dump_json(by_alias=True))
    except Exception:
        pass

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": f"Project '{project_id}' is now active",
            "project_id": project_id,
            "runner": {"started": start_ok, "error": start_error}
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
async def delete_project(project_id: str, purge: bool = Query(default=False, description="Also delete the project's folder from disk")) -> JSONResponse:
    """Delete a project from the registry.
    
    By default only removes the project from the database and preserves the filesystem.
    If ``purge=true`` is provided, it will also remove the project's directory from disk.
    
    Args:
        project_id: ID of project to delete
        purge: When true, also delete the project directory from disk
        
    Returns:
        Success confirmation
        
    Raises:
        HTTPException: 404 if project not found
    """
    # If deleting the active project, attempt to stop the agent first
    try:
        active = project_service.get_active_project()
        if active and active.id == project_id:
            try:
                await unified_agent.stop()
            except Exception:
                pass
    except Exception:
        pass

    success = project_service.delete_project(project_id, purge_fs=purge)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found"
        )
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": f"Project '{project_id}' deleted from registry" + (" and filesystem" if purge else ""),
            "project_id": project_id,
            "note": "Filesystem structure preserved" if not purge else "Filesystem removed"
        }
    )
