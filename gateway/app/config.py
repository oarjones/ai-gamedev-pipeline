"""Configuration management for AI Gateway."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerConfig(BaseModel):
    """Server configuration."""
    
    model_config = ConfigDict(extra="forbid")
    
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False


class CorsConfig(BaseModel):
    """CORS configuration."""
    
    model_config = ConfigDict(extra="forbid")
    
    allow_origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    allow_credentials: bool = True
    allow_methods: List[str] = ["*"]
    allow_headers: List[str] = ["*"]


class AuthConfig(BaseModel):
    """Auth configuration (minimal API key)."""

    model_config = ConfigDict(extra="forbid")

    require_api_key: bool = True
    api_key: str = "dev-local-key"


class ChatConfig(BaseModel):
    """Chat configuration."""

    model_config = ConfigDict(extra="forbid")

    max_message_length: int = 4000
    history_limit_default: int = 50


class Settings(BaseSettings):
    """Main settings class with YAML and environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        # Ignore unrelated env vars so legacy .env keys don't break startup
        extra="ignore",
    )
    
    server: ServerConfig = Field(default_factory=ServerConfig)
    cors: CorsConfig = Field(default_factory=CorsConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    chat: ChatConfig = Field(default_factory=ChatConfig)
    # Raw processes config loaded from YAML under gateway.processes
    processes: Optional[Dict[str, Any]] = Field(default_factory=dict)


def load_settings() -> Settings:
    """Load settings from YAML file and environment variables."""
    
    # Buscar el archivo relativo al archivo Python actual, no al CWD
    # Este archivo está en gateway/app/config.py
    # El settings.yaml está en la raíz del proyecto: config/settings.yaml
    # Entonces subimos 2 niveles (app -> gateway -> raíz) y luego config/settings.yaml
    
    current_file = Path(__file__).resolve()  # gateway/app/config.py
    project_root = current_file.parent.parent.parent  # Subir 3 niveles: app -> gateway -> raíz
    config_path = project_root / "config" / "settings.yaml"
    
    # También intentar en gateway/config si no existe en la raíz
    local_config_path = current_file.parent.parent / "config" / "settings.yaml"
    
    yaml_config: Dict[str, Any] = {}
    
    # Primero intentar en la raíz del proyecto
    if config_path.exists():
        print(f"[Config] Loading from project root: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            full_config = yaml.safe_load(f) or {}
            # Extract gateway-specific config
            yaml_config = full_config.get("gateway", {})
    # Si no, intentar en gateway/config
    elif local_config_path.exists():
        print(f"[Config] Loading from gateway local: {local_config_path}")
        with open(local_config_path, "r", encoding="utf-8") as f:
            full_config = yaml.safe_load(f) or {}
            # Extract gateway-specific config
            yaml_config = full_config.get("gateway", {})
    else:
        print(f"[Config] WARNING: No settings.yaml found at {config_path} or {local_config_path}")
        print("[Config] Using default configuration")
    
    # Create settings with YAML config as defaults, env vars override
    settings = Settings(**yaml_config)
    
    # Log what was loaded (útil para debug)
    if settings.processes:
        print(f"[Config] Loaded processes: {list(settings.processes.keys())}")
        if "unity" in settings.processes:
            unity_exe = settings.processes["unity"].get("exe")
            print(f"[Config] Unity exe: {unity_exe}")
    
    return settings


# Global settings instance
settings = load_settings()