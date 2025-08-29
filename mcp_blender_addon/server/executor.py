from __future__ import annotations

import threading
import queue
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .logging import get_logger
from .registry import get as reg_get
from .context import SessionContext


try:
    import bpy  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore


MCP_MAX_TASKS = 256


@dataclass
class Task:
    command: str
    params: Dict[str, Any]
    enqueued_at: float
    _event: threading.Event = dataclass(init=False, repr=False)  # type: ignore
    _result: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:  # type: ignore[override]
        object.__setattr__(self, "_event", threading.Event())

    def set_result(self, payload: Dict[str, Any]) -> None:
        self._result = payload
        self._event.set()

    def wait(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        if not self._event.wait(timeout):
            return {
                "status": "error",
                "tool": "executor",
                "message": "timeout waiting for task",
                "trace": "",
            }
        assert self._result is not None
        return self._result


class Executor:
    """Task queue pumped on Blender's main thread via timers.

    - enqueue(command, params) from any thread
    - start_pump() registers a repeating timer (first_interval=0.02)
    - pump drains the queue on main thread and executes commands
    """

    def __init__(self) -> None:
        self._log = get_logger(__name__)
        self._q: "queue.Queue[Task]" = queue.Queue(maxsize=MCP_MAX_TASKS)
        self._running = False
        self._pump_thread_id: Optional[int] = None
        self.metrics_last_duration: float = 0.0

    # -- API --
    def start_pump(self) -> None:
        if bpy is None:
            # Outside Blender: nothing to register; tasks will run synchronously on enqueue
            self._running = True
            return
        if self._running:
            # Re-register timer to survive script reloads if needed
            try:
                bpy.app.timers.register(self._consume_timer, first_interval=0.02, persistent=True)  # type: ignore[attr-defined]
            except Exception:
                pass
            return
        self._running = True
        bpy.app.timers.register(self._consume_timer, first_interval=0.02, persistent=True)  # type: ignore[attr-defined]
        self._log.info("Executor pump started (timer registered)")

    def stop_pump(self) -> None:
        self._running = False

    def in_pump_thread(self) -> bool:
        return self._pump_thread_id is not None and threading.get_ident() == self._pump_thread_id

    def enqueue(self, command: str, params: Dict[str, Any]) -> Task:
        # If queue is full, return an immediate error task
        if self._q.full():
            t = Task(command=command, params=params, enqueued_at=time.time())
            t.set_result({
                "status": "error",
                "tool": "executor",
                "message": "server busy",
                "trace": "",
            })
            return t

        t = Task(command=command, params=params, enqueued_at=time.time())
        if bpy is None:
            # Not in Blender: execute immediately in this thread
            payload = self._execute_task(t)
            t.set_result(payload)
            return t
        self._q.put(t)
        return t

    # -- Capacity helpers for external backpressure --
    def qsize(self) -> int:
        try:
            return self._q.qsize()
        except Exception:
            return 0

    def capacity(self) -> int:
        try:
            return self._q.maxsize or MCP_MAX_TASKS
        except Exception:
            return MCP_MAX_TASKS

    # -- Internals --
    def _consume_timer(self):  # timer callback on main thread
        self._pump_thread_id = threading.get_ident()
        start_loop = time.perf_counter()
        drained = 0
        try:
            while True:
                try:
                    t = self._q.get_nowait()
                except queue.Empty:
                    break
                drained += 1
                payload = self._execute_task(t)
                t.set_result(payload)
        finally:
            self.metrics_last_duration = time.perf_counter() - start_loop
        return 0.02 if self._running else None

    def _execute_task(self, t: Task) -> Dict[str, Any]:
        # Resolve command
        fn = reg_get(t.command)
        if not fn:
            return {
                "status": "error",
                "tool": "executor",
                "message": f"unknown command: {t.command}",
                "trace": "",
            }
        # Build session context; mark has_bpy based on availability
        has_bpy = bpy is not None
        ctx = SessionContext(has_bpy=has_bpy, executor=self)
        qsize = self._q.qsize() if bpy is not None else 0
        t0 = time.perf_counter()
        try:
            result = fn(ctx, t.params)
        except Exception as e:  # noqa: BLE001
            # fn should be a @tool and already normalize errors, but guard anyway
            return {
                "status": "error",
                "tool": getattr(fn, "__name__", "command"),
                "message": str(e),
                "trace": "",
            }
        finally:
            dur = time.perf_counter() - t0
            self._log.info("cmd=%s dur=%.3f q=%d", t.command, dur, qsize)
        return result
