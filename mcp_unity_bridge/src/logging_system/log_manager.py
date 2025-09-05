from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from logging.handlers import RotatingFileHandler
from typing import Any, Callable, Dict, Optional

import websockets

from .config import log_file_path, log_level, aggregator_ws_url
from .models import LogEntry, LogLevel


@dataclass
class _CircuitBreaker:
    failures: int = 0
    open_until: float = 0.0
    threshold: int = 3
    cooldown: float = 15.0

    def ok(self) -> bool:
        return time.time() >= self.open_until

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.open_until = time.time() + self.cooldown
            self.failures = 0

    def record_success(self) -> None:
        self.failures = 0
        self.open_until = 0.0


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload = {
            "timestamp": getattr(record, "timestamp", time.time()),
            "component": getattr(record, "component", "mcp_bridge"),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
            "category": getattr(record, "category", None),
            "correlation_id": getattr(record, "correlation_id", None),
            "stack": getattr(record, "stack", None),
            "performance_ms": getattr(record, "performance_ms", None),
            "extra": getattr(record, "extra_data", {}),
        }
        return json.dumps(payload, ensure_ascii=False)


class LogManager:
    """Centralized logging manager for Python components.

    - Standard JSON format compatible across components.
    - Rotating file handler (10MB, keep 5).
    - Multiple outputs: file, console, optional WebSocket streaming to aggregator.
    - Critical log forwarding to monitoring endpoint (stub).
    - Context manager helpers and a decorator for function execution logging.
    - Simple sampling via categories.
    """

    def __init__(self, component: str = "mcp_bridge") -> None:
        self.component = component
        self.logger = logging.getLogger(component)
        self.logger.setLevel(getattr(logging, log_level().upper(), logging.INFO))
        self.logger.propagate = False
        if not self.logger.handlers:
            fh = RotatingFileHandler(log_file_path(), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
            ch = logging.StreamHandler(sys.stderr)
            fmt = JsonFormatter()
            fh.setFormatter(fmt)
            ch.setFormatter(fmt)
            self.logger.addHandler(fh)
            self.logger.addHandler(ch)

        self._samples: Dict[str, float] = {}
        self._ws_url = aggregator_ws_url()
        self._ws_lock = asyncio.Lock()
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._cb = _CircuitBreaker()

    # ------------------------ Public API ------------------------

    def set_sampling(self, category: str, rate: float) -> None:
        """Set sampling rate for a category (0..1)."""

        self._samples[category] = max(0.0, min(1.0, rate))

    def get_logger(self) -> logging.Logger:
        return self.logger

    def log(self, level: LogLevel, message: str, *, category: Optional[str] = None, correlation_id: Optional[str] = None, extra: Optional[Dict[str, Any]] = None, stack: Optional[str] = None, performance_ms: Optional[float] = None) -> None:
        if category is not None and not self._allow_sample(category):
            return
        rec = self.logger.makeRecord(
            self.logger.name,
            getattr(logging, level.value, logging.INFO),
            fn="",
            lno=0,
            msg=message,
            args=(),
            exc_info=None,
        )
        rec.timestamp = time.time()
        rec.component = self.component
        rec.category = category
        rec.correlation_id = correlation_id
        rec.extra_data = extra or {}
        rec.stack = stack
        rec.performance_ms = performance_ms
        self.logger.handle(rec)

        # Fire-and-forget WS send
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._send_ws(LogEntry(timestamp=rec.timestamp, component=self.component, level=level, module=rec.name, message=message, category=category, correlation_id=correlation_id, stack=stack, performance_ms=performance_ms, extra=extra or {})))
        except Exception:
            pass

        if level == LogLevel.CRITICAL:
            self._send_critical_monitoring(message, correlation_id=correlation_id, extra=extra)

    def debug(self, msg: str, **kw: Any) -> None:
        self.log(LogLevel.DEBUG, msg, **kw)

    def info(self, msg: str, **kw: Any) -> None:
        self.log(LogLevel.INFO, msg, **kw)

    def warning(self, msg: str, **kw: Any) -> None:
        self.log(LogLevel.WARNING, msg, **kw)

    def error(self, msg: str, **kw: Any) -> None:
        self.log(LogLevel.ERROR, msg, **kw)

    def critical(self, msg: str, **kw: Any) -> None:
        self.log(LogLevel.CRITICAL, msg, **kw)

    @contextmanager
    def operation(self, name: str, *, category: Optional[str] = "operation", correlation_id: Optional[str] = None, extra: Optional[Dict[str, Any]] = None):
        start = time.perf_counter()
        self.info(f"{name}: start", category=category, correlation_id=correlation_id, extra=extra)
        try:
            yield
            elapsed = (time.perf_counter() - start) * 1000.0
            self.info(f"{name}: success", category=category, correlation_id=correlation_id, performance_ms=elapsed, extra=extra)
        except Exception as e:
            stack = traceback.format_exc()
            elapsed = (time.perf_counter() - start) * 1000.0
            self.error(f"{name}: error {e}", category=category, correlation_id=correlation_id, performance_ms=elapsed, extra=extra, stack=stack)
            raise

    def log_execution(self, name: Optional[str] = None, category: Optional[str] = "execution") -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            lbl = name or fn.__name__

            @wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                with self.operation(lbl, category=category):
                    return fn(*args, **kwargs)

            return wrapper

        return decorator

    # ------------------------ Internals ------------------------

    def _allow_sample(self, category: str) -> bool:
        import random

        rate = self._samples.get(category)
        return True if rate is None else (random.random() < rate)

    async def _send_ws(self, entry: LogEntry) -> None:
        if not self._cb.ok():
            return
        try:
            async with self._ws_lock:
                if self._ws is None or self._ws.closed:
                    self._ws = await websockets.connect(self._ws_url, ping_interval=20, ping_timeout=20)
            if self._ws:
                await self._ws.send(json.dumps({"type": "log", "payload": entry.model_dump()}))
            self._cb.record_success()
        except Exception:
            self._cb.record_failure()
            try:
                async with self._ws_lock:
                    if self._ws:
                        await self._ws.close()
                    self._ws = None
            except Exception:
                self._ws = None

    def _send_critical_monitoring(self, message: str, *, correlation_id: Optional[str], extra: Optional[Dict[str, Any]]) -> None:
        # Stub: place to integrate with an external monitoring endpoint.
        # For now, we just ensure it's clearly recorded locally.
        rec = self.logger.makeRecord(self.logger.name, logging.CRITICAL, fn="", lno=0, msg=f"MONITORING: {message}", args=(), exc_info=None)
        rec.timestamp = time.time()
        rec.component = self.component
        rec.correlation_id = correlation_id
        rec.extra_data = extra or {}
        self.logger.handle(rec)

