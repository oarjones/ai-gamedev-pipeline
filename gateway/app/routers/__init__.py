"""Router modules for AI Gateway."""

from .projects import router as projects_router
from .agent import router as agent_router
from .chat import router as chat_router
from .timeline import router as timeline_router
from .tools import router as tools_router
from .context import router as context_router
from .config import router as config_router
from .deps import router as deps_router

__all__ = [
    "projects_router",
    "agent_router",
    "chat_router",
    "timeline_router",
    "tools_router",
    "context_router",
    "config_router",
    "deps_router",
]
