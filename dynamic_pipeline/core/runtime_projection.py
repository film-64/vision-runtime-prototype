from __future__ import annotations

from dataclasses import is_dataclass
from typing import Any

from .context import ArtifactPayload, FrameContext, ObjectContext
from .durable_metadata import HookRef, LocalSchedulerEvent, PortableMetadataEvent
from .metadata import MetadataPatch, bucket_to_verified_field
from .metadata_normalizer import (
    POSE_SIDECAR_PAYLOAD_KEY,
    box_values,
    frame_record_from_context,
    hook_ref_from_artifact,
    json_safe_value,
    object_record_from_context,
    pose_observation_from_context,
)
from .runtime_internal_fields import strip_runtime_internal_fields

PATCH_REF_KEYS = {"hook_ref_id", "public_artifact_ref", "sidecar_ref", "memory_ref", "source_ref", "patch_ref"}


def source_anchor_timeline(payload: dict[str, Any]) -> dict[str, Any]:
    timeline = {}
    for key in ("source_frame_index", "source_pts_ms", "sample_index"):
        value = payload.get(key)
        if value is not None:
            timeline[key] = value
    return timeline


class RuntimeProjectionBuilder:
    # Projection creates portable/local records from already-computed runtime
    # state. It must not schedule compute work or stand in for LaneAdmission.
    def __init__(self, recording_id: str):
        self.recording_id = str(recording_id)

    def project_frame(self, frame_context: FrameContext) -> PortableMetadataEvent:
        record = frame_record_from_context(frame_context, recording_id=self.recording_id)
        payload = record.to_payload()
        return PortableMetadataEvent.create(
            record_type="frame",
            event_type="frame.observed",
            recording_id=self.recording_id,
            source_id=record.source_id,
            frame_id=record.frame_id,
            timestamp_ms=record.timestamp_ms,
            producer="runtime_projection",
            payload=payload,
            timeline=source_anchor_timeline(payload),
            record_id=f"{self.recording_id}:frame:{record.source_id}:{record.frame_id}",
        )

    def project_object(self, object_context: ObjectContext, frame_context: FrameContext | None = None) -> PortableMetadataEvent:
        record = object_record_from_context(object_context, recording_id=self.recording_id)
        timestamp_ms = int(getattr(frame_context, "timestamp_ms", 0) or 0) if frame_context is not None else None
        return PortableMetadataEvent.create(
            record_type="object",
            event_type="object.observed",
            recording_id=self.recording_id,
            source_id=record.source_id,
            frame_id=record.frame_id,
            timestamp_ms=timestamp_ms,
            producer="runtime_projection",
            object_id=record.object_id,
            track_id=record.track_id,
            track_version=record.track_version,
            payload=record.to_payload(),
            refs={"object_ref": record.object_id, "track_ref": record.track_id},
            timeline={"parent_record_id": f"{self.recording_id}:frame:{record.source_id}:{record.frame_id}"},
            record_id=f"{self.recording_id}:object:{record.source_id}:{record.frame_id}:{record.object_id}",
        )

    def project_pose_observation(
        self,
        object_context: ObjectContext,
        frame_context: FrameContext | None = None,
    ) -> PortableMetadataEvent | None:
        # Pose observation is a side-channel export for later algorithms and
        # replay views; the heavy keypoint payload is referenced by sidecar.
        payload = pose_observation_from_context(object_context, frame_context)
        if payload is None:
            return None
        source_id = str(object_context.source_id)
        frame_id = int(object_context.frame_id)
        object_id = str(object_context.object_id)
        track_id = object_context.track_id
        timestamp_ms = int(getattr(frame_context, "timestamp_ms", 0) or 0) if frame_context is not None else None
        sidecar_ref = pose_sidecar_ref(source_id=source_id, frame_id=frame_id, object_id=object_id)
        refs = {
            "object_ref": object_id,
            "track_ref": track_id,
            "parent_object_record_id": f"{self.recording_id}:object:{source_id}:{frame_id}:{object_id}",
            "pose_sidecar_ref": sidecar_ref,
        }
        payload[POSE_SIDECAR_PAYLOAD_KEY]["pose_sidecar_ref"] = sidecar_ref
        return PortableMetadataEvent.create(
            record_type="pose_observation",
            event_type="pose.observation.summary",
            recording_id=self.recording_id,
            source_id=source_id,
            frame_id=frame_id,
            timestamp_ms=timestamp_ms,
            producer="runtime_projection",
            object_id=object_id,
            track_id=track_id,
            track_version=int(object_context.track_version or 0),
            payload=payload,
            refs=refs,
            timeline={
                "parent_record_id": refs["parent_object_record_id"],
                "pose_sidecar_ref": sidecar_ref,
            },
            record_id=f"{self.recording_id}:pose:{source_id}:{frame_id}:{object_id}",
        )

    def project_patch(self, patch: MetadataPatch, task_context: Any | None = None) -> PortableMetadataEvent | None:
        summary = portable_patch_summary(patch)
        if not summary:
            return None
        refs = portable_refs_from_value(remove_scheduler_fields(patch.patch))
        object_id = str(patch.object_id)
        timestamp_ms = int(patch.created_at_ms or 0)
        return PortableMetadataEvent.create(
            record_type="metadata_patch",
            event_type="specialist.patch.accepted",
            recording_id=self.recording_id,
            source_id=str(patch.source_id),
            frame_id=int(patch.frame_id),
            timestamp_ms=timestamp_ms,
            producer=str(patch.producer),
            object_id=object_id,
            track_id=patch.track_id,
            track_version=int(getattr(task_context, "track_version", 0) or 0),
            payload={
                "patch_id": patch.patch_id,
                "bucket": patch.bucket,
                "producer": patch.producer,
                "accepted_at_ms": timestamp_ms,
                **summary,
            },
            refs={"patch_ref": patch.patch_id, **refs},
            timeline={
                "parent_record_id": f"{self.recording_id}:object:{patch.source_id}:{patch.frame_id}:{object_id}",
                "source_event_id": patch.patch_id,
            },
            record_id=f"{self.recording_id}:patch:{patch.patch_id}",
        )

    def project_hook_ref(self, hook_ref: HookRef) -> PortableMetadataEvent:
        return PortableMetadataEvent.create(
            record_type="hook_ref",
            event_type="hook_ref.updated",
            recording_id=self.recording_id,
            source_id=hook_ref.source_id,
            frame_id=hook_ref.frame_id,
            timestamp_ms=hook_ref.created_at_ms,
            producer=hook_ref.producer,
            object_id=hook_ref.object_id,
            track_id=hook_ref.track_id,
            payload=hook_ref.to_payload(),
            refs={"hook_ref_id": hook_ref.hook_ref_id, **portable_refs_from_value(hook_ref.summary)},
            timeline={"source_event_id": hook_ref.hook_ref_id},
            record_id=f"{self.recording_id}:hook_ref:{hook_ref.hook_ref_id}",
        )

    def project_artifact_hook_ref(
        self,
        artifact: ArtifactPayload,
        *,
        source_id: str,
        frame_id: int | None = None,
        status: str = "unresolved",
        uri: str | None = None,
    ) -> PortableMetadataEvent:
        return self.project_hook_ref(
            hook_ref_from_artifact(
                artifact,
                recording_id=self.recording_id,
                source_id=source_id,
                frame_id=frame_id,
                status=status,
                uri=uri,
            )
        )

    def project_scheduler(self, task: Any, decision_or_trace: Any | None = None) -> LocalSchedulerEvent:
        local_payload = local_scheduler_safe_value(
            {
                "task": getattr(task, "trace_refs", None) or getattr(task, "metadata", {}) or {},
                "decision_or_trace": getattr(decision_or_trace, "refs", decision_or_trace),
            },
            path="local_scheduler",
        )
        return LocalSchedulerEvent(
            event_id=str(getattr(task, "trace_id", None) or getattr(task, "task_id", "") or "local_scheduler_event"),
            task_id=getattr(task, "task_id", None),
            trace_id=getattr(task, "trace_id", None),
            bucket=getattr(task, "bucket_hint", None) or getattr(task, "bucket", None),
            track_id=getattr(task, "source_track_id", None) or getattr(task, "track_id", None),
            artifact_ref=(getattr(task, "metadata", {}) or {}).get("artifact_ref") if getattr(task, "metadata", None) else None,
            local_payload=local_payload,
        )


def remove_scheduler_fields(value: Any) -> Any:
    return strip_runtime_internal_fields(value)


def pose_sidecar_ref(*, source_id: str, frame_id: int, object_id: str) -> str:
    return f"sidecars/pose/{safe_ref_part(source_id)}/frame_{int(frame_id)}/object_{safe_ref_part(object_id)}.json"


def safe_ref_part(value: object) -> str:
    text = str(value or "").strip()
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text)
    return safe or "unknown"


def portable_patch_summary(patch: MetadataPatch) -> dict[str, Any]:
    cleaned = remove_scheduler_fields(patch.patch)
    verified = cleaned.get("verified") if isinstance(cleaned, dict) else None
    field_name = bucket_to_verified_field(patch.bucket)
    field_value = verified.get(field_name) if isinstance(verified, dict) else None
    if not isinstance(field_value, dict):
        return {}
    status = field_value.get("status")
    if status in {"stale", "rejected", "cancelled", "cancelled_before_run"}:
        return {}
    attributes = field_value.get("attributes") if isinstance(field_value.get("attributes"), dict) else {}
    summary = bucket_specific_summary(patch.bucket, field_value, attributes)
    payload = {
        "status": json_safe_value(status, path="patch.status"),
        "label": json_safe_value(field_value.get("label"), path="patch.label"),
        "score": json_safe_value(field_value.get("score"), path="patch.score"),
        "summary": summary,
        "verified_summary": {
            field_name: {
                "status": json_safe_value(status, path="verified.status"),
                "label": json_safe_value(field_value.get("label"), path="verified.label"),
                "score": json_safe_value(field_value.get("score"), path="verified.score"),
            }
        },
    }
    for key in PATCH_REF_KEYS:
        if key in attributes:
            payload[key] = json_safe_value(attributes[key], path=f"patch.{key}")
    return payload


def bucket_specific_summary(bucket: str, field_value: dict[str, Any], attributes: dict[str, Any]) -> dict[str, Any]:
    base = {
        "bucket": bucket,
        "status": json_safe_value(field_value.get("status"), path="summary.status"),
        "label": json_safe_value(field_value.get("label"), path="summary.label"),
        "score": json_safe_value(field_value.get("score"), path="summary.score"),
    }
    if bucket == "identity":
        for key in ("nickname", "identity_nickname"):
            if key in attributes:
                base["nickname"] = json_safe_value(attributes[key], path="identity.nickname")
                break
    elif bucket == "age":
        for key in ("age_range", "range"):
            if key in attributes:
                base["range"] = json_safe_value(attributes[key], path="age.range")
                break
    elif bucket == "expression":
        base.update(portable_refs_from_value(attributes))
    elif bucket == "face_roi":
        if "face_count" in attributes:
            base["face_count"] = json_safe_value(attributes["face_count"], path="face_roi.face_count")
        for key in ("face_bbox_local", "raw_face_bbox_local"):
            if key in attributes:
                base[key] = box_values(attributes[key])
        base.update(portable_refs_from_value(attributes))
    return json_safe_value(remove_scheduler_fields(base), path=f"{bucket}.summary")


def portable_refs_from_value(value: Any) -> dict[str, Any]:
    refs: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if key_text in PATCH_REF_KEYS and item is not None:
                refs[key_text] = json_safe_value(item, path=f"refs.{key_text}")
            else:
                refs.update(portable_refs_from_value(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            refs.update(portable_refs_from_value(item))
    return refs


def local_scheduler_safe_value(value: Any, *, path: str = "value") -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return {"omitted": True, "reason": "bytes_payload", "len": len(value)}
    if is_dataclass(value):
        return {"omitted": True, "reason": "runtime_object", "type": type(value).__name__}
    if isinstance(value, dict):
        return {str(key): local_scheduler_safe_value(item, path=f"{path}.{key}") for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        if len(items) > 64:
            return {"omitted": True, "reason": "list_too_large", "len": len(items)}
        return [local_scheduler_safe_value(item, path=f"{path}[]") for item in items]
    return {"omitted": True, "reason": "non_json_value", "type": type(value).__name__}
