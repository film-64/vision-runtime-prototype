from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import queue
import threading
import time
from typing import Any

from dynamic_pipeline.core.durable_metadata import LocalSchedulerEvent, PortableMetadataEvent
from dynamic_pipeline.core.metadata_normalizer import POSE_SIDECAR_PAYLOAD_KEY
from dynamic_pipeline.core.metadata_jsonl import MetadataJsonlWriter
from roi_app.metadata_package_manager import MetadataPackageManager


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
    scheduler_event_rejected_count: int = 0
    shutdown_unflushed_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MetadataCommitter:
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
        self.enabled = bool(enabled) and bool(package_manager.is_enabled_for_landing())
        self.queue_capacity = max(1, int(queue_capacity or 1))
        self.flush_records = max(1, int(flush_records or 32))
        self.flush_interval_ms = max(1, int(flush_interval_ms or 1000))
        self.metrics = metrics
        self.mode = "disabled" if not self.enabled else "open"
        self.records_dropped = 0
        self.last_error: str | None = None
        self.raw_runtime_object_rejected_count = 0
        self.scheduler_event_rejected_count = 0
        self.shutdown_unflushed_count = 0
        self._latencies: list[float] = []
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=self.queue_capacity)
        self._stop = threading.Event()
        self._writer: MetadataJsonlWriter | None = None
        self._thread: threading.Thread | None = None
        if self.enabled:
            self.package_manager.ensure_open()
            self._writer = MetadataJsonlWriter(self.package_manager.paths.metadata)
            self._thread = threading.Thread(target=self._run, name="metadata-committer", daemon=True)
            self._thread.start()
        self._publish_status_metrics()

    @property
    def records_written(self) -> int:
        return int(getattr(self._writer, "records_written", 0) or 0)

    def submit(self, event: PortableMetadataEvent) -> bool:
        if not self.enabled:
            return False
        if not isinstance(event, PortableMetadataEvent):
            if isinstance(event, LocalSchedulerEvent):
                self.scheduler_event_rejected_count += 1
                self._inc("metadata_scheduler_field_rejected_count")
            else:
                self.raw_runtime_object_rejected_count += 1
                self._inc("metadata_raw_runtime_object_rejected_count")
            return False
        try:
            self._queue.put_nowait(event)
            self._gauge("metadata_queue_depth", self._queue.qsize())
            return True
        except queue.Full:
            self.records_dropped += 1
            self._inc("metadata_records_dropped")
            self._publish_status_metrics()
            return False

    def _run(self) -> None:
        last_flush = time.monotonic()
        pending_since_flush = 0
        while not self._stop.is_set() or not self._queue.empty():
            try:
                event = self._queue.get(timeout=0.05)
            except queue.Empty:
                if self._writer is not None and pending_since_flush and self._should_flush(last_flush, pending_since_flush):
                    self._flush()
                    pending_since_flush = 0
                    last_flush = time.monotonic()
                continue
            start = time.perf_counter()
            try:
                if self._writer is not None:
                    event_to_write = self.prepare_event_for_write(event)
                    self._writer.write(event_to_write)
                    self.package_manager.ref_writer().append_event_refs(event_to_write)
                    self.package_manager.append_indexes_for_event(event_to_write)
                    self.package_manager.write_writer_checkpoint(event_to_write)
                    pending_since_flush += 1
                    self._inc("metadata_records_written")
                    if self._should_flush(last_flush, pending_since_flush):
                        self._flush()
                        pending_since_flush = 0
                        last_flush = time.monotonic()
            except Exception as exc:  # metadata must fail soft
                self.mode = "error"
                self.last_error = str(exc)
                self._inc("metadata_writer_error_count")
                self._publish_status_metrics()
            finally:
                self._latencies.append((time.perf_counter() - start) * 1000.0)
                self._queue.task_done()
                self._gauge("metadata_queue_depth", self._queue.qsize())
        if self._writer is not None:
            self._flush()
            self._writer.close()

    def _should_flush(self, last_flush: float, pending_since_flush: int) -> bool:
        return pending_since_flush >= self.flush_records or (time.monotonic() - last_flush) * 1000.0 >= self.flush_interval_ms

    def prepare_event_for_write(self, event: PortableMetadataEvent) -> PortableMetadataEvent:
        if event.record_type != "pose_observation":
            return event
        wrote_sidecar = self.package_manager.write_pose_sidecar_for_event(event)
        payload = dict(event.payload)
        payload.pop(POSE_SIDECAR_PAYLOAD_KEY, None)
        if wrote_sidecar:
            self._inc("metadata_pose_sidecar_written_count")
        return replace(event, payload=payload)

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
            self._inc("metadata_shutdown_unflushed_count", self.shutdown_unflushed_count)
            self.mode = "error"
            self.package_manager.mark_state("partial")
        else:
            self.package_manager.close_package("closed" if self.mode != "error" else "error")
        self._publish_status_metrics()

    def status(self) -> MetadataRuntimeStatus:
        return MetadataRuntimeStatus(
            enabled=self.enabled,
            mode=self.mode,
            queue_depth=self._queue.qsize(),
            queue_capacity=self.queue_capacity,
            commit_p95_ms=self._p95(),
            records_written=self.records_written,
            records_dropped=self.records_dropped,
            last_error=self.last_error,
            recording_id=self.package_manager.recording_id,
            current_output_path=str(self.package_manager.paths.metadata),
            package_id=self.package_manager.package_id,
            package_path=str(self.package_manager.paths.root),
            raw_runtime_object_rejected_count=self.raw_runtime_object_rejected_count,
            scheduler_event_rejected_count=self.scheduler_event_rejected_count,
            shutdown_unflushed_count=self.shutdown_unflushed_count,
        )

    def _p95(self) -> float:
        if not self._latencies:
            return 0.0
        values = sorted(self._latencies)
        index = min(len(values) - 1, int(round((len(values) - 1) * 0.95)))
        return float(values[index])

    def _inc(self, name: str, value: int = 1) -> None:
        if self.metrics is not None and hasattr(self.metrics, "inc"):
            self.metrics.inc(name, value)

    def _gauge(self, name: str, value: float) -> None:
        if self.metrics is not None and hasattr(self.metrics, "set_gauge"):
            self.metrics.set_gauge(name, value)

    def _publish_status_metrics(self) -> None:
        if self.metrics is None:
            return
        set_label = getattr(self.metrics, "set_label", None)
        if callable(set_label):
            set_label("metadata_runtime_mode", self.mode)
        self._gauge("metadata_queue_depth", self._queue.qsize())
        self._gauge("metadata_records_dropped", self.records_dropped)
        self._gauge("metadata_shutdown_unflushed", self.shutdown_unflushed_count)


class MetadataObservationPort:
    def __init__(self, committer: MetadataCommitter | None):
        self.committer = committer

    def submit_event(self, event: PortableMetadataEvent) -> bool:
        if self.committer is None:
            return False
        try:
            return self.committer.submit(event)
        except Exception:
            return False

    def submit_hook_ref(self, event: PortableMetadataEvent) -> bool:
        return self.submit_event(event)

    def submit_base_frame(self, _frame_context: Any) -> bool:
        return self._reject_raw()

    def submit_patch(self, _patch: Any, _task_context: Any = None) -> bool:
        return self._reject_raw()

    def status(self) -> MetadataRuntimeStatus | None:
        return self.committer.status() if self.committer is not None else None

    def _reject_raw(self) -> bool:
        if self.committer is not None:
            self.committer.raw_runtime_object_rejected_count += 1
        return False
