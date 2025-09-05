"""
Migration script to centralize configuration into config/settings.yaml.

Detects old hardcoded values across the repo, generates a new YAML config,
validates it via ConfigManager, and reports the changes.

Usage: python migrate_config.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import os


RE_WS_URL = re.compile(r"ws://([\w\.-]+):(\d+)(/\S*)?")


def read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def detect_from_adapter(root: Path) -> Dict[str, Any]:
    p = root / "mcp_unity_bridge" / "mcp_adapter.py"
    txt = read_text(p) or ""
    res: Dict[str, Any] = {}
    # MCP URL
    m = RE_WS_URL.search(txt)
    if m:
        res["mcp_host"], res["mcp_port"] = m.group(1), int(m.group(2))
    # Blender URL (search all, take last occurrence which is likely Blender)
    ms = list(RE_WS_URL.finditer(txt))
    if len(ms) >= 2:
        res["blender_host"], res["blender_port"] = ms[-1].group(1), int(ms[-1].group(2))
    return res


def detect_from_server_config(root: Path) -> Dict[str, Any]:
    p = root / "mcp_unity_bridge" / "src" / "mcp_unity_server" / "config.py"
    txt = read_text(p) or ""
    res: Dict[str, Any] = {}
    m_host = re.search(r"\"mcp_host\"\s*:\s*\"([^\"]+)\"", txt)
    m_port = re.search(r"\"mcp_port\"\s*:\s*(\d+)", txt)
    if m_host:
        res["mcp_host"] = m_host.group(1)
    if m_port:
        res["mcp_port"] = int(m_port.group(1))
    return res


def detect_from_ws_blender_test(root: Path) -> Dict[str, Any]:
    p = root / "mcp_unity_bridge" / "ws_blender_test.py"
    txt = read_text(p) or ""
    res: Dict[str, Any] = {}
    m = RE_WS_URL.search(txt)
    if m:
        res["blender_host"], res["blender_port"] = m.group(1), int(m.group(2))
    # Export path
    m_export = re.search(r"EXPORT_PATH\s*=\s*r?\"([^\"]+)\"", txt)
    if m_export:
        res["blender_export_path"] = m_export.group(1)
    return res


def detect_from_integration_test(root: Path) -> Dict[str, Any]:
    p = root / "mcp_unity_bridge" / "integration_test.py"
    txt = read_text(p) or ""
    res: Dict[str, Any] = {}
    m = re.search(r"WEBSOCKET_BASE_URI\s*=\s*\"ws://([\w\.-]+):(\d+)/ws/\"", txt)
    if m:
        res["mcp_host"], res["mcp_port"] = m.group(1), int(m.group(2))
    return res


def build_settings(root: Path, detected: Dict[str, Any]) -> Dict[str, Any]:
    # Defaults
    settings: Dict[str, Any] = {
        "servers": {
            "mcp_bridge": {"host": detected.get("mcp_host", "127.0.0.1"), "port": detected.get("mcp_port", 8001)},
            "unity_editor": {"host": detected.get("unity_host", "127.0.0.1"), "port": detected.get("unity_port", detected.get("mcp_port", 8001))},
            "blender_addon": {"host": detected.get("blender_host", "127.0.0.1"), "port": detected.get("blender_port", 8002)},
        },
        "paths": {
            "unity_project": "unity_project",
            "blender_export": "unity_project/Assets/Generated",
            "templates": "templates",
        },
        "logging": {"level": "INFO", "file": "logs/app.log"},
        "timeouts": {"mcp_bridge": 15, "unity_editor": 15, "blender_addon": 20},
    }

    # If an absolute export path was found, make it relative to repo if possible
    export_abs = detected.get("blender_export_path")
    if export_abs:
        try:
            exp = Path(export_abs)
            rel = exp.relative_to(root)
            settings["paths"]["blender_export"] = str(rel)
        except Exception:
            settings["paths"]["blender_export"] = str(export_abs)

    return settings


def write_yaml(target: Path, data: Dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    # Avoid requiring PyYAML in migration script: write simple YAML manually
    lines = []
    lines.append("servers:")
    for key in ("mcp_bridge", "unity_editor", "blender_addon"):
        srv = data["servers"][key]
        lines.append(f"  {key}:")
        lines.append(f"    host: {srv['host']}")
        lines.append(f"    port: {srv['port']}")
    lines.append("paths:")
    for key in ("unity_project", "blender_export", "templates"):
        lines.append(f"  {key}: {data['paths'][key]}")
    lines.append("logging:")
    lines.append(f"  level: {data['logging']['level']}")
    lines.append(f"  file: {data['logging']['file']}")
    lines.append("timeouts:")
    for key in ("mcp_bridge", "unity_editor", "blender_addon"):
        lines.append(f"  {key}: {data['timeouts'][key]}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_via_config_manager(root: Path, config_file: Path) -> bool:
    sys.path.insert(0, str(root / "mcp_unity_bridge"))
    sys.path.insert(0, str(root / "mcp_unity_bridge" / "src"))
    try:
        from config_manager import ConfigManager  # type: ignore
    except Exception:
        print("[WARN] Could not import ConfigManager for validation. Skipping validation.")
        return False
    # Force specific config file
    os.environ["AGP_CONFIG_FILE"] = str(config_file)
    try:
        cfg = ConfigManager().reload()
        print("[OK] Validated settings via ConfigManager:")
        print(
            json.dumps(
                {
                    "mcp_bridge": f"{cfg.servers.mcp_bridge.host}:{cfg.servers.mcp_bridge.port}",
                    "blender_addon": f"{cfg.servers.blender_addon.host}:{cfg.servers.blender_addon.port}",
                    "unity_project": str(cfg.paths.unity_project),
                },
                indent=2,
            )
        )
        return True
    except Exception as e:
        print(f"[ERROR] Validation failed: {e}")
        return False
    finally:
        for k in ["AGP_CONFIG_FILE"]:
            if k in os.environ:
                del os.environ[k]


def main() -> int:
    root = Path(__file__).resolve().parent
    print(f"[INFO] Repository root: {root}")

    detected: Dict[str, Any] = {}
    for detector in (detect_from_server_config, detect_from_adapter, detect_from_integration_test, detect_from_ws_blender_test):
        try:
            part = detector(root)
            detected.update({k: v for k, v in part.items() if v is not None})
        except Exception as e:
            print(f"[WARN] Detector {detector.__name__} failed: {e}")

    print("[INFO] Detected old config values:")
    print(json.dumps(detected, indent=2))

    settings = build_settings(root, detected)
    target = root / "config" / "settings.yaml"
    write_yaml(target, settings)
    print(f"[INFO] Wrote new settings.yaml -> {target}")

    validate_via_config_manager(root, target)

    print("[DONE] Migration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
