"""Commands package with auto-registration via decorators.

Importing this package imports submodules, triggering @command decorators
to register functions into the global registry.
"""

from . import modeling as _modeling  # noqa: F401
from . import topology as _topology  # noqa: F401
from . import normals as _normals  # noqa: F401

# Optional lightweight builtin server command
from ..server.registry import command, tool
from ..server.context import SessionContext


@command("server.ping")
@tool
def _server_ping(ctx: SessionContext, params: dict) -> dict:
    return {"pong": True}
