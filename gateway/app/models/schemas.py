"""Pydantic schemas for validating AI-generated task plans.

Conventions:
- API/JSON camelCase from providers is normalized by services.
- Internal models use snake_case.
"""

from __future__ import annotations

from typing import Dict, List, Union, Optional
from pydantic import BaseModel, Field, field_validator


class TaskSchema(BaseModel):
    code: str = Field(pattern=r"^T-\d{3}$")
    title: str = Field(min_length=3, max_length=200)
    description: str = ""
    dependencies: List[str] = []
    mcp_tools: List[str] = []
    deliverables: List[str] = []
    acceptance_criteria: List[str]
    estimates: Dict[str, Union[int, float]] = {}
    priority: int = Field(default=1, ge=1, le=5)
    tags: List[str] = []

    @field_validator("dependencies", mode="before")
    @classmethod
    def _deps_as_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return list(v)

    @field_validator("acceptance_criteria", mode="before")
    @classmethod
    def _acc_as_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return list(v)


class TaskPlanSchema(BaseModel):
    plan_version: int
    summary: str
    tasks: List[TaskSchema]

