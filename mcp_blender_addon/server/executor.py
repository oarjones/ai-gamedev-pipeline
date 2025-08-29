from __future__ import annotations

import threading
import queue
from typing import Any, Callable, Tuple

from .logging import get_logger


try:
    import bpy  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore


Task = Tuple[Callable[..., Any], tuple, dict, "_Result"]


class _Result:
    def __init__(self) -> None:
        self._event = threading.Event()
        self._value: Any = None
        self._error: BaseException | None = None

    def set(self, value: Any = None) -> None:
        self._value = value
        self._event.set()

    def set_error(self, exc: BaseException) -> None:
        self._error = exc
        self._event.set()

    def get(self, timeout: float | None = None) -> Any:
        if not self._event.wait(timeout):
            raise TimeoutError("executor result timeout")
        if self._error:
            raise self._error
        return self._value


class Executor:
    """Queues callables to run on Blender's main thread via timers.

    If bpy is not available, runs tasks synchronously in the caller thread.
    """

    def __init__(self) -> None:
        self._log = get_logger(__name__)
        self._q: "queue.Queue[Task]" = queue.Queue()
        self._running = False

    def start(self) -> None:
        if bpy is None:
            return
        if self._running:
            return
        self._running = True

        def consumer():  # timer callback
            try:
                while True:
                    fn, args, kwargs, res = self._q.get_nowait()
                    try:
                        value = fn(*args, **kwargs)
                        res.set(value)
                    except BaseException as e:  # noqa: BLE001
                        res.set_error(e)
            except queue.Empty:
                pass
            return 0.05 if self._running else None

        bpy.app.timers.register(consumer, first_interval=0.05)  # type: ignore[attr-defined]
        self._log.info("Executor started (timer consumer registered)")

    def stop(self) -> None:
        self._running = False

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if bpy is None:
            return fn(*args, **kwargs)
        res = _Result()
        self._q.put((fn, args, kwargs, res))
        return res.get()

