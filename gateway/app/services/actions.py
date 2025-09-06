"""Action Orchestrator: parses, validates and executes agent plans.

Plan format (example):
[
  {"tool": "blender.create_primitive", "args": {"type": "cube", "size": 1.0}},
  {"tool": "blender.export_fbx", "args": {"outfile": "Generated/test_cube.fbx"}},
  {"tool": "unity.instantiate_fbx", "args": {"asset": "Generated/test_cube.fbx"}}
]

This module validates tools against a whitelist and executes them sequentially.
It publishes TIMELINE and UPDATE/SCENE events after each step and persists
timeline entries in SQLite.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable
from uuid import uuid4
from datetime import datetime

from app.config import settings
from app.db import TimelineEventDB, db
from app.models import Envelope, EventType
from app.ws.events import manager


logger = logging.getLogger(__name__)


# Allowed tool identifiers
ALLOWED_TOOLS: set[str] = {
    "blender.create_primitive",
    "blender.export_fbx",
    "unity.instantiate_fbx",
    "project.create_from_template",
    "unity.get_scene_hierarchy",
}


def _sanitize_args(args: dict) -> dict:
    """Basic sanitization for tool arguments.

    - Enforce JSON-serializable primitives
    - Limit string lengths
    - Remove unexpected non-primitive structures
    """
    def sanitize(value: Any, depth: int = 0) -> Any:
        if depth > 5:
            return None
        if isinstance(value, (int, float, bool)):
            return value
        if isinstance(value, str):
            return value[:1024]
        if isinstance(value, list):
            return [sanitize(v, depth + 1) for v in value[:100]]
        if isinstance(value, dict):
            return {str(k)[:64]: sanitize(v, depth + 1) for k, v in list(value.items())[:100]}
        return None

    if not isinstance(args, dict):
        return {}
    return sanitize(args)


class ToolsRegistry:
    """Mapping from tool id to async callable executing it.

    For now these are mocked operations that simulate side effects and
    return a result dict. Integrate with MCP servers in future iterations.
    """

    def __init__(self) -> None:
        self._map: dict[str, Callable[[str, dict], asyncio.Future]] = {
            "blender.create_primitive": self._blender_create_primitive,
            "blender.export_fbx": self._blender_export_fbx,
            "unity.instantiate_fbx": self._unity_instantiate_fbx,
            "project.create_from_template": self._project_create_from_template,
            "unity.get_scene_hierarchy": self._unity_get_scene_hierarchy,
        }

    async def _blender_create_primitive(self, project_id: str, args: dict) -> dict:
        from app.services.mcp_client import mcp_client
        kind = str(args.get("type", "cube"))
        size = float(args.get("size", 1.0))
        return await mcp_client.create_primitive(kind=kind, size=size, project_id=project_id)

    async def _blender_export_fbx(self, project_id: str, args: dict) -> dict:
        from app.services.mcp_client import mcp_client
        from pathlib import Path
        from uuid import uuid4
        outfile = str(args.get("outfile", "unity_project/Assets/Generated/agent_export.fbx"))
        abs_path = Path(outfile)
        if not abs_path.is_absolute():
            abs_path = (Path.cwd() / outfile).resolve()
        pre = {"path": str(abs_path), "existed": abs_path.exists(), "backup_path": None}
        try:
            if abs_path.exists():
                backup_dir = Path("projects") / project_id / "context" / "backups"
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_path = backup_dir / f"{uuid4().hex}_{abs_path.name}"
                shutil.copy2(abs_path, backup_path)
                pre["backup_path"] = str(backup_path.resolve())
        except Exception:
            # If backup fails, we still proceed; revert may be 'cannot'
            pass
        res = await mcp_client.export_fbx(outfile=outfile, project_id=project_id)
        return {
            **res,
            "exported": outfile,
            "compensate": {
                "type": "file",
                "op": "export",
                "path": str(abs_path),
                "existed": pre.get("existed", False),
                "backup_path": pre.get("backup_path"),
            },
        }

    async def _unity_instantiate_fbx(self, project_id: str, args: dict) -> dict:
        from app.services.mcp_client import mcp_client
        asset = str(args.get("asset", "Assets/Generated/agent_export.fbx"))
        return await mcp_client.instantiate_prefab(asset_path=asset, project_id=project_id)

    async def _project_create_from_template(self, project_id: str, args: dict) -> dict:
        # Create a new project using name/templateId; returns created project id
        from app.models.core import CreateProject
        from app.services.projects import project_service
        name = str(args.get("name", "Untitled"))
        # For now templateId is not used to change behavior; reserved for future
        _ = args.get("templateId")
        proj = project_service.create_project(CreateProject(name=name))
        return {"projectId": proj.id, "name": proj.name}

    async def _unity_get_scene_hierarchy(self, project_id: str, args: dict) -> dict:
        from app.services.mcp_client import mcp_client
        return await mcp_client.get_scene_hierarchy(project_id)

    async def execute(self, tool: str, project_id: str, args: dict) -> dict:
        handler = self._map.get(tool)
        if not handler:
            raise ValueError(f"Unsupported tool: {tool}")
        return await handler(project_id, args)


tools_registry = ToolsRegistry()


class ActionOrchestrator:
    async def run_plan(self, project_id: str, plan: List[Dict[str, Any]], correlation_id: Optional[str] = None) -> dict:
        """Validate and execute plan sequentially, persisting timeline and broadcasting events.

        Aborts on first error; returns summary with per-step statuses.
        """
        if not isinstance(plan, list):
            raise ValueError("Plan must be a list of steps")

        summary: list[dict] = []

        for idx, step in enumerate(plan):
            tool = (step or {}).get("tool")
            args = (step or {}).get("args", {})

            if tool not in ALLOWED_TOOLS:
                err = f"Tool not allowed: {tool}"
                await self._broadcast_error(project_id, err, correlation_id)
                summary.append({"index": idx, "tool": tool, "status": "error", "error": err})
                break

            san_args = _sanitize_args(args)
            # Persist start event
            started = datetime.utcnow()
            ev = db.add_timeline_event(
                TimelineEventDB(
                    project_id=project_id,
                    step_index=idx,
                    tool=tool,
                    args_json=json.dumps(san_args, ensure_ascii=False),
                    status="running",
                    result_json=None,
                    correlation_id=correlation_id,
                    started_at=started,
                )
            )
            # Broadcast tool invocation and timeline running
            await self._broadcast_tool(project_id, idx, tool, san_args, correlation_id)
            await self._broadcast_timeline(project_id, idx, tool, "running", None, correlation_id)

            try:
                timeout = float(settings.timeouts.get("blender_addon", 20)) if tool.startswith("blender") else float(settings.timeouts.get("unity_editor", 15))
                result = await asyncio.wait_for(tools_registry.execute(tool, project_id, san_args), timeout=timeout)
                # Update DB
                ev.status = "success"
                ev.result_json = json.dumps(result, ensure_ascii=False)
                ev.finished_at = datetime.utcnow()
                db.add_timeline_event(ev)  # simple upsert by re-add in this minimal layer

                await self._broadcast_timeline(project_id, idx, tool, "success", result, correlation_id)
                # Secondary updates (scene/update)
                await self._broadcast_update(project_id, tool, result, correlation_id)
                summary.append({"index": idx, "tool": tool, "status": "success", "result": result})
            except asyncio.TimeoutError:
                err = f"Step {idx} timed out"
                await self._finalize_error(ev, project_id, idx, tool, err, correlation_id)
                summary.append({"index": idx, "tool": tool, "status": "error", "error": err})
                break
            except Exception as e:
                err = str(e)
                await self._finalize_error(ev, project_id, idx, tool, err, correlation_id)
                summary.append({"index": idx, "tool": tool, "status": "error", "error": err})
                break

        return {"steps": summary}

    async def _finalize_error(self, ev: TimelineEventDB, project_id: str, idx: int, tool: str, error: str, correlation_id: Optional[str]) -> None:
        try:
            ev.status = "error"
            ev.result_json = json.dumps({"error": error}, ensure_ascii=False)
            ev.finished_at = datetime.utcnow()
            db.add_timeline_event(ev)
        except Exception as e:
            logger.error("Failed updating timeline on error: %s", e)
        await self._broadcast_timeline(project_id, idx, tool, "error", {"error": error}, correlation_id)
        await self._broadcast_error(project_id, error, correlation_id)

    async def _broadcast_timeline(self, project_id: str, index: int, tool: str, status: str, result: Optional[dict], correlation_id: Optional[str]) -> None:
        payload = {
            "index": index,
            "tool": tool,
            "status": status,
            "result": result,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "correlationId": correlation_id,
        }
        env = Envelope(type=EventType.TIMELINE, projectId=project_id, payload=payload, correlationId=correlation_id)
        await manager.broadcast_project(project_id, json.dumps(env.model_dump(by_alias=True, mode="json")))

    async def _broadcast_tool(self, project_id: str, index: int, tool: str, args: dict, correlation_id: Optional[str]) -> None:
        payload = {
            "index": index,
            "tool": tool,
            "args": args,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "correlationId": correlation_id,
        }
        env = Envelope(type=EventType.ACTION, projectId=project_id, payload=payload, correlationId=correlation_id)
        await manager.broadcast_project(project_id, json.dumps(env.model_dump(by_alias=True, mode="json")))

    async def _broadcast_update(self, project_id: str, tool: str, result: dict, correlation_id: Optional[str]) -> None:
        payload = {
            "tool": tool,
            "data": result,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "correlationId": correlation_id,
        }
        env = Envelope(type=EventType.UPDATE, projectId=project_id, payload=payload, correlationId=correlation_id)
        await manager.broadcast_project(project_id, json.dumps(env.model_dump(by_alias=True, mode="json")))

    async def _broadcast_error(self, project_id: str, message: str, correlation_id: Optional[str]) -> None:
        payload = {"error": message, "timestamp": datetime.utcnow().isoformat() + "Z", "correlationId": correlation_id}
        env = Envelope(type=EventType.ERROR, projectId=project_id, payload=payload, correlationId=correlation_id)
        await manager.broadcast_project(project_id, json.dumps(env.model_dump(by_alias=True, mode="json")))


# Singleton instance
action_orchestrator = ActionOrchestrator()
