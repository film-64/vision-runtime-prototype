from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dynamic_pipeline.core.context import BoxSet, FrameContext, ObjectContext, RawCandidate, VerificationField
from dynamic_pipeline.core.source_archive import SourceArchive


REPO_ROOT = Path(__file__).resolve().parents[1]


class ReplayRuntime:
    """Read-only metadata package replay source."""

    def __init__(self, app: Any):
        self.app = app
        self.package_root: Path | None = None
        self.frames: list[dict[str, Any]] = []
        self.index = 0
        self.background = ReplayBackgroundProvider()

    def reset(self) -> None:
        self.package_root = None
        self.frames = []
        self.index = 0

    def tick(self) -> None:
        if not self.ensure_loaded():
            self.app.roi.set_video_frame(self.background.frame((640, 640)))
            self.app.roi.set_frame_context(None)
            self.app.timer.start(self.app.dynamic_ui_tick_ms("replay_empty"))
            return
        if self.app.video_paused:
            frame_context = self.current_frame_context()
        else:
            frame_context = self.next_frame_context()
        if frame_context is None:
            self.app.set_status("Replay: no metadata frame")
            self.app.timer.start(self.app.dynamic_ui_tick_ms("replay_empty"))
            return
        self.app.roi.set_video_frame(self.background.frame(frame_context.frame_size))
        self.app.roi.set_frame_context(frame_context)
        self.app.set_status(f"Replay frame={frame_context.frame_id} objects={len(frame_context.objects)}")
        self.app.timer.start(max(1, int(1000 / self.video_display_fps())))

    def ensure_loaded(self) -> bool:
        root = self.selected_package_root()
        if root is None:
            self.app.set_status("Replay skipped: no metadata package")
            return False
        if self.package_root == root and self.frames:
            return True
        try:
            self.frames = load_replay_frames(root)
        except Exception as exc:
            self.app.set_status(f"Replay load failed: {exc}")
            self.frames = []
            self.package_root = root
            return False
        self.package_root = root
        self.index = 0
        if not self.frames:
            self.app.set_status(f"Replay empty package: {root}/metadata.jsonl has no frame records")
            return False
        self.app.set_status(f"Replay loaded: {root.name} frames={len(self.frames)}")
        return bool(self.frames)

    def selected_package_root(self) -> Path | None:
        raw = str(self.app.config.get("replay_package_path", "") or "").strip()
        if raw:
            path = Path(raw)
            if not path.is_absolute():
                path = REPO_ROOT / path
            if path.name == "metadata.jsonl":
                path = path.parent
            return path if (path / "metadata.jsonl").is_file() else None
        source_hash = str(self.app.config.get("replay_source_hash", "") or "").strip()
        if not source_hash:
            return None
        metadata_root = Path(str(self.app.config.get("metadata_runtime_output_root", "output/metadata/default") or "output/metadata/default"))
        if not metadata_root.is_absolute():
            metadata_root = REPO_ROOT / metadata_root
        path = resolve_replay_package_root(
            metadata_root,
            source_hash=source_hash,
            package_view=str(self.app.config.get("replay_package_view", "aggregate_if_available") or "aggregate_if_available"),
        )
        return path if path is not None and (path / "metadata.jsonl").is_file() else None

    def current_frame_context(self) -> FrameContext | None:
        if not self.frames:
            return None
        position = max(0, min(self.index - 1, len(self.frames) - 1))
        return frame_context_from_replay(self.frames[position])

    def next_frame_context(self) -> FrameContext | None:
        if not self.frames:
            return None
        if self.index >= len(self.frames):
            if self.video_loop():
                self.index = 0
            else:
                return self.current_frame_context()
        frame = self.frames[self.index]
        self.index += 1
        return frame_context_from_replay(frame)

    def video_display_fps(self) -> float:
        return max(1.0, float(self.app.config.get("video_display_fps", "30") or 30))

    def video_loop(self) -> bool:
        return str(self.app.config.get("video_loop", "true") or "true").strip().lower() in {"1", "true", "yes", "on"}


def resolve_replay_package_root(
    metadata_root: str | Path,
    *,
    source_hash: str,
    package_view: str = "aggregate_if_available",
) -> Path | None:
    metadata_root = Path(metadata_root)
    resolved = SourceArchive(metadata_root).resolve_by_hash(source_hash)
    if not resolved:
        return None
    view = str(package_view or "aggregate_if_available")
    latest_aggregate = resolved.get("latest_aggregate_event") if isinstance(resolved, dict) else None
    latest_event = resolved.get("latest_event") if isinstance(resolved, dict) else None
    if view == "aggregate_if_available" and isinstance(latest_aggregate, dict) and latest_aggregate.get("latest_package_path"):
        return metadata_root / str(latest_aggregate["latest_package_path"])
    if isinstance(latest_event, dict) and latest_event.get("latest_package_path"):
        return metadata_root / str(latest_event["latest_package_path"])
    return None


class ReplayBackgroundProvider:
    def __init__(self):
        self._cache: dict[tuple[int, int], Any] = {}

    def frame(self, frame_size: tuple[int, int]) -> Any:
        from PySide6.QtGui import QColor, QImage

        width = max(1, int(frame_size[0] or 1))
        height = max(1, int(frame_size[1] or 1))
        key = (width, height)
        image = self._cache.get(key)
        if image is None:
            image = QImage(width, height, QImage.Format_RGB32)
            image.fill(QColor("#737373"))
            self._cache[key] = image
        return image


def load_replay_frames(package_root: str | Path) -> list[dict[str, Any]]:
    root = Path(package_root)
    path = root / "metadata.jsonl"
    frames: dict[tuple[str, int], dict[str, Any]] = {}
    objects: dict[tuple[str, int], list[dict[str, Any]]] = {}
    patches: dict[str, list[dict[str, Any]]] = {}
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                continue
            record_type = str(record.get("record_type") or "")
            source_id = str(record.get("source_id") or "")
            frame_id = record.get("frame_id")
            frame_key = (source_id, int(frame_id)) if frame_id is not None else (source_id, -1)
            if record_type == "frame":
                frames[frame_key] = record
            elif record_type == "object":
                objects.setdefault(frame_key, []).append(record)
            elif record_type == "metadata_patch":
                object_id = str(record.get("object_id") or "")
                if object_id:
                    patches.setdefault(object_id, []).append(record)
    output = []
    for key in sorted(frames, key=lambda item: (frames[item].get("timestamp_ms") or 0, item[0], item[1])):
        record = dict(frames[key])
        frame_objects = [
            merge_patch_summaries(item, patches.get(replay_object_id(item), [])) for item in objects.get(key, [])
        ]
        record["objects"] = frame_objects
        output.append(record)
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


def frame_context_from_replay(frame_record: dict[str, Any]) -> FrameContext:
    payload = frame_record.get("payload") if isinstance(frame_record.get("payload"), dict) else {}
    frame = FrameContext(
        frame_id=int(frame_record.get("frame_id") or payload.get("frame_id") or 0),
        source_id=str(frame_record.get("source_id") or payload.get("source_id") or "Replay"),
        timestamp_ms=int(frame_record.get("timestamp_ms") or payload.get("timestamp_ms") or 0),
        frame_width=int(payload.get("frame_width") or 1),
        frame_height=int(payload.get("frame_height") or 1),
        prompt_version=int(payload.get("prompt_version") or 0),
        platform={"kind": "Replay"},
        detector_index=int(payload.get("detector_index") or frame_record.get("frame_id") or 0),
    )
    frame.objects = [object_context_from_replay(record, frame) for record in frame_record.get("objects", [])]
    return frame


def object_context_from_replay(record: dict[str, Any], frame: FrameContext) -> ObjectContext:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    frame_box = as_float_box(payload.get("bbox_frame_xyxy")) or [0.0, 0.0, 1.0, 1.0]
    screen_box = as_float_box(payload.get("bbox_screen_xyxy"))
    label = str(payload.get("display_label") or payload.get("class_name") or "object")
    score = float(payload.get("display_score") if payload.get("display_score") is not None else payload.get("confidence") or 0.0)
    raw = RawCandidate(
        producer=str(record.get("producer") or "Replay"),
        class_name=str(payload.get("class_name") or label),
        confidence=float(payload.get("confidence") or score or 0.0),
        prompt_names=[label],
        attributes={
            "pose_keypoints": payload.get("pose_keypoints") or {},
            "mask_polygons": payload.get("mask_polygons") or [],
        },
    )
    obj = ObjectContext(
        object_id=str(record.get("object_id") or payload.get("object_id") or ""),
        frame_id=frame.frame_id,
        source_id=frame.source_id,
        frame_size=frame.frame_size,
        boxes=BoxSet.from_frame_box(frame_box, frame.frame_size, screen_xyxy=screen_box),
        raw_candidate=raw,
        track_id=record.get("track_id") or payload.get("track_id"),
        track_version=int(record.get("track_version") or payload.get("track_version") or 0),
        source_track_id=record.get("track_id") or payload.get("track_id"),
        detector_index=frame.detector_index,
        source_detector_index=frame.detector_index,
        deadline_detector_index=frame.detector_index,
    )
    obj.display.label = label
    obj.display.score = score
    apply_verified_summary(obj, payload.get("verified_summary"))
    return obj


def apply_verified_summary(obj: ObjectContext, summary: Any) -> None:
    if not isinstance(summary, dict):
        return
    for name, value in summary.items():
        field = getattr(obj.verified, str(name), None)
        if not isinstance(field, VerificationField) or not isinstance(value, dict):
            continue
        field.status = str(value.get("status") or field.status)
        field.label = value.get("label")
        field.score = value.get("score")
        field.producer = value.get("producer")


def as_float_box(value: Any) -> list[float] | None:
    if value is None:
        return None
    try:
        values = [float(item) for item in list(value)[:4]]
    except Exception:
        return None
    return values if len(values) == 4 else None
