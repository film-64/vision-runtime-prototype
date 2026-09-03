from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dynamic_pipeline.core.context import BoxSet, FrameContext, ObjectContext, RawCandidate, VerificationField


class ReplayRuntime:
    """Headless read-only replay of a durable metadata package."""

    def __init__(self, app: Any):
        self.app = app
        self.package_root: Path | None = None
        self.frames: list[dict[str, Any]] = []
        self.index = 0

    def ensure_loaded(self) -> bool:
        raw = str(self.app.config.get("replay_package_path", "") or "").strip()
        root = Path(raw) if raw else None
        if root is None or not (root / "metadata.jsonl").is_file():
            self.app.set_status("Replay skipped: no metadata package")
            return False
        if self.package_root == root and self.frames:
            return True
        try:
            self.frames = load_replay_frames(root)
        except Exception as exc:
            self.frames = []
            self.package_root = root
            self.app.set_status(f"Replay load failed: {exc}")
            return False
        self.package_root = root
        self.index = 0
        if not self.frames:
            self.app.set_status(f"Replay empty package: {root}/metadata.jsonl has no frame records")
            return False
        self.app.set_status(f"Replay loaded: {root.name} frames={len(self.frames)}")
        return True

    def current_frame_context(self) -> FrameContext | None:
        if not self.frames:
            return None
        position = max(0, min(self.index - 1, len(self.frames) - 1))
        return frame_context_from_replay(self.frames[position])

    def next_frame_context(self) -> FrameContext | None:
        if not self.frames:
            return None
        if self.index >= len(self.frames):
            return self.current_frame_context()
        frame = self.frames[self.index]
        self.index += 1
        return frame_context_from_replay(frame)


def load_replay_frames(package_root: str | Path) -> list[dict[str, Any]]:
    path = Path(package_root) / "metadata.jsonl"
    frames: dict[tuple[str, int], dict[str, Any]] = {}
    objects: dict[tuple[str, int], list[dict[str, Any]]] = {}
    patches: dict[str, list[dict[str, Any]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            continue
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        source_id = str(record.get("source_id") or payload.get("source_id") or "")
        frame_id = record.get("frame_id", payload.get("frame_id"))
        key = (source_id, int(frame_id)) if frame_id is not None else (source_id, -1)
        record_type = str(record.get("record_type") or "")
        if record_type == "frame":
            frames[key] = record
        elif record_type == "object":
            objects.setdefault(key, []).append(record)
        elif record_type == "metadata_patch":
            object_id = str(record.get("object_id") or payload.get("object_id") or "")
            if object_id:
                patches.setdefault(object_id, []).append(record)
    output = []
    for key in sorted(frames, key=lambda item: (frames[item].get("timestamp_ms") or 0, item[0], item[1])):
        frame = dict(frames[key])
        frame["objects"] = [merge_patch_summaries(obj, patches.get(replay_object_id(obj), [])) for obj in objects.get(key, [])]
        output.append(frame)
    return output


def replay_object_id(record: dict[str, Any]) -> str:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    return str(record.get("object_id") or payload.get("object_id") or "")


def merge_patch_summaries(object_record: dict[str, Any], patches: list[dict[str, Any]]) -> dict[str, Any]:
    record = dict(object_record)
    payload = dict(record.get("payload") if isinstance(record.get("payload"), dict) else {})
    verified = dict(payload.get("verified_summary") if isinstance(payload.get("verified_summary"), dict) else {})
    for patch in patches:
        patch_payload = patch.get("payload") if isinstance(patch.get("payload"), dict) else {}
        patch_verified = patch_payload.get("verified_summary") if isinstance(patch_payload.get("verified_summary"), dict) else {}
        verified.update(patch_verified)
    payload["verified_summary"] = verified
    record["payload"] = payload
    return record


def frame_context_from_replay(record: dict[str, Any]) -> FrameContext:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    frame = FrameContext(
        frame_id=int(record.get("frame_id") or payload.get("frame_id") or 0),
        source_id=str(record.get("source_id") or payload.get("source_id") or "Replay"),
        timestamp_ms=int(record.get("timestamp_ms") or payload.get("timestamp_ms") or 0),
        frame_width=int(payload.get("frame_width") or 1),
        frame_height=int(payload.get("frame_height") or 1),
        prompt_version=int(payload.get("prompt_version") or 0),
        platform={"kind": "Replay"},
        detector_index=int(payload.get("detector_index") or record.get("frame_id") or 0),
    )
    frame.objects = [object_context_from_replay(obj, frame) for obj in record.get("objects", [])]
    return frame


def object_context_from_replay(record: dict[str, Any], frame: FrameContext) -> ObjectContext:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    frame_box = _float_box(payload.get("bbox_frame_xyxy")) or [0.0, 0.0, 1.0, 1.0]
    screen_box = _float_box(payload.get("bbox_screen_xyxy"))
    label = str(payload.get("display_label") or payload.get("class_name") or "object")
    score = float(payload.get("display_score") if payload.get("display_score") is not None else payload.get("confidence") or 0.0)
    obj = ObjectContext(
        object_id=str(record.get("object_id") or payload.get("object_id") or ""),
        frame_id=frame.frame_id,
        source_id=frame.source_id,
        frame_size=frame.frame_size,
        boxes=BoxSet.from_frame_box(frame_box, frame.frame_size, screen_xyxy=screen_box),
        raw_candidate=RawCandidate(
            producer=str(record.get("producer") or "Replay"),
            class_name=str(payload.get("class_name") or label),
            confidence=float(payload.get("confidence") or score),
            prompt_names=[label],
        ),
        track_id=record.get("track_id") or payload.get("track_id"),
        source_track_id=record.get("track_id") or payload.get("track_id"),
        track_version=int(record.get("track_version") or payload.get("track_version") or 0),
        detector_index=frame.detector_index,
        source_detector_index=frame.detector_index,
        deadline_detector_index=frame.detector_index,
    )
    obj.display.label = label
    obj.display.score = score
    summary = payload.get("verified_summary")
    if isinstance(summary, dict):
        for name, value in summary.items():
            field = getattr(obj.verified, str(name), None)
            if isinstance(field, VerificationField) and isinstance(value, dict):
                field.status = str(value.get("status") or field.status)
                field.label = value.get("label")
                field.score = value.get("score")
                field.producer = value.get("producer")
    return obj


def _float_box(value: Any) -> list[float] | None:
    if value is None:
        return None
    try:
        values = [float(item) for item in list(value)[:4]]
    except Exception:
        return None
    return values if len(values) == 4 else None
