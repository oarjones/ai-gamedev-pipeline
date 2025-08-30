"""Commands package with auto-registration via decorators.

Importing this package imports submodules, triggering @command decorators
to register functions into the global registry.
"""

from . import modeling as _modeling  # noqa: F401
from . import topology as _topology  # noqa: F401
from . import topology_cleanup as _topology_cleanup  # noqa: F401
from . import normals as _normals  # noqa: F401
from . import modeling_edit as _modeling_edit  # noqa: F401
from . import modifiers_core as _modifiers_core  # noqa: F401
from . import selection_sets as _selection_sets  # noqa: F401
from . import analysis_metrics as _analysis_metrics  # noqa: F401
from . import proc_terrain as _proc_terrain  # noqa: F401
from . import proc_arch as _proc_arch  # noqa: F401
from . import proc_character as _proc_character  # noqa: F401
from . import reference_blueprints as _reference_blueprints  # noqa: F401
from . import reference as _reference  # noqa: F401
from . import mesh as _mesh  # noqa: F401
# Import helpers to register commands under the 'helpers' namespace
from ..helpers import snapshot as _helpers_snapshot  # noqa: F401

# Optional lightweight builtin server command
from ..server.registry import command, tool, COMMANDS
from ..server.context import SessionContext


@command("server.ping")
@tool
def _server_ping(ctx: SessionContext, params: dict) -> dict:
    return {"pong": True}


@command("server.list_commands")
@tool
def _server_list_commands(ctx: SessionContext, params: dict) -> dict:
    # Return a sorted list of available command names
    try:
        names = sorted(COMMANDS.keys())
    except Exception:
        names = []
    return {"commands": names}
