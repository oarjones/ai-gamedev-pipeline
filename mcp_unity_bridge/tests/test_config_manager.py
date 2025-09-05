import os
from pathlib import Path
import importlib
import types

import pytest


def _import_manager():
    # Ensure import from src path
    root = Path(__file__).resolve().parents[2]
    src = root / "mcp_unity_bridge" / "src"
    if str(src) not in os.sys.path:
        os.sys.path.insert(0, str(src))
    return importlib.import_module("config_manager")


def test_defaults_when_missing_file(monkeypatch, tmp_path: Path):
    cm = _import_manager()
    # Point to a non-existent config file
    monkeypatch.setenv("AGP_CONFIG_FILE", str(tmp_path / "missing.yaml"))
    mgr = cm.ConfigManager()
    cfg = mgr.reload()
    assert cfg.servers.mcp_bridge.port == 8001
    assert cfg.servers.blender_addon.port == 8002
    assert cfg.paths.unity_project.exists() is False or cfg.paths.unity_project.name == "unity_project"


def test_env_overrides(monkeypatch):
    cm = _import_manager()
    monkeypatch.setenv("MCP_PORT", "9001")
    monkeypatch.setenv("BLENDER_PORT", "9002")
    mgr = cm.ConfigManager()
    cfg = mgr.reload()
    assert cfg.servers.mcp_bridge.port == 9001
    assert cfg.servers.blender_addon.port == 9002


def test_reload_applies_changes(monkeypatch):
    cm = _import_manager()
    mgr = cm.ConfigManager()
    cfg1 = mgr.reload()
    p1 = cfg1.servers.mcp_bridge.port
    monkeypatch.setenv("MCP_PORT", str(9101 if p1 != 9101 else 9102))
    cfg2 = mgr.reload()
    assert cfg2.servers.mcp_bridge.port != p1


def test_corrupt_yaml_graceful(monkeypatch, tmp_path: Path):
    cm = _import_manager()
    bad = tmp_path / "bad.yaml"
    bad.write_text("servers: [this is not valid]", encoding="utf-8")
    monkeypatch.setenv("AGP_CONFIG_FILE", str(bad))
    mgr = cm.ConfigManager()
    cfg = mgr.reload()
    # Defaults applied
    assert cfg.servers.mcp_bridge.port == 8001

