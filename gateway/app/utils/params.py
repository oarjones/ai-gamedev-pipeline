"""Request params helpers for API consistency.

Conventions:
- API layer uses camelCase (projectId)
- Python internals use snake_case (project_id)
"""

from typing import Optional


def normalize_project_id(projectId: Optional[str] = None, project_id: Optional[str] = None) -> str:
    """Normalize project identifier from common aliases.

    Returns the first non-empty value among projectId and project_id.
    """
    return (projectId or project_id or "").strip()

