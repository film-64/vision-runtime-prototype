from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .context import now_ms, new_id


@dataclass
class MetadataPatch:
    producer: str
    bucket: str
    frame_id: int
    source_id: str
    object_id: str
    patch: dict[str, Any]
    track_id: str | None = None
    base_version: int = 0
    patch_id: str = field(default_factory=lambda: new_id("patch"))
    created_at_ms: int = field(default_factory=now_ms)
    ttl_ms: int = 500

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def specialist_result_to_patch(result, task_context, *, ttl_ms: int = 500) -> MetadataPatch:
    bucket = getattr(task_context, "bucket", getattr(result, "specialist", "unknown"))
    status = getattr(result, "status", "unknown")
    label = getattr(result, "label", "unknown")
    score = float(getattr(result, "score", 0.0) or 0.0)
    field_name = bucket_to_verified_field(bucket)
    return MetadataPatch(
        producer=getattr(result, "specialist", bucket),
        bucket=bucket,
        frame_id=task_context.frame_id,
        source_id=task_context.source_id,
        object_id=task_context.object_id,
        track_id=task_context.track_id,
        base_version=getattr(task_context.object_snapshot, "version", 0) if task_context.object_snapshot else 0,
        ttl_ms=ttl_ms,
        patch={
            "verified": {
                field_name: {
                    "status": status,
                    "label": label if status == "matched" else None,
                    "score": score,
                    "producer": getattr(result, "specialist", bucket),
                    "attributes": getattr(result, "attributes", {}) or {},
                }
            },
            "runtime": {
                "completed_buckets": [bucket],
            },
        },
    )


def bucket_to_verified_field(bucket: str) -> str:
    if bucket in {"identity", "face"}:
        return "identity"
    if bucket in {"closed_class", "closed_class_verify"}:
        return "closed_class"
    return bucket
