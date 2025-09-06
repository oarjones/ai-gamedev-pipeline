"""MCPClient: thin wrapper around the MCP adapter functions (same venv).

Provides high-level helpers used by the gateway without duplicating logic.
Endpoints/credentials are read from the shared config via the adapter's
ConfigManager, and may be overridden per-project via .agp/project.json
(agent.env.*). Includes retry/backoff (circuit breaker) and run_tool().
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Callable, Awaitable
import time


logger = logging.getLogger(__name__)


def _ensure_config_env() -> None:
    """Ensure the MCP adapter resolves the same config file as the gateway.

    If AGP_CONFIG_FILE is unset, point it to repo-root/config/settings.yaml.
    The adapter's ConfigManager defaults to that path but we set explicitly
    to avoid surprises in alternative run contexts.
    """
    if not os.getenv("AGP_CONFIG_FILE"):
        # Repo root = two levels up from this file: gateway/app/services -> repo
        repo_root = Path(__file__).resolve().parents[3]
        cfg_path = repo_root / "config" / "settings.yaml"
        os.environ["AGP_CONFIG_FILE"] = str(cfg_path)


async def _retry(fn: Callable[[], Awaitable[Any]], attempts: int = 2, delay: float = 0.2) -> Any:
    last_exc: Optional[Exception] = None
    for i in range(attempts):
        try:
            return await fn()
        except Exception as e:  # pragma: no cover - transient
            last_exc = e
            logger.warning("MCP call failed (try %s/%s): %s", i + 1, attempts, e)
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


def _parse_json(s: str) -> Dict[str, Any]:
    try:
        return json.loads(s)
    except Exception as e:
        return {"status": "error", "error": f"invalid JSON from adapter: {e}", "raw": s}


class MCPClient:
    """Wrapper to call MCP adapter functions with minimal ceremony."""

    def __init__(self) -> None:
        _ensure_config_env()
        # Import lazily after env var is set to ensure URLs are resolved once
        from mcp_unity_bridge import mcp_adapter as _adapter  # type: ignore

        self._adapter = _adapter
        self._breaker: Dict[str, Dict[str, float]] = {
            # key -> {"failures": int, "open_until": epoch}
        }

    # ------------------------ Circuit breaker ------------------------
    def _cb_check(self, key: str) -> None:
        st = self._breaker.get(key)
        if not st:
            return
        if st.get("open_until", 0) > time.time():
            raise RuntimeError(f"Circuit open for {key}")

    def _cb_record(self, key: str, ok: bool) -> None:
        st = self._breaker.setdefault(key, {"failures": 0, "open_until": 0.0})
        if ok:
            st["failures"] = 0
            st["open_until"] = 0.0
        else:
            st["failures"] = int(st.get("failures", 0)) + 1
            backoff = min(60.0, 0.5 * (2 ** (st["failures"] - 1)))
            st["open_until"] = time.time() + backoff

    # -------------------------- Env per project --------------------------
    def _apply_project_env(self, project_id: Optional[str]) -> Dict[str, str]:
        env: Dict[str, str] = {}
        if not project_id:
            return env
        pj = Path("projects") / project_id / ".agp" / "project.json"
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
            agent_env = (data.get("agent", {}) or {}).get("env", {})  # type: ignore
            if isinstance(agent_env, dict):
                for k, v in agent_env.items():
                    env[str(k)] = str(v)
        except Exception:
            pass
        # Apply into process env for adapter to pick up
        for k, v in env.items():
            os.environ[str(k)] = str(v)
        return env

    # ------------------------- Unity helpers -------------------------

    async def get_scene_hierarchy(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        key = "unity"
        self._cb_check(key)
        self._apply_project_env(project_id)
        async def call():
            s = await self._adapter.unity_get_scene_hierarchy()
            return _parse_json(s)
        try:
            res = await _retry(call)
            self._cb_record(key, ok=True)
            return res
        except Exception as e:
            self._cb_record(key, ok=False)
            raise e

    async def capture_screenshot(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        key = "unity"
        self._cb_check(key)
        self._apply_project_env(project_id)
        async def call():
            s = await self._adapter.unity_capture_screenshot()
            return _parse_json(s)
        try:
            res = await _retry(call)
            self._cb_record(key, ok=True)
            return res
        except Exception as e:
            self._cb_record(key, ok=False)
            raise e

    async def instantiate_prefab(self, asset_path: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        # Use dynamic code path until a dedicated adapter tool exists
        code = f"""
        using UnityEditor;
        using UnityEngine;
        var go = AssetDatabase.LoadAssetAtPath<GameObject>(@"{asset_path}");
        if (go == null) {{
            throw new System.Exception("Prefab/FBX not found: {asset_path}");
        }}
        var instance = PrefabUtility.InstantiatePrefab(go) as GameObject;
        if (instance == null) {{
            throw new System.Exception("Failed to instantiate prefab: {asset_path}");
        }}
        instance.transform.position = Vector3.zero;
        """

        key = "unity"
        self._cb_check(key)
        self._apply_project_env(project_id)
        async def call():
            s = await self._adapter.unity_command(code)
            return _parse_json(s)
        try:
            res = await _retry(call)
            self._cb_record(key, ok=True)
            return res
        except Exception as e:
            self._cb_record(key, ok=False)
            raise e

    # ------------------------ Blender helpers ------------------------

    async def export_fbx(self, outfile: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Call Blender add-on command to export FBX to given path."""
        payload = {"path": outfile}

        key = "blender"
        self._cb_check(key)
        self._apply_project_env(project_id)
        async def call():
            s = await self._adapter.blender_call("export_fbx", payload)
            return _parse_json(s)
        try:
            res = await _retry(call)
            self._cb_record(key, ok=True)
            return res
        except Exception as e:
            self._cb_record(key, ok=False)
            raise e

    async def create_primitive(self, kind: str = "cube", size: float = 1.0, name: Optional[str] = None, project_id: Optional[str] = None) -> Dict[str, Any]:
        payload = {"kind": kind, "params": {"size": size}}
        if name:
            payload["name"] = name

        key = "blender"
        self._cb_check(key)
        self._apply_project_env(project_id)
        async def call():
            s = await self._adapter.blender_modeling_create_primitive(**payload)
            return _parse_json(s)
        try:
            res = await _retry(call)
            self._cb_record(key, ok=True)
            return res
        except Exception as e:
            self._cb_record(key, ok=False)
            raise e

    # ------------------------ run_tool generic ------------------------
    async def run_tool(self, project_id: str, name: str, args: Dict[str, Any] | None = None, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        args = args or {}
        try:
            if name == "unity.get_scene_hierarchy":
                return await self.get_scene_hierarchy(project_id)
            if name == "blender.export_fbx":
                return await self.export_fbx(str(args.get("outfile", "unity_project/Assets/Generated/agent_export.fbx")), project_id)
            if name == "blender.create_primitive":
                return await self.create_primitive(str(args.get("type", "cube")), float(args.get("size", 1.0)), None, project_id)
            if name == "unity.instantiate_fbx":
                return await self.instantiate_prefab(str(args.get("asset", "Assets/Generated/agent_export.fbx")), project_id)

            # Fallback: try blender_call with full name if it looks like a Blender command
            if name.startswith("blender."):
                key = "blender"
                self._cb_check(key)
                self._apply_project_env(project_id)
                async def call():
                    s = await self._adapter.blender_call(name.split("blender.",1)[1], args)
                    return _parse_json(s)
                try:
                    res = await _retry(call)
                    self._cb_record(key, ok=True)
                    return res
                except Exception as e:
                    self._cb_record(key, ok=False)
                    raise e
        except Exception as e:
            # Emit log event on errors
            try:
                from app.ws.events import manager
                from app.models import Envelope, EventType
                payload = {"level": "error", "message": f"run_tool failed: {name}: {e}"}
                env = Envelope(type=EventType.LOG, projectId=project_id, payload=payload, correlationId=correlation_id)
                await manager.broadcast_project(project_id, env.model_dump_json(by_alias=True))
            except Exception:
                pass
            raise



# Singleton instance
mcp_client = MCPClient()
