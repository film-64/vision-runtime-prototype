from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from .context import ArtifactPayload, FrameContext, ObjectContext, VerificationField, new_id
from .durable_metadata import (
    MetadataEnvelope,
    FrameRecord,
    HookRef,
    MetadataPatchRecord,
    ObjectRecord,
)
from .metadata import MetadataPatch, bucket_to_verified_field
from .runtime_internal_fields import RUNTIME_INTERNAL_FIELDS


HEAVY_KEY_FRAGMENTS = (
    "embedding",
    "feature_vector",
    "image",
    "crop",
    "mask",
    "segmentation",
    "pose_sequence",
    "source_row",
    "raw_result",
    "debug_blob",
)
PORTABLE_REF_KEYS = {"hook_ref_id", "public_artifact_ref", "sidecar_ref", "memory_ref", "source_ref", "patch_ref"}
MAX_JSON_LIST_ITEMS = 32
MAX_JSON_DICT_ITEMS = 64
MAX_STRING_LENGTH = 512
COCO17_KEYPOINTS = tuple(range(17))
POSE_SIDECAR_PAYLOAD_KEY = "_pose_sidecar_payload"


def frame_record_from_context(frame_context: FrameContext, *, recording_id: str, source_kind: str = "runtime") -> FrameRecord:
    return FrameRecord(
        recording_id=str(recording_id),
        source_id=str(frame_context.source_id),
        frame_id=int(frame_context.frame_id),
        timestamp_ms=int(frame_context.timestamp_ms),
        detector_index=int(frame_context.detector_index or 0),
        frame_width=int(frame_context.frame_width or 0),
        frame_height=int(frame_context.frame_height or 0),
        object_count=len(frame_context.objects or []),
        source_kind=str(source_kind or "runtime"),
        prompt_version=int(frame_context.prompt_version or 0),
        source_frame_index=(
            int(frame_context.source_frame_index) if frame_context.source_frame_index is not None else None
        ),
        source_pts_ms=float(frame_context.source_pts_ms) if frame_context.source_pts_ms is not None else None,
        sample_index=int(frame_context.sample_index) if frame_context.sample_index is not None else None,
    )


def object_record_from_context(object_context: ObjectContext, *, recording_id: str) -> ObjectRecord:
    display = object_context.display
    raw = object_context.raw_candidate
    return ObjectRecord(
        recording_id=str(recording_id),
        source_id=str(object_context.source_id),
        frame_id=int(object_context.frame_id),
        object_id=str(object_context.object_id),
        track_id=object_context.track_id,
        track_version=int(object_context.track_version or 0),
        class_name=str(raw.class_name or ""),
        confidence=float(raw.confidence or 0.0),
        bbox_frame_xyxy=box_values(object_context.boxes.frame_xyxy),
        bbox_screen_xyxy=box_values(object_context.boxes.screen_xyxy),
        display_label=getattr(display, "label", None),
        display_score=float(display.score) if display is not None and display.score is not None else None,
        pose_keypoints=pose_keypoint_values(raw.attributes.get("pose_keypoints") if raw.attributes else None),
        mask_polygons=mask_polygon_values(raw.attributes.get("mask_polygons") if raw.attributes else None),
        verified_summary=verified_summary(object_context),
    )


def pose_observation_from_context(
    object_context: ObjectContext,
    frame_context: FrameContext | None = None,
) -> dict[str, Any] | None:
    raw = object_context.raw_candidate
    pose_keypoints = pose_keypoint_values(raw.attributes.get("pose_keypoints") if raw.attributes else None)
    if not pose_keypoints:
        return None
    source_keypoint_count = len(pose_keypoints)
    keypoint_schema = "coco17" if all(str(index) in pose_keypoints for index in COCO17_KEYPOINTS) else "coco17_partial"
    visible_points = sorted(int(index) for index, point in pose_keypoints.items() if len(point) >= 3 and float(point[2]) > 0.0)
    missing_points = [index for index in COCO17_KEYPOINTS if str(index) not in pose_keypoints or index not in visible_points]
    posture_features = posture_feature_summary(pose_keypoints)
    bbox_summary = {
        "person_bbox_frame_xyxy": box_values(object_context.boxes.frame_xyxy),
        "person_bbox_screen_xyxy": box_values(object_context.boxes.screen_xyxy),
    }
    reason_codes = []
    missing_required = []
    if keypoint_schema != "coco17":
        reason_codes.append("partial_coco17_keypoints")
    if not available_upper_body_profile(pose_keypoints):
        reason_codes.append("insufficient_upper_body_keypoints")
        missing_required.extend([index for index in (7, 8, 9, 10) if str(index) not in pose_keypoints])
    pose_action = str(raw.attributes.get("pose_action") or "pose") if raw.attributes else "pose"
    payload = {
        "keypoint_schema": keypoint_schema,
        "keypoint_count": 17 if keypoint_schema == "coco17" else source_keypoint_count,
        "visible_keypoint_count": len(visible_points),
        "visible_points": visible_points,
        "missing_points": missing_points,
        "pose_action_coarse": pose_action,
        "pose_quality_state": "sufficient" if source_keypoint_count >= 13 else "insufficient_keypoints",
        "available_profiles": available_pose_profiles(pose_keypoints),
        "missing_required_keypoints": sorted(set(missing_required)),
        "bbox_summary": bbox_summary,
        "source_keypoint_count": source_keypoint_count,
        "reason_codes": reason_codes,
    }
    timestamp_ms = int(getattr(frame_context, "timestamp_ms", 0) or 0) if frame_context is not None else None
    payload[POSE_SIDECAR_PAYLOAD_KEY] = {
        "schema_version": "pose_sidecar.v1",
        "keypoint_schema": keypoint_schema,
        "source_id": str(object_context.source_id),
        "frame_id": int(object_context.frame_id),
        "timestamp_ms": timestamp_ms,
        "object_id": str(object_context.object_id),
        "track_id": object_context.track_id,
        "track_version": int(object_context.track_version or 0),
        "bbox_summary": bbox_summary,
        "keypoints": pose_keypoints,
        "posture_features": posture_features,
        "reason_codes": reason_codes,
    }
    return payload


def available_pose_profiles(pose_keypoints: dict[str, list[float]]) -> list[str]:
    profiles = []
    if any(str(index) in pose_keypoints for index in (0, 1, 2, 3, 4)):
        profiles.append("face_visibility")
    if all(str(index) in pose_keypoints for index in (11, 12, 13, 14, 15, 16)):
        profiles.append("lower_body")
    if available_upper_body_profile(pose_keypoints):
        profiles.append("upper_body")
        profiles.append("relation_aux_candidate")
    return profiles


def available_upper_body_profile(pose_keypoints: dict[str, list[float]]) -> bool:
    return all(str(index) in pose_keypoints for index in (5, 6, 7, 8, 9, 10))


def posture_feature_summary(pose_keypoints: dict[str, list[float]]) -> dict[str, Any]:
    return {
        "feature_vector_schema": "posture_features.coco17.v1",
        "standing_state": lower_body_state(pose_keypoints),
        "sit_or_squat_state": sit_or_squat_state(pose_keypoints),
        "left_arm_up_state": arm_up_state(pose_keypoints, shoulder=5, elbow=7, wrist=9),
        "right_arm_up_state": arm_up_state(pose_keypoints, shoulder=6, elbow=8, wrist=10),
        "hand_near_head_left_state": hand_near_state(pose_keypoints, wrist=9, anchors=(0, 1, 3), max_distance_ratio=0.35),
        "hand_near_head_right_state": hand_near_state(pose_keypoints, wrist=10, anchors=(0, 2, 4), max_distance_ratio=0.35),
        "hand_near_torso_left_state": hand_near_state(pose_keypoints, wrist=9, anchors=(5, 11), max_distance_ratio=0.45),
        "hand_near_torso_right_state": hand_near_state(pose_keypoints, wrist=10, anchors=(6, 12), max_distance_ratio=0.45),
        "phone_like_candidate_left_state": phone_like_candidate_state(pose_keypoints, wrist=9, anchors=(0, 1, 3)),
        "phone_like_candidate_right_state": phone_like_candidate_state(pose_keypoints, wrist=10, anchors=(0, 2, 4)),
        "confidence_summary": pose_confidence_summary(pose_keypoints),
    }


def lower_body_state(pose_keypoints: dict[str, list[float]]) -> str:
    required = (11, 12, 13, 14, 15, 16)
    if not all(str(index) in pose_keypoints for index in required):
        return "insufficient_keypoints"
    left_hip, right_hip = point_value(pose_keypoints, 11), point_value(pose_keypoints, 12)
    left_knee, right_knee = point_value(pose_keypoints, 13), point_value(pose_keypoints, 14)
    left_ankle, right_ankle = point_value(pose_keypoints, 15), point_value(pose_keypoints, 16)
    hip_y = mean_coordinate([left_hip, right_hip], 1)
    knee_y = mean_coordinate([left_knee, right_knee], 1)
    ankle_y = mean_coordinate([left_ankle, right_ankle], 1)
    if hip_y is None or knee_y is None or ankle_y is None:
        return "insufficient_keypoints"
    leg_span = max(1.0, ankle_y - hip_y)
    return "standing" if (knee_y - hip_y) / leg_span >= 0.42 else "not_standing"


def sit_or_squat_state(pose_keypoints: dict[str, list[float]]) -> str:
    state = lower_body_state(pose_keypoints)
    if state == "insufficient_keypoints":
        return state
    return "sit_or_squat" if state == "not_standing" else "not_sit_or_squat"


def arm_up_state(pose_keypoints: dict[str, list[float]], *, shoulder: int, elbow: int, wrist: int) -> str:
    points = [point_value(pose_keypoints, index) for index in (shoulder, elbow, wrist)]
    if any(point is None for point in points):
        return "insufficient_keypoints"
    shoulder_y, elbow_y, wrist_y = (float(point[1]) for point in points if point is not None)
    return "arm_up" if wrist_y < shoulder_y and elbow_y < shoulder_y else "not_arm_up"


def hand_near_state(
    pose_keypoints: dict[str, list[float]],
    *,
    wrist: int,
    anchors: tuple[int, ...],
    max_distance_ratio: float,
) -> str:
    wrist_point = point_value(pose_keypoints, wrist)
    anchor_points = [point_value(pose_keypoints, index) for index in anchors]
    anchor_points = [point for point in anchor_points if point is not None]
    scale = body_scale(pose_keypoints)
    if wrist_point is None or not anchor_points or scale is None:
        return "insufficient_keypoints"
    distance = min(point_distance(wrist_point, anchor) for anchor in anchor_points)
    return "near" if distance / max(1.0, scale) <= max_distance_ratio else "not_near"


def phone_like_candidate_state(pose_keypoints: dict[str, list[float]], *, wrist: int, anchors: tuple[int, ...]) -> str:
    near_head = hand_near_state(pose_keypoints, wrist=wrist, anchors=anchors, max_distance_ratio=0.35)
    if near_head == "insufficient_keypoints":
        return "insufficient_keypoints"
    return "candidate" if near_head == "near" else "not_candidate"


def pose_confidence_summary(pose_keypoints: dict[str, list[float]]) -> dict[str, float]:
    scores = [float(point[2]) for point in pose_keypoints.values() if len(point) >= 3]
    if not scores:
        return {"min": 0.0, "mean": 0.0, "max": 0.0}
    return {"min": min(scores), "mean": sum(scores) / len(scores), "max": max(scores)}


def point_value(pose_keypoints: dict[str, list[float]], index: int) -> list[float] | None:
    point = pose_keypoints.get(str(index))
    return point if point and len(point) >= 2 else None


def mean_coordinate(points: list[list[float] | None], coordinate_index: int) -> float | None:
    values = [float(point[coordinate_index]) for point in points if point is not None]
    return sum(values) / len(values) if values else None


def body_scale(pose_keypoints: dict[str, list[float]]) -> float | None:
    ys = [float(point[1]) for point in pose_keypoints.values() if len(point) >= 2]
    if len(ys) < 2:
        return None
    return max(1.0, max(ys) - min(ys))


def point_distance(a: list[float], b: list[float]) -> float:
    return ((float(a[0]) - float(b[0])) ** 2 + (float(a[1]) - float(b[1])) ** 2) ** 0.5


def frame_envelopes_from_context(frame_context: FrameContext, *, recording_id: str) -> list[MetadataEnvelope]:
    frame_record = frame_record_from_context(frame_context, recording_id=recording_id)
    envelopes = [
        MetadataEnvelope.wrap(
            record_type="frame",
            recording_id=recording_id,
            source_id=frame_record.source_id,
            frame_id=frame_record.frame_id,
            timestamp_ms=frame_record.timestamp_ms,
            producer="frame_context_normalizer",
            payload=frame_record.to_payload(),
            record_id=f"{recording_id}:frame:{frame_record.source_id}:{frame_record.frame_id}",
        )
    ]
    for obj in frame_context.objects or []:
        object_record = object_record_from_context(obj, recording_id=recording_id)
        envelopes.append(
            MetadataEnvelope.wrap(
                record_type="object",
                recording_id=recording_id,
                source_id=object_record.source_id,
                frame_id=object_record.frame_id,
                timestamp_ms=frame_record.timestamp_ms,
                producer="object_context_normalizer",
                payload=object_record.to_payload(),
                record_id=f"{recording_id}:object:{object_record.source_id}:{object_record.frame_id}:{object_record.object_id}",
            )
        )
    return envelopes


def patch_record_from_patch(patch: MetadataPatch, *, recording_id: str) -> MetadataPatchRecord:
    return MetadataPatchRecord(
        recording_id=str(recording_id),
        source_id=str(patch.source_id),
        frame_id=int(patch.frame_id),
        object_id=str(patch.object_id),
        track_id=patch.track_id,
        patch_id=str(patch.patch_id),
        bucket=str(patch.bucket),
        producer=str(patch.producer),
        base_version=int(patch.base_version or 0),
        ttl_ms=int(patch.ttl_ms or 0),
        patch_summary=metadata_patch_summary(patch),
        created_at_ms=int(patch.created_at_ms or 0),
    )


def patch_envelope_from_patch(patch: MetadataPatch, *, recording_id: str) -> MetadataEnvelope:
    record = patch_record_from_patch(patch, recording_id=recording_id)
    return MetadataEnvelope.wrap(
        record_type="metadata_patch",
        recording_id=recording_id,
        source_id=record.source_id,
        frame_id=record.frame_id,
        timestamp_ms=record.created_at_ms,
        producer=record.producer,
        payload=record.to_payload(),
        record_id=f"{recording_id}:patch:{record.patch_id}",
    )


def hook_ref_from_artifact(
    artifact: ArtifactPayload,
    *,
    recording_id: str,
    source_id: str,
    frame_id: int | None = None,
    status: str = "unresolved",
    uri: str | None = None,
) -> HookRef:
    metadata = json_safe_value(artifact.metadata, path="artifact.metadata")
    summary = {
        "artifact_id": artifact.artifact_id,
        "artifact_name": artifact.name,
        "created_at_detector_index": int(artifact.created_at_detector_index or 0),
        "metadata": metadata,
    }
    if artifact.image is not None:
        summary["image_ref"] = summarize_heavy_value("image", artifact.image)
    if artifact.display_image is not None:
        summary["display_image_ref"] = summarize_heavy_value("display_image", artifact.display_image)
    if artifact.embedding is not None:
        summary["embedding_ref"] = summarize_heavy_value("embedding", artifact.embedding)
    return HookRef(
        hook_ref_id=f"hook_{artifact.artifact_id}" if artifact.artifact_id else new_id("hook"),
        recording_id=str(recording_id),
        source_id=str(source_id or ""),
        frame_id=int(frame_id) if frame_id is not None else None,
        object_id=artifact.object_id,
        track_id=artifact.track_id,
        kind=str(artifact.name or "artifact"),
        producer=str(artifact.producer or "artifact_runtime"),
        status=status,  # type: ignore[arg-type]
        summary=summary,
        uri=uri,
    )


def verified_summary(object_context: ObjectContext) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    verified = object_context.verified
    for name in ("identity", "age", "expression", "closed_class", "ocr", "pose", "hand", "pet"):
        field_value = getattr(verified, name, None)
        if not isinstance(field_value, VerificationField):
            continue
        if field_value.status == "not_run" and field_value.label is None and field_value.score is None:
            continue
        summary[name] = {
            "status": field_value.status,
            "label": field_value.label,
            "score": field_value.score,
            "producer": field_value.producer,
        }
    return summary


def json_safe_value(value: Any, *, path: str = "value") -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) <= MAX_STRING_LENGTH:
            return value
        return {"omitted": True, "reason": "string_too_long", "len": len(value)}
    if isinstance(value, bytes):
        return {"omitted": True, "reason": "bytes_payload", "len": len(value)}
    if is_dataclass(value):
        return summarize_heavy_value(path, value)
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_JSON_DICT_ITEMS:
                output["_truncated"] = {"omitted": True, "reason": "dict_too_large", "len": len(value)}
                break
            key_text = str(key)
            if key_text in RUNTIME_INTERNAL_FIELDS:
                continue
            if is_heavy_key(key_text):
                output[key_text] = summarize_heavy_value(key_text, item)
            else:
                output[key_text] = json_safe_value(item, path=f"{path}.{key_text}")
        return output
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        if len(items) > MAX_JSON_LIST_ITEMS:
            return summarize_heavy_value(path, value)
        return [json_safe_value(item, path=f"{path}[]") for item in items]
    return summarize_heavy_value(path, value)


def is_heavy_key(key: str) -> bool:
    lowered = key.strip().lower()
    return any(fragment in lowered for fragment in HEAVY_KEY_FRAGMENTS)


def summarize_heavy_value(name: str, value: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "omitted": True,
        "reason": "heavy_or_runtime_payload",
        "kind": str(name),
        "type": type(value).__name__,
    }
    if hasattr(value, "shape"):
        try:
            summary["shape"] = [int(item) for item in getattr(value, "shape")]
        except Exception:
            pass
    if hasattr(value, "size") and not isinstance(value, (str, bytes, bytearray, list, tuple, set, dict)):
        try:
            size = getattr(value, "size")
            summary["size"] = list(size) if isinstance(size, tuple) else size
        except Exception:
            pass
    try:
        summary["len"] = len(value)  # type: ignore[arg-type]
    except Exception:
        pass
    return summary


def box_values(value: Any) -> list[float] | None:
    if value is None:
        return None
    try:
        return [float(item) for item in list(value)[:4]]
    except Exception:
        return None


def pose_keypoint_values(value: Any) -> dict[str, list[float]]:
    if not value:
        return {}
    items = value.items() if isinstance(value, dict) else enumerate(value)
    output: dict[str, list[float]] = {}
    for raw_index, point in items:
        if point is None:
            continue
        try:
            values = list(point)
        except TypeError:
            continue
        if len(values) < 2:
            continue
        try:
            index = int(raw_index)
            x = float(values[0])
            y = float(values[1])
            score = float(values[2]) if len(values) >= 3 else 1.0
        except Exception:
            continue
        output[str(index)] = [x, y, score]
    return output


def mask_polygon_values(value: Any) -> list[list[list[float]]]:
    if not value:
        return []
    polygons: list[list[list[float]]] = []
    for polygon in value if isinstance(value, (list, tuple)) else []:
        points: list[list[float]] = []
        for point in polygon if isinstance(polygon, (list, tuple)) else []:
            try:
                values = list(point)
            except TypeError:
                continue
            if len(values) < 2:
                continue
            try:
                points.append([float(values[0]), float(values[1])])
            except Exception:
                continue
        if len(points) >= 3:
            polygons.append(points)
    return polygons


def metadata_patch_summary(patch: MetadataPatch) -> dict[str, Any]:
    field_name = bucket_to_verified_field(patch.bucket)
    cleaned = json_safe_value(patch.patch, path="patch")
    verified = cleaned.get("verified") if isinstance(cleaned, dict) else None
    field_value = verified.get(field_name) if isinstance(verified, dict) else None
    if not isinstance(field_value, dict):
        return {}
    status = field_value.get("status")
    label = field_value.get("label")
    score = field_value.get("score")
    attributes = field_value.get("attributes") if isinstance(field_value.get("attributes"), dict) else {}
    summary = {
        "bucket": patch.bucket,
        "status": status,
        "label": label,
        "score": score,
    }
    if patch.bucket == "identity":
        for key in ("nickname", "identity_nickname"):
            if key in attributes:
                summary["nickname"] = attributes[key]
                break
    elif patch.bucket == "age":
        for key in ("age_range", "range"):
            if key in attributes:
                summary["range"] = attributes[key]
                break
    elif patch.bucket == "face_roi":
        if "face_count" in attributes:
            summary["face_count"] = attributes["face_count"]
        for key in ("face_bbox_local", "raw_face_bbox_local"):
            if key in attributes:
                summary[key] = box_values(attributes[key])
    refs = {key: attributes[key] for key in PORTABLE_REF_KEYS if key in attributes}
    return {
        "status": status,
        "label": label,
        "score": score,
        "summary": json_safe_value(summary, path="patch.summary"),
        "verified_summary": {
            field_name: {
                "status": status,
                "label": label,
                "score": score,
            }
        },
        **json_safe_value(refs, path="patch.refs"),
    }
