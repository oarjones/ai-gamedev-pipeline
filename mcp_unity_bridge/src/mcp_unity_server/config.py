from typing import Dict, Any

ConfigManager = None  # type: ignore
try:
    from config_manager import ConfigManager  # type: ignore
except Exception:
    try:
        from src.config_manager import ConfigManager  # type: ignore
    except Exception:
        ConfigManager = None  # type: ignore


def get_settings() -> Dict[str, Any]:
    """Return server runtime settings derived from centralized config.

    Returns:
        Dict[str, Any]: Contains at least mcp_host and mcp_port.
    """

    if ConfigManager is not None:
        cfg = ConfigManager().get()
        return {
            "mcp_port": cfg.servers.mcp_bridge.port,
            "mcp_host": cfg.servers.mcp_bridge.host,
            # keep legacy field for potential external use
            "unity_editor_url": f"http://{cfg.servers.unity_editor.host}:{cfg.servers.unity_editor.port}",
        }
    # Fallback defaults if ConfigManager import fails
    return {
        "mcp_port": 8001,
        "mcp_host": "127.0.0.1",
        "unity_editor_url": "http://127.0.0.1:8002",
    }
