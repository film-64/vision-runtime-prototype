from __future__ import annotations

from typing import Any

from .context import FrameContext, ObjectContext, VerificationField
from .durable_metadata import PortableMetadataEvent
from .metadata import MetadataPatch, bucket_to_verified_field

PORTABLE_REF_KEYS = {"hook_ref_id", "public_artifact_ref", "sidecar_ref", "memory_ref", "source_ref", "patch_ref"}


class RuntimeProjectionBuilder:
    """Project selected runtime state into the durable public metadata contract.

    The projection is deliberately allowlist-based: scheduler/resource/debug
    state is not serialized unless a durable field explicitly names it.
    """

    def __init__(self, recording_id: str):
        self.recording_id = str(recording_id)

    def project_frame(self, frame: FrameContext) -> PortableMetadataEvent:
        payload = {
            "recording_id": self.recording_id,
            "source_id": str(frame.source_id),
            "frame_id": int(frame.frame_id),
            "timestamp_ms": int(frame.timestamp_ms),
            "detector_index": int(frame.detector_index or 0),
            "frame_width": int(frame.frame_width),
            "frame_height": int(frame.frame_height),
            "object_count": len(frame.objects),
            "source_kind": "runtime",
            "prompt_version": int(frame.prompt_version or 0),
            "source_frame_index": frame.source_frame_index,
            "source_pts_ms": frame.source_pts_ms,
            "sample_index": frame.sample_index,
        }
        return PortableMetadataEvent.create(
            record_type="frame",
            event_type="frame.observed",
            recording_id=self.recording_id,
            source_id=frame.source_id,
            frame_id=frame.frame_id,
            timestamp_ms=frame.timestamp_ms,
            producer="runtime_projection",
            payload=payload,
            timeline={
                key: value
                for key, value in (
                    ("source_frame_index", frame.source_frame_index),
                    ("source_pts_ms", frame.source_pts_ms),
                    ("sample_index", frame.sample_index),
                )
                if value is not None
            },
            record_id=f"{self.recording_id}:frame:{frame.source_id}:{frame.frame_id}",
        )

    def project_object(self, obj: ObjectContext, frame: FrameContext | None = None) -> PortableMetadataEvent:
        raw = obj.raw_candidate
        payload = {
            "recording_id": self.recording_id,
            "source_id": str(obj.source_id),
            "frame_id": int(obj.frame_id),
            "object_id": str(obj.object_id),
            "track_id": obj.track_id,
            "track_version": int(obj.track_version or 0),
            "class_name": str(raw.class_name or ""),
            "confidence": float(raw.confidence or 0.0),
            "bbox_frame_xyxy": [float(v) for v in obj.boxes.frame_xyxy],
            "bbox_screen_xyxy": [float(v) for v in obj.boxes.screen_xyxy] if obj.boxes.screen_xyxy else None,
            "display_label": obj.display.label if obj.display else None,
            "display_score": float(obj.display.score) if obj.display else None,
            "verified_summary": _verified_summary(obj),
        }
        return PortableMetadataEvent.create(
            record_type="object",
            event_type="object.observed",
            recording_id=self.recording_id,
            source_id=obj.source_id,
            frame_id=obj.frame_id,
            timestamp_ms=frame.timestamp_ms if frame is not None else None,
            producer="runtime_projection",
            object_id=obj.object_id,
            track_id=obj.track_id,
            track_version=obj.track_version,
            payload=payload,
            refs={"object_ref": obj.object_id, "track_ref": obj.track_id},
            timeline={"parent_record_id": f"{self.recording_id}:frame:{obj.source_id}:{obj.frame_id}"},
            record_id=f"{self.recording_id}:object:{obj.source_id}:{obj.frame_id}:{obj.object_id}",
        )

    def project_patch(self, patch: MetadataPatch) -> PortableMetadataEvent | None:
        field_name = bucket_to_verified_field(patch.bucket)
        verified = patch.patch.get("verified") if isinstance(patch.patch, dict) else None
        field_value = verified.get(field_name) if isinstance(verified, dict) else None
        if not isinstance(field_value, dict):
            return None
        status = field_value.get("status")
        if status in {"stale", "rejected", "cancelled", "cancelled_before_run"}:
            return None
        attributes = field_value.get("attributes") if isinstance(field_value.get("attributes"), dict) else {}
        refs = _portable_refs(attributes)
        payload = {
            "patch_id": patch.patch_id,
            "bucket": patch.bucket,
            "producer": patch.producer,
            "accepted_at_ms": int(patch.created_at_ms or 0),
            "status": status,
            "label": field_value.get("label"),
            "score": field_value.get("score"),
            "summary": {
                "bucket": patch.bucket,
                "status": status,
                "label": field_value.get("label"),
                "score": field_value.get("score"),
            },
            "verified_summary": {
                field_name: {
                    "status": status,
                    "label": field_value.get("label"),
                    "score": field_value.get("score"),
                    "producer": patch.producer,
                }
            },
            **refs,
        }
        return PortableMetadataEvent.create(
            record_type="metadata_patch",
            event_type="specialist.patch.accepted",
            recording_id=self.recording_id,
            source_id=patch.source_id,
            frame_id=patch.frame_id,
            timestamp_ms=patch.created_at_ms,
            producer=patch.producer,
            object_id=patch.object_id,
            track_id=patch.track_id,
            payload=payload,
            refs={"patch_ref": patch.patch_id, **refs},
            timeline={
                "parent_record_id": f"{self.recording_id}:object:{patch.source_id}:{patch.frame_id}:{patch.object_id}",
                "source_event_id": patch.patch_id,
            },
            record_id=f"{self.recording_id}:patch:{patch.patch_id}",
        )


def _verified_summary(obj: ObjectContext) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for name, value in vars(obj.verified).items():
        if not isinstance(value, VerificationField) or value.status == "not_run":
            continue
        output[name] = {
            "status": value.status,
            "label": value.label,
            "score": value.score,
            "producer": value.producer,
        }
    return output


def _portable_refs(value: Any) -> dict[str, Any]:
    output: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in PORTABLE_REF_KEYS and item is not None:
                output[str(key)] = item
            else:
                output.update(_portable_refs(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            output.update(_portable_refs(item))
    return output
