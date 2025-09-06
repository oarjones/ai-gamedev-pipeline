"""MCPClient: thin wrapper around the MCP adapter functions (same venv).

Provides high-level helpers used by the gateway without duplicating logic.
Endpoints/credentials are read from the shared config via the adapter's
ConfigManager. Implements simple retry/backoff and normalized error shapes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Callable, Awaitable


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

    # ------------------------- Unity helpers -------------------------

    async def get_scene_hierarchy(self) -> Dict[str, Any]:
        async def call():
            s = await self._adapter.unity_get_scene_hierarchy()
            return _parse_json(s)

        return await _retry(call)

    async def capture_screenshot(self) -> Dict[str, Any]:
        async def call():
            s = await self._adapter.unity_capture_screenshot()
            return _parse_json(s)

        return await _retry(call)

    async def instantiate_prefab(self, asset_path: str) -> Dict[str, Any]:
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

        async def call():
            s = await self._adapter.unity_command(code)
            return _parse_json(s)

        return await _retry(call)

    # ------------------------ Blender helpers ------------------------

    async def export_fbx(self, outfile: str) -> Dict[str, Any]:
        """Call Blender add-on command to export FBX to given path."""
        payload = {"path": outfile}

        async def call():
            s = await self._adapter.blender_call("export_fbx", payload)
            return _parse_json(s)

        return await _retry(call)

    async def create_primitive(self, kind: str = "cube", size: float = 1.0, name: Optional[str] = None) -> Dict[str, Any]:
        payload = {"kind": kind, "params": {"size": size}}
        if name:
            payload["name"] = name

        async def call():
            s = await self._adapter.blender_modeling_create_primitive(**payload)
            return _parse_json(s)

        return await _retry(call)


# Singleton instance
mcp_client = MCPClient()

