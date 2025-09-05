"""Infraestructura de logging para el add-on de Blender.

Configura salida a consola y archivo rotativo (1MB x3). Usa un logger
de raíz `mcp_blender_addon` y expone `get_logger` para submódulos.
"""

from __future__ import annotations

import logging
import sys
import os
from logging.handlers import RotatingFileHandler


_configured = False


def _log_dir() -> str:
    # Prefer user home dir to avoid permission issues within Blender install
    base = os.path.join(os.path.expanduser("~"), ".mcp_blender_addon", "logs")
    try:
        os.makedirs(base, exist_ok=True)
        return base
    except Exception:
        # Fallback to current working directory
        base = os.path.join(os.getcwd(), "logs")
        os.makedirs(base, exist_ok=True)
        return base


def _configure_once() -> None:
    global _configured
    if _configured:
        return
    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
    formatter = logging.Formatter(fmt)

    # Console handler
    sh = logging.StreamHandler(stream=sys.stdout)
    sh.setFormatter(formatter)

    # Rotating file handler (1MB, 3 backups)
    try:
        fh_path = os.path.join(_log_dir(), "addon.log")
        fh = RotatingFileHandler(fh_path, maxBytes=1_000_000, backupCount=3)
        fh.setFormatter(formatter)
    except Exception:
        fh = None

    root = logging.getLogger("mcp_blender_addon")
    root.setLevel(logging.INFO)
    root.addHandler(sh)
    if fh is not None:
        root.addHandler(fh)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    _configure_once()
    return logging.getLogger(f"mcp_blender_addon.{name}")
