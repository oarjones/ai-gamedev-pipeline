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


# Buscar el archivo relativo al archivo Python actual, no al CWD
# Este archivo está en gateway/app/services/config_service.py
# El settings.yaml está en la raíz del proyecto: config/settings.yaml
current_file = Path(__file__).resolve()  # gateway/app/services/config_service.py
project_root = current_file.parent.parent.parent.parent  # Subir 4 niveles: services -> app -> gateway -> raíz
CONFIG_PATH = project_root / "config" / "settings.yaml"

# También permitir configuración local en gateway/config
LOCAL_CONFIG_PATH = current_file.parent.parent.parent / "config" / "settings.yaml"


def _get_config_path() -> Path:
    """Obtener la ruta del archivo de configuración."""
    if CONFIG_PATH.exists():
        return CONFIG_PATH
    elif LOCAL_CONFIG_PATH.exists():
        return LOCAL_CONFIG_PATH
    else:
        # Si ninguno existe, usar la raíz del proyecto por defecto
        return CONFIG_PATH


def _load_full_yaml() -> Dict[str, Any]:
    config_path = _get_config_path()
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _save_full_yaml_atomic(data: Dict[str, Any]) -> None:
    config_path = _get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    # Backup
    if config_path.exists():
        backup = config_path.with_suffix(config_path.suffix + ".bak")
        try:
            config_path.replace(backup)
        except Exception:
            pass
        # If backup moved, write fresh file; else continue to atomic write as well
    tmp = config_path.with_suffix(config_path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    tmp.replace(config_path)


def _mask_key(v: str | None) -> str | None:
    if not v:
        return v
    s = str(v)
    if len(s) <= 4:
        return "****"
    return "****" + s[-4:]


def _is_masked(v: Any) -> bool:
    return isinstance(v, str) and re.match(r"^\*{3,}.*", v) is not None


def _default_config() -> Dict[str, Any]:
    """Default configuration structure compatible with frontend expectations."""
    full_yaml = _load_full_yaml()
    base = {
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
        "integrations": {
            "gemini": {"apiKey": None, "defaultModel": ""},
            "openai": {"apiKey": None, "defaultModel": "gpt-4o"},
            "anthropic": {"apiKey": None, "defaultModel": "claude-3-sonnet-20240229"},
        },
        "projects": {
            "root": "projects",
        },
        "providers": {
            "geminiCli": {
                "command": "gemini",
            },
        },
    }
    # Fill from existing if available for compatibility
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
    # Mask api keys if requested
    if mask_secrets:
        integrations = merged.get("integrations", {})
        for prov in ("gemini", "openai", "anthropic"):
            if prov in integrations and "apiKey" in integrations[prov]:
                integrations[prov]["apiKey"] = _mask_key(integrations[prov]["apiKey"])
    return merged


def _validate_paths(cfg: Dict[str, Any]) -> Dict[str, str]:
    errors: Dict[str, str] = {}
    # Unity executable
    unity_exe = cfg.get("executables", {}).get("unityExecutablePath")
    if unity_exe and not Path(unity_exe).exists():
        errors["executables.unityExecutablePath"] = "File not found"
    # Blender executable (optional)
    blender_exe = cfg.get("executables", {}).get("blenderExecutablePath")
    if blender_exe and not Path(blender_exe).exists():
        errors["executables.blenderExecutablePath"] = "File not found"
    # Unity project root (can be created later)
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