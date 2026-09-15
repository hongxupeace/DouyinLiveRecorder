from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

from .domain import ProbeResult, ProbeSettings, Room
from .probe import ProbeRegistry


class ProbeTaskSignals(QObject):
    finished = Signal(str, object)


class ProbeTask(QRunnable):
    def __init__(
        self,
        room_id: str,
        url: str,
        settings: ProbeSettings,
        registry: ProbeRegistry,
    ):
        super().__init__()
        self.room_id = room_id
        self.url = url
        self.settings = settings
        self.registry = registry
        self.signals = ProbeTaskSignals()

    def run(self) -> None:
        try:
            result = asyncio.run(self.registry.probe(self.url, self.settings))
        except Exception as error:  # noqa: BLE001 - QRunnable must report all failures.
            result = ProbeResult(is_live=False, error=str(error))
        self.signals.finished.emit(self.room_id, result)


class MonitoringCoordinator(QObject):
    checking = Signal(str)
    result_ready = Signal(str, object, str)

    def __init__(
        self,
        room_provider: Callable[[], list[Room]],
        settings_provider: Callable[[], ProbeSettings],
        interval_provider: Callable[[], int],
        registry: ProbeRegistry | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._room_provider = room_provider
        self._settings_provider = settings_provider
        self._interval_provider = interval_provider
        self._registry = registry or ProbeRegistry()
        self._thread_pool = QThreadPool(self)
        self._thread_pool.setMaxThreadCount(4)
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._next_due: dict[str, float] = {}
        self._in_flight: set[str] = set()
        self._purposes: dict[str, str] = {}
        self._tasks: set[ProbeTask] = set()

    def start(self) -> None:
        self._timer.start()
        self._tick()

    def stop(self) -> None:
        self._timer.stop()
        self._thread_pool.clear()
        self._thread_pool.waitForDone(3000)

    def probe_now(self, room: Room, purpose: str = "monitor") -> None:
        if room.id in self._in_flight:
            if purpose == "record":
                self._purposes[room.id] = purpose
            return
        self._submit(room, purpose)

    def forget(self, room_id: str) -> None:
        self._next_due.pop(room_id, None)
        self._purposes.pop(room_id, None)

    def _tick(self) -> None:
        now = time.monotonic()
        room_ids = set()
        for room in self._room_provider():
            room_ids.add(room.id)
            if (
                room.monitor_enabled
                and room.id not in self._in_flight
                and now >= self._next_due.get(room.id, 0)
            ):
                self._submit(room, "monitor")
        for stale_id in set(self._next_due) - room_ids:
            self.forget(stale_id)

    def _submit(self, room: Room, purpose: str) -> None:
        self._in_flight.add(room.id)
        self._purposes[room.id] = purpose
        self.checking.emit(room.id)
        task = ProbeTask(
            room_id=room.id,
            url=room.url,
            settings=self._settings_provider(),
            registry=self._registry,
        )
        self._tasks.add(task)
        task.signals.finished.connect(
            lambda room_id, result, current_task=task: self._finish(
                room_id, result, current_task
            )
        )
        self._thread_pool.start(task)

    def _finish(self, room_id: str, result: ProbeResult, task: ProbeTask) -> None:
        self._tasks.discard(task)
        self._in_flight.discard(room_id)
        purpose = self._purposes.pop(room_id, "monitor")
        interval = max(10, self._interval_provider())
        self._next_due[room_id] = time.monotonic() + interval
        self.result_ready.emit(room_id, result, purpose)
