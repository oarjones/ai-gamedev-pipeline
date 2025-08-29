from __future__ import annotations

import logging
import sys


_configured = False


def _configure_once() -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(stream=sys.stdout)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handler.setFormatter(logging.Formatter(fmt))
    root = logging.getLogger("mcp_blender_addon")
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    _configure_once()
    return logging.getLogger(f"mcp_blender_addon.{name}")

