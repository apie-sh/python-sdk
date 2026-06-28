from __future__ import annotations

import asyncio
import json
import random
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from .errors import ApieError
from .events import async_send_events, send_events
from .http import AsyncHttpClient, HttpClient


@dataclass(slots=True)
class EventQueueDiagnostics:
    queue_size: int = 0
    dropped_count: int = 0
    deduplicated_count: int = 0
    flush_count: int = 0
    retry_count: int = 0
    last_error_at: Optional[str] = None
    last_flush_at: Optional[str] = None
    last_error_message: Optional[str] = None


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


class EventQueue:
    def __init__(
        self,
        http: HttpClient,
        *,
        flush_interval_ms: int = 2000,
        max_batch_size: int = 25,
        max_queue_size: int = 5000,
        retry_attempts: int = 3,
        retry_base_delay_ms: int = 250,
        drop_policy: str = "drop_oldest",
        durable_storage_path: Optional[str] = None,
        idempotency_key: Optional[Callable[[dict[str, Any]], Optional[str]]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        transform: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
    ) -> None:
        self._http = http
        self._flush_interval_ms = flush_interval_ms
        self._max_batch_size = max_batch_size
        self._max_queue_size = max_queue_size
        self._retry_attempts = retry_attempts
        self._retry_base_delay_ms = retry_base_delay_ms
        self._drop_policy = drop_policy
        self._storage_path = durable_storage_path
        self._idempotency_key = idempotency_key
        self._on_error = on_error or (lambda error: None)
        self._transform = transform

        self._queue: list[dict[str, Any]] = []
        self._queued_keys: set[str] = set()
        self._diagnostics = EventQueueDiagnostics()
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._flushing = False

        self._restore_persisted_queue()
        self._sync_diagnostics()

    def _is_retryable_error(self, error: Exception) -> bool:
        if not isinstance(error, ApieError):
            return True
        if error.status in {408, 409, 429}:
            return True
        return error.status >= 500

    def _jitter(self, delay_ms: int) -> int:
        jitter_multiplier = 0.75 + random.random() * 0.5
        return max(50, int(round(delay_ms * jitter_multiplier)))

    def _resolve_retry_delay(self, attempt: int, error: Exception) -> Optional[int]:
        if not self._is_retryable_error(error):
            return None
        if isinstance(error, ApieError) and error.retry_after_ms is not None:
            return self._jitter(max(error.retry_after_ms, self._retry_base_delay_ms))
        delay = self._retry_base_delay_ms * (2 ** (attempt - 1))
        return self._jitter(delay)

    def start(self) -> None:
        if self._running:
            return
        self._running = True

        def _loop() -> None:
            while self._running:
                time.sleep(self._flush_interval_ms / 1000)
                try:
                    self.flush()
                except Exception as error:  # pragma: no cover - defensive
                    self._on_error(error)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self._thread = None

    def _resolve_event_key(self, event: dict[str, Any]) -> Optional[str]:
        if self._idempotency_key is not None:
            return self._idempotency_key(event)
        event_id = event.get("eventId")
        return str(event_id) if event_id else None

    def enqueue(self, event: dict[str, Any]) -> None:
        prepared = self._transform(event) if self._transform else event
        key = self._resolve_event_key(prepared)
        with self._lock:
            if key and key in self._queued_keys:
                self._diagnostics.deduplicated_count += 1
                self._sync_diagnostics()
                return

            if len(self._queue) >= self._max_queue_size:
                if self._drop_policy == "drop_newest":
                    self._diagnostics.dropped_count += 1
                    self._sync_diagnostics()
                    return
                dropped = self._queue.pop(0)
                dropped_key = self._resolve_event_key(dropped)
                if dropped_key:
                    self._queued_keys.discard(dropped_key)
                self._diagnostics.dropped_count += 1

            self._queue.append(prepared)
            if key:
                self._queued_keys.add(key)
            self._persist_queue()
            self._sync_diagnostics()

        if len(self._queue) >= self._max_batch_size:
            self.flush()

    def _send_batch_with_retry(self, batch: list[dict[str, Any]]) -> None:
        attempt = 0
        while attempt < self._retry_attempts:
            try:
                send_events(self._http, batch)
                return
            except Exception as error:
                attempt += 1
                self._diagnostics.retry_count += 1
                if attempt >= self._retry_attempts:
                    raise
                delay = self._resolve_retry_delay(attempt, error)
                if delay is None:
                    raise
                time.sleep(delay / 1000)

    def flush(self) -> None:
        with self._lock:
            if self._flushing or not self._queue:
                return
            self._flushing = True
        try:
            while True:
                with self._lock:
                    if not self._queue:
                        break
                    batch = self._queue[: self._max_batch_size]
                try:
                    self._send_batch_with_retry(batch)
                    with self._lock:
                        self._queue = self._queue[len(batch) :]
                        for event in batch:
                            key = self._resolve_event_key(event)
                            if key:
                                self._queued_keys.discard(key)
                        self._diagnostics.flush_count += 1
                        self._diagnostics.last_flush_at = _now_iso()
                        self._persist_queue()
                except Exception as error:
                    self._on_error(error)
                    self._diagnostics.last_error_at = _now_iso()
                    self._diagnostics.last_error_message = str(error)
                    break
        finally:
            with self._lock:
                self._sync_diagnostics()
                self._flushing = False

    def get_diagnostics(self) -> EventQueueDiagnostics:
        with self._lock:
            return EventQueueDiagnostics(
                queue_size=self._diagnostics.queue_size,
                dropped_count=self._diagnostics.dropped_count,
                deduplicated_count=self._diagnostics.deduplicated_count,
                flush_count=self._diagnostics.flush_count,
                retry_count=self._diagnostics.retry_count,
                last_error_at=self._diagnostics.last_error_at,
                last_flush_at=self._diagnostics.last_flush_at,
                last_error_message=self._diagnostics.last_error_message,
            )

    def _sync_diagnostics(self) -> None:
        self._diagnostics.queue_size = len(self._queue)

    def _restore_persisted_queue(self) -> None:
        if not self._storage_path:
            return
        path = Path(self._storage_path)
        if not path.exists():
            return
        try:
            raw = path.read_text(encoding="utf-8")
            if not raw.strip():
                return
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                return
            for candidate in parsed:
                if not isinstance(candidate, dict):
                    continue
                if len(self._queue) >= self._max_queue_size:
                    break
                key = self._resolve_event_key(candidate)
                if key and key in self._queued_keys:
                    continue
                self._queue.append(candidate)
                if key:
                    self._queued_keys.add(key)
        except Exception as error:
            self._on_error(error)

    def _persist_queue(self) -> None:
        if not self._storage_path:
            return
        path = Path(self._storage_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._queue), encoding="utf-8")
        except Exception as error:
            self._on_error(error)


class AsyncEventQueue:
    def __init__(
        self,
        http: AsyncHttpClient,
        *,
        flush_interval_ms: int = 2000,
        max_batch_size: int = 25,
        max_queue_size: int = 5000,
        retry_attempts: int = 3,
        retry_base_delay_ms: int = 250,
        drop_policy: str = "drop_oldest",
        durable_storage_path: Optional[str] = None,
        idempotency_key: Optional[Callable[[dict[str, Any]], Optional[str]]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        transform: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
    ) -> None:
        self._http = http
        self._flush_interval_ms = flush_interval_ms
        self._max_batch_size = max_batch_size
        self._max_queue_size = max_queue_size
        self._retry_attempts = retry_attempts
        self._retry_base_delay_ms = retry_base_delay_ms
        self._drop_policy = drop_policy
        self._storage_path = durable_storage_path
        self._idempotency_key = idempotency_key
        self._on_error = on_error or (lambda error: None)
        self._transform = transform

        self._queue: list[dict[str, Any]] = []
        self._queued_keys: set[str] = set()
        self._diagnostics = EventQueueDiagnostics()
        self._flushing = False
        self._task: Optional[asyncio.Task[None]] = None

        self._restore_persisted_queue()
        self._sync_diagnostics()

    def _is_retryable_error(self, error: Exception) -> bool:
        if not isinstance(error, ApieError):
            return True
        if error.status in {408, 409, 429}:
            return True
        return error.status >= 500

    def _jitter(self, delay_ms: int) -> int:
        jitter_multiplier = 0.75 + random.random() * 0.5
        return max(50, int(round(delay_ms * jitter_multiplier)))

    def _resolve_retry_delay(self, attempt: int, error: Exception) -> Optional[int]:
        if not self._is_retryable_error(error):
            return None
        if isinstance(error, ApieError) and error.retry_after_ms is not None:
            return self._jitter(max(error.retry_after_ms, self._retry_base_delay_ms))
        delay = self._retry_base_delay_ms * (2 ** (attempt - 1))
        return self._jitter(delay)

    def start(self) -> None:
        if self._task is not None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        async def _loop() -> None:
            while True:
                await asyncio.sleep(self._flush_interval_ms / 1000)
                await self.flush()

        self._task = loop.create_task(_loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    def _resolve_event_key(self, event: dict[str, Any]) -> Optional[str]:
        if self._idempotency_key is not None:
            return self._idempotency_key(event)
        event_id = event.get("eventId")
        return str(event_id) if event_id else None

    def enqueue(self, event: dict[str, Any]) -> None:
        prepared = self._transform(event) if self._transform else event
        key = self._resolve_event_key(prepared)
        if key and key in self._queued_keys:
            self._diagnostics.deduplicated_count += 1
            self._sync_diagnostics()
            return

        if len(self._queue) >= self._max_queue_size:
            if self._drop_policy == "drop_newest":
                self._diagnostics.dropped_count += 1
                self._sync_diagnostics()
                return
            dropped = self._queue.pop(0)
            dropped_key = self._resolve_event_key(dropped)
            if dropped_key:
                self._queued_keys.discard(dropped_key)
            self._diagnostics.dropped_count += 1

        self._queue.append(prepared)
        if key:
            self._queued_keys.add(key)
        self._persist_queue()
        self._sync_diagnostics()

    async def _send_batch_with_retry(self, batch: list[dict[str, Any]]) -> None:
        attempt = 0
        while attempt < self._retry_attempts:
            try:
                await async_send_events(self._http, batch)
                return
            except Exception as error:
                attempt += 1
                self._diagnostics.retry_count += 1
                if attempt >= self._retry_attempts:
                    raise
                delay = self._resolve_retry_delay(attempt, error)
                if delay is None:
                    raise
                await asyncio.sleep(delay / 1000)

    async def flush(self) -> None:
        if self._flushing or not self._queue:
            return
        self._flushing = True
        try:
            while self._queue:
                batch = self._queue[: self._max_batch_size]
                try:
                    await self._send_batch_with_retry(batch)
                    self._queue = self._queue[len(batch) :]
                    for event in batch:
                        key = self._resolve_event_key(event)
                        if key:
                            self._queued_keys.discard(key)
                    self._diagnostics.flush_count += 1
                    self._diagnostics.last_flush_at = _now_iso()
                    self._persist_queue()
                except Exception as error:
                    self._on_error(error)
                    self._diagnostics.last_error_at = _now_iso()
                    self._diagnostics.last_error_message = str(error)
                    break
        finally:
            self._sync_diagnostics()
            self._flushing = False

    def get_diagnostics(self) -> EventQueueDiagnostics:
        return EventQueueDiagnostics(
            queue_size=self._diagnostics.queue_size,
            dropped_count=self._diagnostics.dropped_count,
            deduplicated_count=self._diagnostics.deduplicated_count,
            flush_count=self._diagnostics.flush_count,
            retry_count=self._diagnostics.retry_count,
            last_error_at=self._diagnostics.last_error_at,
            last_flush_at=self._diagnostics.last_flush_at,
            last_error_message=self._diagnostics.last_error_message,
        )

    def _sync_diagnostics(self) -> None:
        self._diagnostics.queue_size = len(self._queue)

    def _restore_persisted_queue(self) -> None:
        if not self._storage_path:
            return
        path = Path(self._storage_path)
        if not path.exists():
            return
        try:
            raw = path.read_text(encoding="utf-8")
            if not raw.strip():
                return
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                return
            for candidate in parsed:
                if not isinstance(candidate, dict):
                    continue
                if len(self._queue) >= self._max_queue_size:
                    break
                key = self._resolve_event_key(candidate)
                if key and key in self._queued_keys:
                    continue
                self._queue.append(candidate)
                if key:
                    self._queued_keys.add(key)
        except Exception as error:
            self._on_error(error)

    def _persist_queue(self) -> None:
        if not self._storage_path:
            return
        path = Path(self._storage_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._queue), encoding="utf-8")
        except Exception as error:
            self._on_error(error)
