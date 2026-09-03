from __future__ import annotations

from dataclasses import asdict, dataclass, field
import time
import uuid
from typing import Any


def now_ms() -> int:
    return int(time.time() * 1000)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class BoxSet:
    frame_xyxy: list[float]
    model_input_xyxy: list[float] | None = None
    roi_local_xyxy: list[float] | None = None
    screen_xyxy: list[float] | None = None
    display_norm_xyxy: list[float] | None = None
    detector_xyxy: list[float] | None = None
    track_xyxy: list[float] | None = None
    display_xyxy: list[float] | None = None

    @classmethod
    def from_frame_box(
        cls,
        frame_xyxy: list[float],
        frame_size: tuple[int, int],
        *,
        screen_xyxy: list[float] | None = None,
        roi_local_xyxy: list[float] | None = None,
        model_input_xyxy: list[float] | None = None,
    ) -> "BoxSet":
        return cls(
            frame_xyxy=[float(value) for value in frame_xyxy],
            model_input_xyxy=model_input_xyxy,
            roi_local_xyxy=roi_local_xyxy,
            screen_xyxy=screen_xyxy,
            display_norm_xyxy=normalize_box(frame_xyxy, frame_size),
            detector_xyxy=list(screen_xyxy) if screen_xyxy else [float(value) for value in frame_xyxy],
            track_xyxy=list(screen_xyxy) if screen_xyxy else None,
            display_xyxy=list(screen_xyxy) if screen_xyxy else None,
        )


@dataclass
class FrameContext:
    frame_id: int
    source_id: str
    timestamp_ms: int
    frame_width: int
    frame_height: int
    prompt_version: int = 0
    orientation: int = 0
    mirrored: bool = False
    pixel_format: str | None = None
    coordinate_origin: str = "top_left"
    coordinate_order: str = "xyxy"
    platform: dict[str, Any] = field(default_factory=dict)
    objects: list["ObjectContext"] = field(default_factory=list)
    detector_index: int = 0
    source_frame_index: int | None = None
    source_pts_ms: float | None = None
    sample_index: int | None = None

    @property
    def frame_size(self) -> tuple[int, int]:
        return self.frame_width, self.frame_height

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RawCandidate:
    producer: str
    class_name: str
    confidence: float
    prompt_names: list[str] = field(default_factory=list)
    hit_count: int = 1
    prompt_count: int = 0
    hit_ratio: float = 0.0
    box_count: int = 1
    prompt_version: int = 0
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationField:
    status: str = "not_run"
    label: str | None = None
    score: float | None = None
    producer: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerifiedState:
    identity: VerificationField = field(default_factory=VerificationField)
    age: VerificationField = field(default_factory=VerificationField)
    expression: VerificationField = field(default_factory=VerificationField)
    color: VerificationField = field(default_factory=VerificationField)
    clothing_attribute: VerificationField = field(default_factory=VerificationField)
    closed_class: VerificationField = field(default_factory=VerificationField)
    ocr: VerificationField = field(default_factory=VerificationField)
    pose: VerificationField = field(default_factory=VerificationField)
    hand: VerificationField = field(default_factory=VerificationField)
    pet: VerificationField = field(default_factory=VerificationField)


@dataclass
class DisplayObject:
    label: str
    score: float
    state: str = "raw"
    osd_ready: bool = True
    secondary_lines: list[str] = field(default_factory=list)
    visible_box_xyxy: list[float] | None = None


@dataclass
class RuntimeState:
    route_buckets: list[str] = field(default_factory=list)
    pending_buckets: list[str] = field(default_factory=list)
    completed_buckets: list[str] = field(default_factory=list)
    stale_buckets: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    attention_dag_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    ocr_display_regions: list[dict[str, Any]] = field(default_factory=list)
    source_row: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionTask:
    """Unified scheduler-facing task contract.

    This is the stable contract #9 needs before RegionTask and TaskContext can
    be fully collapsed. Existing call sites may still use adapters, but these
    fields are the single semantic surface for admission, scheduling, execution,
    stale checks, and trace stitching.
    """

    task_id: str
    bucket: str
    source: str
    frame_id: int | None = None
    source_id: str | None = None
    object_id: str | None = None
    track_id: str | None = None
    source_track_id: str | None = None
    source_detector_index: int = 0
    deadline_detector_index: int = 0
    priority: int = 0
    utility_score: float = 0.0
    estimated_cost_intervals: int = 1
    state_generation: int = 0
    dependencies: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()
    dispatch_policy: str = "bucketed"
    trace_id: str | None = None
    trace_refs: dict[str, Any] = field(default_factory=dict)
    metadata_refs: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_task_context(cls, task_context: "TaskContext") -> "ExecutionTask":
        return cls(
            task_id=task_context.task_id,
            bucket=task_context.bucket,
            source=str(task_context.metadata.get("source", "task_context")),
            frame_id=task_context.frame_id,
            source_id=task_context.source_id,
            object_id=task_context.object_id,
            track_id=task_context.track_id,
            source_track_id=task_context.source_track_id,
            source_detector_index=int(task_context.source_detector_index or 0),
            deadline_detector_index=int(task_context.deadline_detector_index or 0),
            priority=int(task_context.priority or 0),
            utility_score=float(task_context.utility_score or 0.0),
            estimated_cost_intervals=int(task_context.estimated_cost_intervals or 1),
            state_generation=int(task_context.state_generation or 0),
            dependencies=tuple(task_context.requires),
            produces=tuple(task_context.produces),
            dispatch_policy=task_context.dispatch_policy,
            trace_id=task_context.trace_id,
            trace_refs=trace_ref_values(task_context.metadata),
            metadata_refs=trace_metadata_refs(
                task_context.metadata,
                source_id=task_context.source_id,
                frame_id=task_context.frame_id,
                object_id=task_context.object_id,
                track_id=task_context.track_id,
                source_track_id=task_context.source_track_id,
            ),
        )

    @classmethod
    def from_region_task(cls, task: Any) -> "ExecutionTask":
        metadata = getattr(task, "metadata", {}) or {}
        return cls(
            task_id=str(getattr(task, "task_id", "")),
            bucket=str(getattr(task, "bucket_hint", "") or metadata.get("bucket") or "scheduler"),
            source=str(getattr(task, "source", "") or metadata.get("source") or "region_task"),
            frame_id=int(metadata["frame_id"]) if metadata.get("frame_id") is not None else None,
            source_id=metadata.get("source_id"),
            object_id=metadata.get("object_id"),
            track_id=metadata.get("track_id"),
            source_track_id=getattr(task, "source_track_id", None),
            source_detector_index=int(getattr(task, "source_detector_index", 0) or 0),
            deadline_detector_index=int(getattr(task, "deadline_detector_index", 0) or 0),
            priority=int(getattr(task, "priority", 0) or 0),
            utility_score=float(getattr(task, "utility_score", 0.0) or 0.0),
            estimated_cost_intervals=int(getattr(task, "estimated_cost_intervals", 1) or 1),
            state_generation=int(getattr(task, "state_generation", 0) or getattr(task, "generation", 0) or 0),
            dependencies=tuple(metadata.get("requires", ())),
            produces=tuple(metadata.get("produces", ())),
            dispatch_policy=str(getattr(task, "dispatch_policy", "bucketed") or "bucketed"),
            trace_id=metadata.get("trace_id") or getattr(task, "trace_id", None),
            trace_refs=dict(getattr(task, "trace_refs", {}) or {}),
            metadata_refs=trace_metadata_refs(
                metadata,
                source_id=metadata.get("source_id"),
                frame_id=metadata.get("frame_id"),
                object_id=metadata.get("object_id"),
                track_id=metadata.get("track_id"),
                source_track_id=getattr(task, "source_track_id", None),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


TRACE_REF_KEYS = {
    "artifact_name",
    "artifact_ref",
    "artifact_source",
    "age_label",
    "age_score",
    "age_status",
    "bucket",
    "backend_capability_requirement",
    "backend_profile",
    "concurrency_key",
    "concurrency_scope",
    "crop_ref",
    "crop_sha1",
    "detector_index",
    "downstream_effect",
    "execution_lane",
    "execution_mode",
    "expression_label",
    "expression_score",
    "expression_status",
    "frame_id",
    "identity_label",
    "identity_nickname",
    "identity_score",
    "identity_status",
    "input_box_source",
    "latency_aggregator_ms",
    "latency_queue_wait_ms",
    "latency_run_ms",
    "latency_total_since_created_ms",
    "lane_queue_completed",
    "lane_queue_inflight",
    "lane_queue_rejected_concurrency_key",
    "lane_queue_rejected_duplicate",
    "lane_queue_submitted",
    "lane_queue_waiting",
    "memory_label",
    "memory_score",
    "memory_source",
    "memory_status",
    "merge_policy",
    "object_id",
    "produces",
    "queue_topology",
    "queue_lane",
    "requires",
    "route_buckets",
    "runtime_object_key",
    "sample_names",
    "schedule_phase",
    "schedule_frequency",
    "scheduler_lane",
    "serial_merge_complete",
    "serial_merge_enter",
    "source_id",
    "source_kind",
    "source_track_id",
    "specialist",
    "specialist_label",
    "specialist_score",
    "specialist_status",
    "trace_id",
    "track_id",
    "track_version",
    "upstream_trigger",
    "worker_id",
    "worker_lane",
}

TRACE_REF_SUFFIXES = (
    "_bytes",
    "_count",
    "_dim",
    "_dims",
    "_height",
    "_mode",
    "_ms",
    "_nbytes",
    "_shape",
    "_size",
    "_source",
    "_width",
)


ADMISSION_TRACE_REF_KEYS = {
    "admission_decision",
    "admission_decision_id",
    "admission_override_reason",
    "decision",
    "decision_id",
}


def trace_ref_values(metadata: dict[str, Any]) -> dict[str, Any]:
    refs = metadata.get("trace_refs") if isinstance(metadata, dict) else {}
    output = dict(refs) if isinstance(refs, dict) else {}
    if isinstance(metadata, dict):
        for key in ADMISSION_TRACE_REF_KEYS:
            if key in metadata:
                output[key] = metadata[key]
    return output


def trace_metadata_refs(metadata: dict[str, Any], **fallbacks: Any) -> dict[str, Any]:
    refs = {}
    for key, value in fallbacks.items():
        if value is not None:
            refs[key] = value
    for key, value in (metadata or {}).items():
        if key in TRACE_REF_KEYS or key.endswith("_ref") or key.endswith("_id") or key.endswith(TRACE_REF_SUFFIXES):
            refs[key] = value
    return refs


@dataclass(frozen=True)
class TaskTraceEvent:
    trace_id: str
    task_id: str
    bucket: str
    phase: str
    reason: str = ""
    timestamp_ms: int = field(default_factory=now_ms)
    source_detector_index: int = 0
    deadline_detector_index: int = 0
    priority: int = 0
    utility_score: float = 0.0
    estimated_cost_intervals: int = 1
    effective_score: float = 0.0
    state_generation: int = 0
    refs: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_execution_task(
        cls,
        task: ExecutionTask,
        *,
        phase: str,
        reason: str = "",
        effective_score: float = 0.0,
    ) -> "TaskTraceEvent":
        return cls(
            trace_id=task.trace_id or task.task_id,
            task_id=task.task_id,
            bucket=task.bucket,
            phase=phase,
            reason=reason,
            source_detector_index=task.source_detector_index,
            deadline_detector_index=task.deadline_detector_index,
            priority=task.priority,
            utility_score=task.utility_score,
            estimated_cost_intervals=task.estimated_cost_intervals,
            effective_score=float(effective_score or 0.0),
            state_generation=task.state_generation,
            refs=dict(task.metadata_refs),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TaskTraceStore:
    def __init__(self, enabled: bool = False, max_events: int = 4096, writer: Any | None = None):
        self.enabled = bool(enabled)
        self.max_events = max(1, int(max_events or 1))
        self.events: list[TaskTraceEvent] = []
        self.writer = writer

    def record(self, event: TaskTraceEvent) -> None:
        if not self.enabled:
            return
        self.events.append(event)
        if len(self.events) > self.max_events:
            del self.events[: len(self.events) - self.max_events]
        if self.writer is not None:
            self.writer.write({"record_type": "task_trace", **event.to_dict()})

    def events_for(self, trace_id: str) -> list[TaskTraceEvent]:
        return [event for event in self.events if event.trace_id == trace_id]


@dataclass(frozen=True)
class ArtifactPayload:
    artifact_id: str
    name: str
    producer: str
    track_id: str | None = None
    object_id: str | None = None
    created_at_detector_index: int = 0
    image: Any | None = None
    display_image: Any | None = None
    embedding: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_result(
        cls,
        result: Any,
        *,
        producer_config: Any,
        object_context: Any,
        detector_index: int,
    ) -> "ArtifactPayload":
        attrs = dict(getattr(result, "attributes", {}) or {})
        name = str(attrs.get("artifact_name") or getattr(producer_config, "name", "artifact") or "artifact")
        reserved = {"artifact_image", "artifact_display_image", "face_embedding"}
        return cls(
            artifact_id=str(attrs.get("artifact_id") or new_id(f"artifact_{name}")),
            name=name,
            producer=str(getattr(producer_config, "name", name) or name),
            track_id=str(getattr(object_context, "track_id", "") or "") or None,
            object_id=getattr(object_context, "object_id", None),
            created_at_detector_index=int(detector_index or 0),
            image=attrs.get("artifact_image"),
            display_image=attrs.get("artifact_display_image"),
            embedding=attrs.get("face_embedding"),
            metadata={key: value for key, value in attrs.items() if key not in reserved},
        )

    def ref(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_name": self.name,
            "artifact_producer": self.producer,
            "track_id": self.track_id,
            "object_id": self.object_id,
            "created_at_detector_index": self.created_at_detector_index,
        }


@dataclass
class ObjectContext:
    object_id: str
    frame_id: int
    source_id: str
    frame_size: tuple[int, int]
    boxes: BoxSet
    raw_candidate: RawCandidate
    verified: VerifiedState = field(default_factory=VerifiedState)
    display: DisplayObject | None = None
    runtime: RuntimeState = field(default_factory=RuntimeState)
    track_id: str | None = None
    source_track_id: str | None = None
    track_version: int = 0
    source_track_version: int = 0
    detector_index: int = 0
    source_detector_index: int = 0
    deadline_detector_index: int = 0
    visible: bool = True
    parent: dict[str, Any] | None = None
    version: int = 0

    def __post_init__(self):
        if self.display is None:
            label = self.raw_candidate.prompt_names[0] if self.raw_candidate.prompt_names else self.raw_candidate.class_name
            self.display = DisplayObject(label=label, score=float(self.raw_candidate.confidence), state="raw")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskContext:
    task_id: str
    frame_id: int
    source_id: str
    object_id: str
    bucket: str
    priority: int
    deadline_ms: int
    created_at_ms: int
    stale_after_ms: int
    dispatch_policy: str
    track_id: str | None = None
    source_track_id: str | None = None
    source_track_version: int = 0
    source_detector_index: int = 0
    deadline_detector_index: int = 0
    source_bbox: list[float] | None = None
    estimated_cost_intervals: int = 1
    utility_score: float = 0.0
    state_generation: int = 0
    trace_id: str | None = None
    status: str = "pending"
    drop_reason: str | None = None
    requires: list[str] = field(default_factory=list)
    produces: list[str] = field(default_factory=list)
    object_snapshot: ObjectContext | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_execution_task(self) -> ExecutionTask:
        return ExecutionTask.from_task_context(self)


def normalize_box(box: list[float], frame_size: tuple[int, int]) -> list[float]:
    width, height = frame_size
    if width <= 0 or height <= 0:
        return [0.0, 0.0, 0.0, 0.0]
    x1, y1, x2, y2 = [float(value) for value in box]
    return [
        clamp01(x1 / width),
        clamp01(y1 / height),
        clamp01(x2 / width),
        clamp01(y2 / height),
    ]


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def validate_box_xyxy(box: list[float], frame_size: tuple[int, int]) -> None:
    if len(box) != 4:
        raise ValueError(f"xyxy box must have 4 values, got {len(box)}")
    width, height = frame_size
    if width <= 0 or height <= 0:
        raise ValueError(f"frame size must be positive, got {frame_size}")
    x1, y1, x2, y2 = [float(value) for value in box]
    if x2 < x1 or y2 < y1:
        raise ValueError(f"invalid xyxy order: {box}")
