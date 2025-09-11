"""Configuration service for centralized settings with validation and masking.

Stores data under config/settings.yaml -> gateway.config
Keeps compatibility with existing sections (servers/paths/timeouts/gateway.processes).
"""

from __future__ import annotations

import os
import re
import socket
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml


CONFIG_PATH = Path("config/settings.yaml")


def _load_full_yaml() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _save_full_yaml_atomic(data: Dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Backup
    if CONFIG_PATH.exists():
        backup = CONFIG_PATH.with_suffix(CONFIG_PATH.suffix + ".bak")
        try:
            CONFIG_PATH.replace(backup)
        except Exception:
            pass
        # If backup moved, write fresh file; else continue to atomic write as well
    tmp = CONFIG_PATH.with_suffix(CONFIG_PATH.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    tmp.replace(CONFIG_PATH)


def _mask_key(v: str | None) -> str | None:
    if not v:
        return v
    s = str(v)
    if len(s) <= 4:
        return "****"
    return "****" + s[-4:]


def _is_masked(v: Any) -> bool:
    return isinstance(v, str) and re.match(r"^\*{3,}.*$", v or "") is not None


def _default_config() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "executables": {
            "unityExecutablePath": "",
            "blenderExecutablePath": "",
            "unityProjectRoot": "projects",
        },
        "bridges": {
            "unityBridgePort": 8001,
            "blenderBridgePort": 8002,
        },
        "providers": {
            "geminiCli": {"command": "gemini"}
        },
        "integrations": {
            "gemini": {"apiKey": "", "defaultModel": ""},
            "openai": {"apiKey": "", "defaultModel": ""},
            "anthropic": {"apiKey": "", "defaultModel": ""},
        },
        "projects": {"root": "projects"},
        "dependencies": {
            "requirementFiles": [
                "mcp_unity_bridge/requirements.txt",
                "gateway/pyproject.toml"
            ],
            "extraAllowed": [
                "openai",
                "anthropic",
                "google-generativeai",
                "typer",
                "mcp",
                "mcp[cli]"
            ],
            "venvRoots": [
                "projects/*/.venv",
                "venvs/*"
            ],
            "venvDefault": "venvs/agp",
            "minimalPackages": ["fastapi", "uvicorn", "websockets"]
        },
        "agents": {
            "default": "gemini"
        }
    }


def _merge_compatibility(base: Dict[str, Any], full_yaml: Dict[str, Any]) -> Dict[str, Any]:
    gateway = full_yaml.get("gateway", {}) if isinstance(full_yaml, dict) else {}
    processes = gateway.get("processes", {}) if isinstance(gateway, dict) else {}
    paths = full_yaml.get("paths", {}) if isinstance(full_yaml, dict) else {}
    servers = full_yaml.get("servers", {}) if isinstance(full_yaml, dict) else {}

    # Executables
    unity_exe = processes.get("unity", {}).get("exe")
    blender_exe = processes.get("blender", {}).get("exe")
    if unity_exe:
        base["executables"]["unityExecutablePath"] = unity_exe
    if blender_exe:
        base["executables"]["blenderExecutablePath"] = blender_exe
    # Project root
    unity_project = paths.get("unity_project")
    if unity_project:
        base["executables"]["unityProjectRoot"] = unity_project
        base["projects"]["root"] = unity_project

    # Ports
    ub_port = processes.get("unity_bridge", {}).get("port") or servers.get("mcp_bridge", {}).get("port")
    bb_port = processes.get("blender_bridge", {}).get("port") or servers.get("blender_addon", {}).get("port")
    if ub_port:
        base["bridges"]["unityBridgePort"] = int(ub_port)
    if bb_port:
        base["bridges"]["blenderBridgePort"] = int(bb_port)

    return base


def get_all(mask_secrets: bool = True) -> Dict[str, Any]:
    full = _load_full_yaml()
    gw = full.get("gateway", {}) if isinstance(full, dict) else {}
    cfg = gw.get("config", {}) if isinstance(gw, dict) else {}
    # Start with defaults
    merged = _default_config()
    # Overlay stored config
    if isinstance(cfg, dict):
        for k, v in cfg.items():
            if isinstance(v, dict) and k in merged:
                merged[k].update(v)
            else:
                merged[k] = v
    # Fill from compatibility sources
    merged = _merge_compatibility(merged, full)

    if mask_secrets:
        for prov in ("gemini", "openai", "anthropic"):
            key = merged["integrations"].get(prov, {}).get("apiKey")
            merged["integrations"][prov]["apiKey"] = _mask_key(key)

    return merged


def _validate_paths(cfg: Dict[str, Any]) -> Dict[str, str]:
    errors: Dict[str, str] = {}
    unity = cfg.get("executables", {}).get("unityExecutablePath")
    blender = cfg.get("executables", {}).get("blenderExecutablePath")
    if unity and not Path(unity).exists():
        errors["executables.unityExecutablePath"] = f"Unity executable not found: {unity}"
    if blender and not Path(blender).exists():
        errors["executables.blenderExecutablePath"] = f"Blender executable not found: {blender}"
    proj_root = cfg.get("projects", {}).get("root") or cfg.get("executables", {}).get("unityProjectRoot")
    if proj_root:
        p = Path(proj_root)
        try:
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)
        except Exception:
            errors["projects.root"] = f"Cannot access or create project root: {proj_root}"
    # Providers (geminiCli): if command looks like a path, check exists
    cmd = (cfg.get("providers", {}) or {}).get("geminiCli", {}).get("command")
    if isinstance(cmd, str) and ("/" in cmd or "\\" in cmd):
        if not Path(cmd).exists():
            errors["providers.geminiCli.command"] = f"Gemini CLI command not found: {cmd}"
    return errors


def _port_free(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, int(port)))
        return True
    except Exception:
        return False


def _validate_ports(cfg: Dict[str, Any]) -> Dict[str, str]:
    errors: Dict[str, str] = {}
    try:
        ub = int(cfg.get("bridges", {}).get("unityBridgePort"))
        if ub <= 0 or ub > 65535:
            errors["bridges.unityBridgePort"] = "Invalid port"
        elif not _port_free(ub):
            errors["bridges.unityBridgePort"] = "Port is not available"
    except Exception:
        errors["bridges.unityBridgePort"] = "Must be a number"
    try:
        bb = int(cfg.get("bridges", {}).get("blenderBridgePort"))
        if bb <= 0 or bb > 65535:
            errors["bridges.blenderBridgePort"] = "Invalid port"
        elif not _port_free(bb):
            errors["bridges.blenderBridgePort"] = "Port is not available"
    except Exception:
        errors["bridges.blenderBridgePort"] = "Must be a number"
    return errors


def _validate_keys(cfg: Dict[str, Any]) -> Dict[str, str]:
    errors: Dict[str, str] = {}
    integrations = cfg.get("integrations", {})
    # Very light validation: non-empty strings when provided
    for prov in ("gemini", "openai", "anthropic"):
        val = integrations.get(prov, {}).get("apiKey")
        if val and _is_masked(val):
            continue  # unchanged
        if val is not None and not isinstance(val, str):
            errors[f"integrations.{prov}.apiKey"] = "Must be a string"
        # Optional provider-specific hints
        if prov == "openai" and val and isinstance(val, str) and not val.startswith("sk-"):
            errors[f"integrations.{prov}.apiKey"] = "Expected key starting with 'sk-'"
    return errors


def validate(cfg: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
    errors: Dict[str, str] = {}
    errors.update(_validate_paths(cfg))
    errors.update(_validate_ports(cfg))
    errors.update(_validate_keys(cfg))
    return (len(errors) == 0), errors


def update(partial: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and persist partial config into settings.yaml under gateway.config.

    Returns masked config.
    """
    full = _load_full_yaml()
    gw = full.setdefault("gateway", {})
    cfg = gw.get("config")
    if not isinstance(cfg, dict):
        cfg = _default_config()
        gw["config"] = cfg

    # Deep merge partial with masking rules (masked keys mean 'leave as-is')
    def deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                deep_merge(dst[k], v)
            else:
                # Ignore masked api keys to keep existing value
                if k == "apiKey" and _is_masked(v):
                    continue
                dst[k] = v

    deep_merge(cfg, partial or {})
    # Validate before saving
    ok, errors = validate(cfg)
    if not ok:
        raise ValueError(yaml.safe_dump(errors, sort_keys=True))

    # Propagate to compatibility sections to keep existing services in sync
    processes = gw.setdefault("processes", {})
    unity = processes.setdefault("unity", {})
    blender = processes.setdefault("blender", {})
    unity_bridge = processes.setdefault("unity_bridge", {})
    blender_bridge = processes.setdefault("blender_bridge", {})
    # Executables
    exe_u = cfg.get("executables", {}).get("unityExecutablePath")
    if exe_u:
        unity["exe"] = exe_u
    exe_b = cfg.get("executables", {}).get("blenderExecutablePath")
    if exe_b:
        blender["exe"] = exe_b
    # Project root
    proj_root = (cfg.get("projects", {}) or {}).get("root") or (cfg.get("executables", {}) or {}).get("unityProjectRoot")
    if proj_root:
        full.setdefault("paths", {})["unity_project"] = proj_root
        # If blender export path is relative to unity project, keep as-is
    # Ports
    ub_port = cfg.get("bridges", {}).get("unityBridgePort")
    if ub_port:
        unity_bridge["port"] = int(ub_port)
    bb_port = cfg.get("bridges", {}).get("blenderBridgePort")
    if bb_port:
        blender_bridge["port"] = int(bb_port)

    # Persist and return masked
    _save_full_yaml_atomic(full)
    return get_all(mask_secrets=True)
