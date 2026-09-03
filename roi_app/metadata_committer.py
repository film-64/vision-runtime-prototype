from __future__ import annotations

from dataclasses import asdict, dataclass
import queue
import threading
import time
from typing import Any

from dynamic_pipeline.core.durable_metadata import PortableMetadataEvent
from dynamic_pipeline.core.metadata_jsonl import MetadataJsonlWriter
from .metadata_package_manager import MetadataPackageManager


@dataclass
class MetadataRuntimeStatus:
    enabled: bool
    mode: str
    queue_depth: int
    queue_capacity: int
    commit_p95_ms: float
    records_written: int
    records_dropped: int
    last_error: str | None
    recording_id: str
    current_output_path: str
    package_id: str
    package_path: str
    raw_runtime_object_rejected_count: int = 0
    shutdown_unflushed_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MetadataCommitter:
    """Bounded asynchronous writer for durable portable metadata events."""

    def __init__(
        self,
        package_manager: MetadataPackageManager,
        *,
        enabled: bool = False,
        queue_capacity: int = 256,
        flush_records: int = 32,
        flush_interval_ms: int = 1000,
        metrics: Any = None,
    ):
        self.package_manager = package_manager
        self.enabled = bool(enabled) and package_manager.is_enabled_for_landing()
        self.queue_capacity = max(1, int(queue_capacity))
        self.flush_records = max(1, int(flush_records))
        self.flush_interval_ms = max(1, int(flush_interval_ms))
        self.metrics = metrics
        self.mode = "disabled" if not self.enabled else "open"
        self.records_dropped = 0
        self.last_error: str | None = None
        self.raw_runtime_object_rejected_count = 0
        self.shutdown_unflushed_count = 0
        self._latencies: list[float] = []
        self._queue: queue.Queue[PortableMetadataEvent] = queue.Queue(maxsize=self.queue_capacity)
        self._stop = threading.Event()
        self._writer: MetadataJsonlWriter | None = None
        self._thread: threading.Thread | None = None
        if self.enabled:
            self.package_manager.ensure_open()
            self._writer = MetadataJsonlWriter(self.package_manager.paths.metadata)
            self._thread = threading.Thread(target=self._run, name="metadata-committer", daemon=True)
            self._thread.start()

    @property
    def records_written(self) -> int:
        return int(getattr(self._writer, "records_written", 0) or 0)

    def submit(self, event: PortableMetadataEvent) -> bool:
        if not self.enabled:
            return False
        if not isinstance(event, PortableMetadataEvent):
            self.raw_runtime_object_rejected_count += 1
            return False
        try:
            self._queue.put_nowait(event)
            return True
        except queue.Full:
            self.records_dropped += 1
            return False

    def _run(self) -> None:
        last_flush = time.monotonic()
        pending = 0
        while not self._stop.is_set() or not self._queue.empty():
            try:
                event = self._queue.get(timeout=0.05)
            except queue.Empty:
                if pending and self._should_flush(last_flush, pending):
                    self._flush()
                    pending = 0
                    last_flush = time.monotonic()
                continue
            start = time.perf_counter()
            try:
                if self._writer is not None:
                    self._writer.write(event)
                    self.package_manager.ref_writer().append_event_refs(event)
                    self.package_manager.append_indexes_for_event(event)
                    self.package_manager.write_writer_checkpoint(event)
                    pending += 1
                    if self._should_flush(last_flush, pending):
                        self._flush()
                        pending = 0
                        last_flush = time.monotonic()
            except Exception as exc:
                self.mode = "error"
                self.last_error = str(exc)
            finally:
                self._latencies.append((time.perf_counter() - start) * 1000.0)
                self._queue.task_done()
        if self._writer is not None:
            self._flush()
            self._writer.close()

    def _should_flush(self, last_flush: float, pending: int) -> bool:
        return pending >= self.flush_records or (time.monotonic() - last_flush) * 1000.0 >= self.flush_interval_ms

    def _flush(self) -> None:
        if self._writer is not None:
            self._writer.flush()

    def shutdown(self, timeout_s: float = 1.0) -> None:
        if not self.enabled:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(0.0, float(timeout_s)))
        if self._thread is not None and self._thread.is_alive():
            self.shutdown_unflushed_count = self._queue.qsize()
            self.mode = "error"
            self.package_manager.mark_state("partial")
        else:
            self.package_manager.close_package("closed" if self.mode != "error" else "error")

    def status(self) -> MetadataRuntimeStatus:
        values = sorted(self._latencies)
        p95 = values[min(len(values) - 1, int(round((len(values) - 1) * 0.95)))] if values else 0.0
        return MetadataRuntimeStatus(
            enabled=self.enabled,
            mode=self.mode,
            queue_depth=self._queue.qsize(),
            queue_capacity=self.queue_capacity,
            commit_p95_ms=float(p95),
            records_written=self.records_written,
            records_dropped=self.records_dropped,
            last_error=self.last_error,
            recording_id=self.package_manager.recording_id,
            current_output_path=str(self.package_manager.paths.metadata),
            package_id=self.package_manager.package_id,
            package_path=str(self.package_manager.paths.root),
            raw_runtime_object_rejected_count=self.raw_runtime_object_rejected_count,
            shutdown_unflushed_count=self.shutdown_unflushed_count,
        )
