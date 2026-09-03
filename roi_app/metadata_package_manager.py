from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from dynamic_pipeline.core.context import now_ms
from dynamic_pipeline.core.event_registry import EventRegistry
from dynamic_pipeline.core.package_manifest import PACKAGE_SCHEMA_VERSION, MetadataPackageManifest, default_package_id, write_json
from dynamic_pipeline.core.paste_rules import write_paste_rules
from dynamic_pipeline.core.ref_graph import RefGraphWriter
from dynamic_pipeline.core.source_archive import SourceArchive
from dynamic_pipeline.core.source_fingerprint import SourceFingerprint, fingerprint_file, write_source_fingerprint

INDEX_NAMES = ("by_frame", "by_track", "by_object", "by_hook_ref", "by_memory_ref", "by_time")


@dataclass(frozen=True)
class MetadataPackagePaths:
    root: Path
    manifest: Path
    metadata: Path
    paste_rules: Path
    refs: Path
    indexes: dict[str, Path]
    writer_checkpoint: Path
    source_fingerprint: Path
    archive_link: Path


class MetadataPackageManager:
    """Curated package manager for the public synthetic metadata path."""

    def __init__(
        self,
        root: str | Path,
        *,
        package_id: str | None = None,
        recording_id: str | None = None,
        source_id: str = "source",
        source_mode: str = "Offline",
        metadata_landing_mode: str = "offline_only",
        eligible_source_modes: tuple[str, ...] | list[str] = ("Offline",),
        archive_link_timing: str = "post_close_idle",
        source_path: str | Path | None = None,
        source_kind: str = "file",
        description: str | None = None,
    ):
        self.root = Path(root)
        self.source_mode = str(source_mode)
        self.metadata_landing_mode = str(metadata_landing_mode)
        self.eligible_source_modes = {str(item) for item in eligible_source_modes}
        self.archive_link_timing = str(archive_link_timing)
        self.source_path = Path(source_path) if source_path else None
        self.source_kind = str(source_kind)
        self.archive_managed = self._archive_managed()
        self.event_id = EventRegistry(self.root).allocate_event_id() if self.archive_managed and package_id is None else None
        self.created_at_ms = now_ms()
        self.package_id = package_id or default_package_id(event_id=self.event_id if self.event_id is not None else "unmanaged", description=description)
        self.recording_id = recording_id or self.package_id
        self.source_id = str(source_id)
        package_root = self.root / "packages" / self.package_id
        self.paths = MetadataPackagePaths(
            root=package_root,
            manifest=package_root / "manifest.json",
            metadata=package_root / "metadata.jsonl",
            paste_rules=package_root / "paste_rules.yaml",
            refs=package_root / "refs.jsonl",
            indexes={name: package_root / "indexes" / f"{name}.jsonl" for name in INDEX_NAMES},
            writer_checkpoint=package_root / "checkpoints" / "writer_checkpoint.json",
            source_fingerprint=package_root / "source_fingerprint.json",
            archive_link=package_root / "archive_link.json",
        )

    def is_enabled_for_landing(self) -> bool:
        return self.archive_managed

    def ensure_open(self) -> MetadataPackageManifest:
        self.paths.root.mkdir(parents=True, exist_ok=True)
        (self.paths.root / "indexes").mkdir(exist_ok=True)
        (self.paths.root / "checkpoints").mkdir(exist_ok=True)
        write_paste_rules(self.paths.paste_rules, self.package_id)
        if not self.paths.manifest.is_file():
            write_json(self.paths.manifest, self._manifest("open").to_dict())
        for path in [self.paths.metadata, self.paths.refs, *self.paths.indexes.values()]:
            path.touch(exist_ok=True)
        return self._manifest("open")

    def mark_state(self, state: str) -> None:
        write_json(self.paths.manifest, self._manifest(state).to_dict())

    def close_package(self, state: str = "closed") -> None:
        self.mark_state(state)
        if state != "closed" or not self.archive_managed:
            return
        fingerprint = self.compute_source_fingerprint()
        if fingerprint is None or self.event_id is None:
            return
        SourceArchive(self.root).link_package(
            package_root=self.paths.root,
            package_id=self.package_id,
            event_id=self.event_id,
            package_created_at_ms=self.created_at_ms,
            fingerprint=fingerprint,
            state=state,
        )

    def compute_source_fingerprint(self) -> SourceFingerprint | None:
        if not self.archive_managed or self.source_path is None or not self.source_path.is_file():
            return None
        fingerprint = fingerprint_file(self.source_path, source_kind=self.source_kind)
        write_source_fingerprint(self.paths.source_fingerprint, fingerprint)
        return fingerprint

    def ref_writer(self) -> RefGraphWriter:
        return RefGraphWriter(self.paths.refs)

    def append_indexes_for_event(self, event: Any) -> int:
        record = event.to_dict() if hasattr(event, "to_dict") else event
        if not isinstance(record, dict):
            return 0
        base = {key: record.get(key) for key in ("record_id", "record_type", "source_id", "frame_id", "timestamp_ms", "object_id", "track_id")}
        rows: list[tuple[str, dict[str, Any]]] = [("by_time", dict(base))]
        if record.get("frame_id") is not None:
            rows.append(("by_frame", dict(base)))
        if record.get("track_id"):
            rows.append(("by_track", dict(base)))
        if record.get("object_id"):
            rows.append(("by_object", dict(base)))
        refs = record.get("refs") if isinstance(record.get("refs"), dict) else {}
        if refs.get("hook_ref_id"):
            rows.append(("by_hook_ref", {**base, "hook_ref_id": refs["hook_ref_id"]}))
        if refs.get("memory_ref"):
            rows.append(("by_memory_ref", {**base, "memory_ref": refs["memory_ref"]}))
        for name, row in rows:
            with self.paths.indexes[name].open("a", encoding="utf-8") as file:
                file.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        return len(rows)

    def write_writer_checkpoint(self, event: Any) -> None:
        record = event.to_dict() if hasattr(event, "to_dict") else event
        if isinstance(record, dict):
            write_json(self.paths.writer_checkpoint, {
                "package_id": self.package_id,
                "commit_state": "complete",
                "record_id": record.get("record_id"),
                "record_type": record.get("record_type"),
                "timestamp_ms": record.get("timestamp_ms"),
                "updated_at_ms": now_ms(),
            })

    def _manifest(self, state: str) -> MetadataPackageManifest:
        return MetadataPackageManifest(
            schema_version=PACKAGE_SCHEMA_VERSION,
            package_id=self.package_id,
            display_name=self.package_id,
            created_at_ms=self.created_at_ms,
            updated_at_ms=now_ms(),
            recording_id=self.recording_id,
            source_id=self.source_id,
            root_kind="local_metadata_package",
            metadata_file="metadata.jsonl",
            paste_rules_file="paste_rules.yaml",
            refs_file="refs.jsonl",
            index_files={name: f"indexes/{name}.jsonl" for name in INDEX_NAMES},
            contains_scheduler_trace=False,
            contains_raw_payload=False,
            sidecar_policy={},
            package_state=str(state),
            event_id=self.event_id,
            source_mode=self.source_mode,
            metadata_landing_mode=self.metadata_landing_mode,
            archive_managed=self.archive_managed,
            archive_link_timing=self.archive_link_timing,
        )

    def _archive_managed(self) -> bool:
        if self.metadata_landing_mode == "disabled":
            return False
        if self.metadata_landing_mode == "offline_only":
            return self.source_mode in self.eligible_source_modes
        return self.metadata_landing_mode == "all_sources"
