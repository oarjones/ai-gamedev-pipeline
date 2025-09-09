from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_log_dir() -> Path:
    p = repo_root() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def log_file_path() -> Path:
    # Integrate with global settings if available
    try:
        from config_manager import ConfigManager  # type: ignore
        cfg = ConfigManager().get()
        return Path(cfg.logging.file)
    except Exception:
        pass
    env = os.getenv("LOG_FILE")
    return Path(env) if env else (default_log_dir() / "app.log")


def log_level() -> str:
    try:
        from config_manager import ConfigManager  # type: ignore
        return ConfigManager().get().logging.level
    except Exception:
        pass
    return os.getenv("LOG_LEVEL", "INFO")


def aggregator_host_port() -> Tuple[str, int]:
    host = os.getenv("LOG_AGGR_HOST", "127.0.0.1")
    port = int(os.getenv("LOG_AGGR_PORT", "8765"))
    return host, port


def aggregator_ws_url() -> str:
    h, p = aggregator_host_port()
    return f"ws://{h}:{p}/ws/logs"


def database_path() -> Path:
    return repo_root() / "logs" / "logs.sqlite3"

