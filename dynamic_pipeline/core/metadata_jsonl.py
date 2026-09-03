from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Iterable


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
    patches_by_object: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

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
            "patch_count": sum(len(items) for items in self.patches_by_object.values()),
            "issues": [{"line_number": issue.line_number, "reason": issue.reason} for issue in self.issues],
        }


class MetadataJsonlWriter:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("a", encoding="utf-8")
        self.records_written = 0

    def write(self, record: Any) -> None:
        payload = record.to_dict() if hasattr(record, "to_dict") else record
        if not isinstance(payload, dict):
            raise TypeError("metadata record must serialize to an object")
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


class MetadataReplayReader:
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
            if error or not isinstance(record, dict):
                summary.bad_jsonl_lines += 1
                summary.issues.append(MetadataReplayIssue(line_number, "bad_jsonl" if error else "record_not_object"))
                continue
            summary.records_read += 1
            record_type = str(record.get("record_type") or "")
            payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
            source_id = str(record.get("source_id") or payload.get("source_id") or "")
            frame_id = record.get("frame_id", payload.get("frame_id"))
            frame_key = (source_id, int(frame_id)) if frame_id is not None else (source_id, -1)
            if record_type == "frame":
                summary.frames[frame_key] = record
            elif record_type == "object":
                summary.objects_by_frame.setdefault(frame_key, []).append(record)
            elif record_type == "metadata_patch":
                object_id = str(record.get("object_id") or payload.get("object_id") or "")
                if object_id:
                    summary.patches_by_object.setdefault(object_id, []).append(record)
        return summary
