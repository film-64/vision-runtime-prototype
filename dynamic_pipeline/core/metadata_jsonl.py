from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Iterable

from .durable_metadata import LocalSchedulerEvent


@dataclass(frozen=True)
class MetadataReplayIssue:
    line_number: int
    reason: str


@dataclass
class MetadataReplaySummary:
    path: Path
    records_read: int = 0
    bad_jsonl_lines: int = 0
    issues: list[MetadataReplayIssue] = field(default_factory=list)
    frames: dict[tuple[str, int], dict[str, Any]] = field(default_factory=dict)
    objects_by_frame: dict[tuple[str, int], list[dict[str, Any]]] = field(default_factory=dict)
    pose_observations_by_object: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    patches_by_object: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    hook_refs: list[dict[str, Any]] = field(default_factory=list)
    aggregate_package_markers: list[dict[str, Any]] = field(default_factory=list)
    aggregate_layer_markers: list[dict[str, Any]] = field(default_factory=list)
    aggregate_fusion_groups: list[dict[str, Any]] = field(default_factory=list)

    def frame_count(self) -> int:
        return len(self.frames)

    def object_count(self) -> int:
        return sum(len(items) for items in self.objects_by_frame.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "records_read": self.records_read,
            "bad_jsonl_lines": self.bad_jsonl_lines,
            "frame_count": self.frame_count(),
            "object_count": self.object_count(),
            "pose_observation_count": sum(len(items) for items in self.pose_observations_by_object.values()),
            "patch_count": sum(len(items) for items in self.patches_by_object.values()),
            "hook_ref_count": len(self.hook_refs),
            "aggregate_package_marker_count": len(self.aggregate_package_markers),
            "aggregate_layer_marker_count": len(self.aggregate_layer_markers),
            "aggregate_fusion_group_count": len(self.aggregate_fusion_groups),
            "issues": [{"line_number": issue.line_number, "reason": issue.reason} for issue in self.issues],
        }


class MetadataJsonlWriter:
    """Append-only writer for the durable metadata timeline."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("a", encoding="utf-8")
        self.records_written = 0

    def write(self, record: Any) -> None:
        payload = record.to_dict() if hasattr(record, "to_dict") else record
        if isinstance(record, LocalSchedulerEvent) or (
            isinstance(payload, dict) and payload.get("record_type") == "local_scheduler_event"
        ):
            raise ValueError("local scheduler events must not be written to metadata.jsonl")
        self._file.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        self.records_written += 1

    def write_many(self, records: Iterable[Any]) -> None:
        for record in records:
            self.write(record)

    def flush(self) -> None:
        self._file.flush()

    def close(self) -> None:
        self.flush()
        self._file.close()

    def __enter__(self) -> "MetadataJsonlWriter":
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()


class MetadataReplayReader:
    """Read durable metadata without importing the live detector/runtime path."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def iter_records(self):
        if not self.path.is_file():
            return
        with self.path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    yield line_number, json.loads(text), None
                except json.JSONDecodeError as exc:
                    yield line_number, None, str(exc)

    def read_summary(self) -> MetadataReplaySummary:
        summary = MetadataReplaySummary(path=self.path)
        for line_number, record, error in self.iter_records():
            if error:
                summary.bad_jsonl_lines += 1
                summary.issues.append(MetadataReplayIssue(line_number=line_number, reason="bad_jsonl"))
                continue
            if not isinstance(record, dict):
                summary.bad_jsonl_lines += 1
                summary.issues.append(MetadataReplayIssue(line_number=line_number, reason="record_not_object"))
                continue
            summary.records_read += 1
            self._add_record(summary, record)
        return summary

    def _add_record(self, summary: MetadataReplaySummary, record: dict[str, Any]) -> None:
        record_type = str(record.get("record_type") or "")
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        source_id = str(record.get("source_id") or payload.get("source_id") or "")
        frame_id = record.get("frame_id", payload.get("frame_id"))
        frame_key = (source_id, int(frame_id)) if frame_id is not None else (source_id, -1)
        if record_type == "frame":
            summary.frames[frame_key] = record
        elif record_type == "object":
            summary.objects_by_frame.setdefault(frame_key, []).append(record)
        elif record_type == "pose_observation":
            object_id = str(record.get("object_id") or payload.get("object_id") or "")
            summary.pose_observations_by_object.setdefault(object_id, []).append(record)
        elif record_type == "metadata_patch":
            object_id = str(record.get("object_id") or payload.get("object_id") or "")
            summary.patches_by_object.setdefault(object_id, []).append(record)
        elif record_type == "hook_ref":
            summary.hook_refs.append(record)
        elif record_type == "aggregate_package_marker":
            summary.aggregate_package_markers.append(record)
        elif record_type == "aggregate_layer_marker":
            summary.aggregate_layer_markers.append(record)
        elif record_type == "aggregate_fusion_group":
            summary.aggregate_fusion_groups.append(record)

    def list_frames(self) -> list[dict[str, Any]]:
        summary = self.read_summary()
        return [summary.frames[key] for key in sorted(summary.frames)]

    def objects_for_frame(self, source_id: str, frame_id: int) -> list[dict[str, Any]]:
        summary = self.read_summary()
        return list(summary.objects_by_frame.get((str(source_id), int(frame_id)), []))
