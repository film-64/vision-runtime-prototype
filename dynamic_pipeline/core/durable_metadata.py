from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .context import new_id, now_ms


SCHEMA_VERSION = "durable_metadata.v1"
HOOK_REF_STATUSES = {"pending", "ready", "unresolved", "expired", "error"}


@dataclass(frozen=True)
class MetadataEnvelope:
    schema_version: str
    record_type: str
    record_id: str
    recording_id: str
    source_id: str
    frame_id: int | None
    timestamp_ms: int | None
    emitted_at_ms: int
    producer: str
    payload: dict[str, Any]

    @classmethod
    def wrap(
        cls,
        *,
        record_type: str,
        recording_id: str,
        source_id: str,
        frame_id: int | None,
        timestamp_ms: int | None,
        producer: str,
        payload: dict[str, Any],
        record_id: str | None = None,
    ) -> "MetadataEnvelope":
        return cls(
            schema_version=SCHEMA_VERSION,
            record_type=str(record_type),
            record_id=record_id or new_id(str(record_type).replace("-", "_")),
            recording_id=str(recording_id),
            source_id=str(source_id or ""),
            frame_id=int(frame_id) if frame_id is not None else None,
            timestamp_ms=int(timestamp_ms) if timestamp_ms is not None else None,
            emitted_at_ms=now_ms(),
            producer=str(producer or "runtime"),
            payload=dict(payload or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FrameRecord:
    recording_id: str
    source_id: str
    frame_id: int
    timestamp_ms: int
    detector_index: int
    frame_width: int
    frame_height: int
    object_count: int
    source_kind: str
    prompt_version: int
    source_frame_index: int | None = None
    source_pts_ms: float | None = None
    sample_index: int | None = None

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ObjectRecord:
    recording_id: str
    source_id: str
    frame_id: int
    object_id: str
    track_id: str | None
    track_version: int
    class_name: str
    confidence: float
    bbox_frame_xyxy: list[float]
    bbox_screen_xyxy: list[float] | None
    display_label: str | None
    display_score: float | None
    pose_keypoints: dict[str, list[float]] = field(default_factory=dict)
    mask_polygons: list[list[list[float]]] = field(default_factory=list)
    verified_summary: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HookRef:
    hook_ref_id: str
    recording_id: str
    source_id: str
    frame_id: int | None
    object_id: str | None
    track_id: str | None
    kind: str
    producer: str
    status: Literal["pending", "ready", "unresolved", "expired", "error"]
    summary: dict[str, Any] = field(default_factory=dict)
    uri: str | None = None
    created_at_ms: int = field(default_factory=now_ms)

    def __post_init__(self) -> None:
        if self.status not in HOOK_REF_STATUSES:
            raise ValueError(f"invalid HookRef status: {self.status}")

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MetadataPatchRecord:
    recording_id: str
    source_id: str
    frame_id: int
    object_id: str
    track_id: str | None
    patch_id: str
    bucket: str
    producer: str
    base_version: int
    ttl_ms: int
    patch_summary: dict[str, Any]
    created_at_ms: int

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PortableMetadataEvent:
    schema_version: str
    record_type: str
    record_id: str
    recording_id: str
    source_id: str
    frame_id: int | None
    timestamp_ms: int | None
    emitted_at_ms: int
    event_type: str
    producer: str
    object_id: str | None = None
    track_id: str | None = None
    track_version: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    refs: dict[str, Any] = field(default_factory=dict)
    timeline: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        record_type: str,
        event_type: str,
        recording_id: str,
        source_id: str,
        frame_id: int | None,
        timestamp_ms: int | None,
        producer: str,
        payload: dict[str, Any] | None = None,
        refs: dict[str, Any] | None = None,
        timeline: dict[str, Any] | None = None,
        object_id: str | None = None,
        track_id: str | None = None,
        track_version: int = 0,
        record_id: str | None = None,
    ) -> "PortableMetadataEvent":
        event_record_id = record_id or new_id(str(record_type).replace("-", "_"))
        event_timeline = {
            "record_id": event_record_id,
            "recording_id": str(recording_id),
            "source_id": str(source_id or ""),
            "frame_id": int(frame_id) if frame_id is not None else None,
            "timestamp_ms": int(timestamp_ms) if timestamp_ms is not None else None,
        }
        event_timeline.update(timeline or {})
        return cls(
            schema_version=SCHEMA_VERSION,
            record_type=str(record_type),
            record_id=event_record_id,
            recording_id=str(recording_id),
            source_id=str(source_id or ""),
            frame_id=int(frame_id) if frame_id is not None else None,
            timestamp_ms=int(timestamp_ms) if timestamp_ms is not None else None,
            emitted_at_ms=now_ms(),
            event_type=str(event_type),
            producer=str(producer or "runtime_projection"),
            object_id=object_id,
            track_id=track_id,
            track_version=int(track_version or 0),
            payload=dict(payload or {}),
            refs=dict(refs or {}),
            timeline=event_timeline,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LocalSchedulerEvent:
    event_id: str
    task_id: str | None
    trace_id: str | None
    bucket: str | None
    track_id: str | None
    artifact_ref: str | None = None
    local_payload: dict[str, Any] = field(default_factory=dict)
    timestamp_ms: int = field(default_factory=now_ms)

    def to_dict(self) -> dict[str, Any]:
        return {"record_type": "local_scheduler_event", **asdict(self)}
