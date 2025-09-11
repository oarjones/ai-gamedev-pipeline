from __future__ import annotations

import enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class LogLevel(str, enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogEntry(BaseModel):
    timestamp: float = Field(..., description="Unix epoch seconds with fraction")
    component: str
    level: LogLevel
    module: str
    message: str
    category: Optional[str] = None
    correlation_id: Optional[str] = None
    stack: Optional[str] = None
    performance_ms: Optional[float] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class WSLogMessage(BaseModel):
    type: str = Field("log", const=True)
    payload: LogEntry


class QueryFilters(BaseModel):
    component: Optional[str] = None
    level: Optional[LogLevel] = None
    keyword: Optional[str] = None
    start_ts: Optional[float] = None
    end_ts: Optional[float] = None

