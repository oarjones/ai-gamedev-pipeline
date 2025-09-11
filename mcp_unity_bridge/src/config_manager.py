"""
ConfigManager: Centralized settings loader for AI GameDev Pipeline.

Implements a Singleton that loads and validates configuration from YAML using
Pydantic, supports environment variable overrides, caches results with a TTL,
and provides hot-reload via reload().

Google-style docstrings and type hints are used throughout.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - handled gracefully
    yaml = None  # type: ignore

from pydantic import BaseModel, Field, ValidationError


# ---------------------------------------------------------------------------
# Pydantic models for schema validation
# ---------------------------------------------------------------------------


class ServerConfig(BaseModel):
    """Server host/port configuration.

    Attributes:
        host: Hostname or IP.
        port: TCP port.
    """

    host: str
    port: int


class Servers(BaseModel):
    """All server endpoints for the system."""

    mcp_bridge: ServerConfig
    unity_editor: ServerConfig
    blender_addon: ServerConfig


class PathsConfig(BaseModel):
    """Filesystem paths, relative to repository root unless absolute."""

    unity_project: Path
    blender_export: Path
    templates: Path


class LoggingConfig(BaseModel):
    """Logging configuration for the app."""

    level: str = Field(pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    file: Path


class TimeoutsConfig(BaseModel):
    """Timeouts (in seconds) per service."""

    mcp_bridge: int
    unity_editor: int
    blender_addon: int


class Settings(BaseModel):
    """Top-level configuration structure."""

    servers: Servers
    paths: PathsConfig
    logging: LoggingConfig
    timeouts: TimeoutsConfig


# ---------------------------------------------------------------------------
# Defaults and helpers
# ---------------------------------------------------------------------------


def _default_settings(repo_root: Path) -> Settings:
    """Build default settings.

    Args:
        repo_root: Repository root used to resolve relative paths.

    Returns:
        Settings: Default configuration object.
    """

    return Settings(
        servers=Servers(
            mcp_bridge=ServerConfig(host="127.0.0.1", port=8001),
            unity_editor=ServerConfig(host="127.0.0.1", port=8001),
            blender_addon=ServerConfig(host="127.0.0.1", port=8002),
        ),
        paths=PathsConfig(
            unity_project=repo_root / "unity_project",
            blender_export=repo_root / "unity_project" / "Assets" / "Generated",
            templates=repo_root / "templates",
        ),
        logging=LoggingConfig(level="INFO", file=repo_root / "logs" / "app.log"),
        timeouts=TimeoutsConfig(mcp_bridge=15, unity_editor=15, blender_addon=20),
    )


def _resolve_relative(base: Path, p: Path) -> Path:
    """Resolve path relative to base if not absolute.

    Args:
        base: Base directory for relative resolution.
        p: Input path that can be relative or absolute.

    Returns:
        Path: Absolute path.
    """

    return p if p.is_absolute() else (base / p).resolve()


# ---------------------------------------------------------------------------
# ConfigManager (Singleton with TTL cache and hot reload)
# ---------------------------------------------------------------------------


class ConfigManager:
    """Singleton manager for application configuration.

    Responsibilities:
    - Locate and load YAML configuration (config/settings.yaml),
    - Validate structure via Pydantic models,
    - Apply environment variable overrides,
    - Cache config with TTL to avoid frequent disk IO,
    - Support hot reload via reload().

    Environment overrides supported (strings/ints):
    - AGP_CONFIG_FILE: explicit path to YAML file.
    - MCP_HOST, MCP_PORT, UNITY_HOST, UNITY_PORT, BLENDER_HOST, BLENDER_PORT
    - MCP_TIMEOUT, UNITY_TIMEOUT, BLENDER_TIMEOUT
    - UNITY_PROJECT_DIR, BLENDER_EXPORT_DIR, TEMPLATES_DIR
    - LOG_LEVEL, LOG_FILE
    """

    _instance: Optional["ConfigManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ConfigManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        self._logger = logging.getLogger("config_manager")
        if not self._logger.handlers:
            # Keep logging simple; rely on app to configure handlers.
            handler = logging.StreamHandler()
            self._logger.addHandler(handler)
        self._logger.setLevel(logging.INFO)

        # Determine repo root (two levels up from this file: src -> mcp_unity_bridge -> repo)
        self._repo_root: Path = Path(__file__).resolve().parents[2]

        # Default config file location (can be overridden by AGP_CONFIG_FILE)
        self._config_file: Path = (
            Path(os.getenv("AGP_CONFIG_FILE"))
            if os.getenv("AGP_CONFIG_FILE")
            else (self._repo_root / "config" / "settings.yaml")
        )

        self._cache_ttl_seconds: int = 60
        self._cache_timestamp: float = 0.0
        self._cached_settings: Optional[Settings] = None

    # ------------------------------ Public API ------------------------------

    def get(self) -> Settings:
        """Return current settings, reloading if TTL expired.

        Returns:
            Settings: Validated and possibly overridden configuration.
        """

        now = time.time()
        if self._cached_settings and (now - self._cache_timestamp) < self._cache_ttl_seconds:
            return self._cached_settings

        settings = self._load_and_validate()
        self._cached_settings = settings
        self._cache_timestamp = now
        return settings

    def reload(self) -> Settings:
        """Force a reload of the configuration.

        Returns:
            Settings: Freshly loaded configuration.
        """

        self._logger.info("Reloading configuration from disk and environment overrides.")
        self._cache_timestamp = 0.0
        self._cached_settings = None
        return self.get()

    # ----------------------------- Helper methods ---------------------------

    def get_repo_root(self) -> Path:
        """Get repository root directory.

        Returns:
            Path: Repo root path.
        """

        return self._repo_root

    def get_config_file(self) -> Path:
        """Get the currently used configuration file path.

        Returns:
            Path: Config file path.
        """

        return self._config_file

    def server_ws_url(self, server: str, ws_path: str = "/ws", client_id: Optional[str] = None) -> str:
        """Build a ws:// URL from server name and optional path/client id.

        Args:
            server: One of "mcp_bridge", "unity_editor", "blender_addon".
            ws_path: Path component, defaults to "/ws".
            client_id: Optional client id segment appended to the URL.

        Returns:
            str: WebSocket URL.
        """

        cfg = self.get()
        endpoint = getattr(cfg.servers, server)
        base = f"ws://{endpoint.host}:{endpoint.port}{ws_path}"
        return f"{base}/{client_id}" if client_id else base

    # ----------------------------- Internal logic ---------------------------

    def _load_and_validate(self) -> Settings:
        """Load YAML settings, apply env overrides, validate and resolve paths.

        Returns:
            Settings: Validated settings.

        Raises:
            None: All errors are handled gracefully with defaults.
        """

        data = None
        if self._config_file.exists() and yaml is not None:
            try:
                with self._config_file.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)  # type: ignore[attr-defined]
                self._logger.info("Loaded configuration file: %s", self._config_file)
            except Exception as e:  # YAML error or IO
                self._logger.warning(
                    "Failed to load YAML config (%s). Falling back to defaults. Error: %s",
                    self._config_file,
                    e,
                )
        elif yaml is None:
            self._logger.warning(
                "PyYAML not installed. Using default configuration values.")
        else:
            self._logger.warning(
                "Config file not found: %s. Using default configuration.", self._config_file
            )

        # Build initial settings (from YAML or defaults)
        try:
            if data is None:
                settings = _default_settings(self._repo_root)
            else:
                # Validate raw YAML using Pydantic; resolve relative paths after
                settings = Settings(**data)
                # Resolve relative paths against repo root
                settings.paths = PathsConfig(
                    unity_project=_resolve_relative(self._repo_root, settings.paths.unity_project),
                    blender_export=_resolve_relative(self._repo_root, settings.paths.blender_export),
                    templates=_resolve_relative(self._repo_root, settings.paths.templates),
                )
                settings.logging = LoggingConfig(
                    level=settings.logging.level,
                    file=_resolve_relative(self._repo_root, settings.logging.file),
                )
        except ValidationError as ve:
            self._logger.warning("Invalid configuration schema. Using defaults. Details: %s", ve)
            settings = _default_settings(self._repo_root)

        # Apply environment overrides
        settings = self._apply_env_overrides(settings)

        # Final sanity log
        self._logger.info(
            "Active config -> mcp_bridge: %s:%s, blender_addon: %s:%s",
            settings.servers.mcp_bridge.host,
            settings.servers.mcp_bridge.port,
            settings.servers.blender_addon.host,
            settings.servers.blender_addon.port,
        )
        return settings

    def _apply_env_overrides(self, settings: Settings) -> Settings:
        """Apply environment variable overrides to settings.

        Args:
            settings: Settings object to mutate via overrides.

        Returns:
            Settings: Mutated settings with overrides applied.
        """

        def _int_env(name: str, default: Optional[int]) -> Optional[int]:
            v = os.getenv(name)
            if v is None:
                return default
            try:
                return int(v)
            except ValueError:
                self._logger.warning("Invalid int for %s: %s (ignored)", name, v)
                return default

        # Servers
        mcp_host = os.getenv("MCP_HOST") or settings.servers.mcp_bridge.host
        mcp_port = _int_env("MCP_PORT", settings.servers.mcp_bridge.port) or settings.servers.mcp_bridge.port
        uni_host = os.getenv("UNITY_HOST") or settings.servers.unity_editor.host
        uni_port = _int_env("UNITY_PORT", settings.servers.unity_editor.port) or settings.servers.unity_editor.port
        ble_host = os.getenv("BLENDER_HOST") or settings.servers.blender_addon.host
        ble_port = _int_env("BLENDER_PORT", settings.servers.blender_addon.port) or settings.servers.blender_addon.port

        # Timeouts
        mcp_to = _int_env("MCP_TIMEOUT", settings.timeouts.mcp_bridge) or settings.timeouts.mcp_bridge
        uni_to = _int_env("UNITY_TIMEOUT", settings.timeouts.unity_editor) or settings.timeouts.unity_editor
        ble_to = _int_env("BLENDER_TIMEOUT", settings.timeouts.blender_addon) or settings.timeouts.blender_addon

        # Paths
        unity_project_dir = Path(os.getenv("UNITY_PROJECT_DIR") or settings.paths.unity_project)
        blender_export_dir = Path(os.getenv("BLENDER_EXPORT_DIR") or settings.paths.blender_export)
        templates_dir = Path(os.getenv("TEMPLATES_DIR") or settings.paths.templates)

        # Logging
        log_level = os.getenv("LOG_LEVEL") or settings.logging.level
        log_file = Path(os.getenv("LOG_FILE") or settings.logging.file)

        # Construct new settings object applying overrides
        overridden = Settings(
            servers=Servers(
                mcp_bridge=ServerConfig(host=mcp_host, port=mcp_port),
                unity_editor=ServerConfig(host=uni_host, port=uni_port),
                blender_addon=ServerConfig(host=ble_host, port=ble_port),
            ),
            paths=PathsConfig(
                unity_project=_resolve_relative(self._repo_root, unity_project_dir),
                blender_export=_resolve_relative(self._repo_root, blender_export_dir),
                templates=_resolve_relative(self._repo_root, templates_dir),
            ),
            logging=LoggingConfig(level=log_level, file=_resolve_relative(self._repo_root, log_file)),
            timeouts=TimeoutsConfig(mcp_bridge=mcp_to, unity_editor=uni_to, blender_addon=ble_to),
        )

        # Informative debug lines
        self._logger.debug("Env overrides applied: MCP_PORT=%s UNITY_PORT=%s BLENDER_PORT=%s", mcp_port, uni_port, ble_port)
        return overridden

