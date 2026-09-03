from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .context import now_ms

SCHEMA_VERSION = "durable_metadata.v1"


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
        record_id: str,
    ) -> "PortableMetadataEvent":
        base_timeline = {
            "record_id": record_id,
            "recording_id": str(recording_id),
            "source_id": str(source_id),
            "frame_id": frame_id,
            "timestamp_ms": timestamp_ms,
        }
        base_timeline.update(timeline or {})
        return cls(
            schema_version=SCHEMA_VERSION,
            record_type=str(record_type),
            record_id=str(record_id),
            recording_id=str(recording_id),
            source_id=str(source_id),
            frame_id=int(frame_id) if frame_id is not None else None,
            timestamp_ms=int(timestamp_ms) if timestamp_ms is not None else None,
            emitted_at_ms=now_ms(),
            event_type=str(event_type),
            producer=str(producer),
            object_id=object_id,
            track_id=track_id,
            track_version=int(track_version or 0),
            payload=dict(payload or {}),
            refs=dict(refs or {}),
            timeline=base_timeline,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
