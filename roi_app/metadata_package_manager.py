from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
from typing import Any

from dynamic_pipeline.core.context import now_ms
from dynamic_pipeline.core.event_registry import EventRegistry
from dynamic_pipeline.core.package_manifest import (
    PACKAGE_SCHEMA_VERSION,
    MetadataPackageManifest,
    default_package_id,
    write_json,
)
from dynamic_pipeline.core.package_identity import PackageIdentity
from dynamic_pipeline.core.paste_rules import write_paste_rules
from dynamic_pipeline.core.ref_graph import RefGraphWriter
from dynamic_pipeline.core.source_fingerprint import SourceFingerprint, fingerprint_file, write_source_fingerprint
from roi_app.archive_link_worker import ArchiveLinkWorker
from roi_app.source_modes import source_mode_or_default


INDEX_NAMES = ("by_frame", "by_track", "by_object", "by_hook_ref", "by_memory_ref", "by_time")


@dataclass(frozen=True)
class MetadataPackagePaths:
    root: Path
    manifest: Path
    metadata: Path
    paste_rules: Path
    refs: Path
    indexes: dict[str, Path]
    local_scheduler_trace: Path
    writer_checkpoint: Path
    sync_checkpoint: Path
    portable_bundles: Path
    hydrated_bundles: Path
    debug_bundles: Path
    source_fingerprint: Path
    archive_link: Path


class MetadataPackageManager:
    def __init__(
        self,
        root: str | Path,
        *,
        package_id: str | None = None,
        recording_id: str | None = None,
        source_id: str = "pc_roi_capture",
        source_mode: str = "frame",
        metadata_landing_mode: str = "offline_only",
        eligible_source_modes: list[str] | tuple[str, ...] | str = ("Offline",),
        archive_link_timing: str = "post_close_idle",
        source_path: str | Path | None = None,
        source_kind: str = "video",
        description: str | None = None,
    ):
        self.root = Path(root)
        self.source_mode = str(source_mode or "")
        self.metadata_landing_mode = str(metadata_landing_mode or "disabled")
        self.eligible_source_modes = self._eligible_set(eligible_source_modes)
        self.archive_link_timing = str(archive_link_timing or "post_close_idle")
        self.source_path = Path(source_path) if source_path else None
        self.source_kind = str(source_kind or "video")
        self.archive_managed = self._archive_managed()
        self.event_id = EventRegistry(self.root).allocate_event_id() if self.archive_managed and package_id is None else None
        self.created_at_ms = now_ms()
        self.package_id = package_id or default_package_id(event_id=self.event_id if self.event_id is not None else "unmanaged", description=description)
        self.recording_id = recording_id or self.package_id
        self.source_id = str(source_id or "")
        self.identity = PackageIdentity(
            event_id=self.event_id,
            package_id=self.package_id,
            package_root=self.root / "packages" / self.package_id,
            created_at_ms=self.created_at_ms,
            source_mode=self.source_mode,
            metadata_landing_mode=self.metadata_landing_mode,
            archive_managed=self.archive_managed,
        )
        self.paths = self._paths()

    def _paths(self) -> MetadataPackagePaths:
        root = self.root / "packages" / self.package_id
        indexes = {name: root / "indexes" / f"{name}.jsonl" for name in INDEX_NAMES}
        return MetadataPackagePaths(
            root=root,
            manifest=root / "manifest.json",
            metadata=root / "metadata.jsonl",
            paste_rules=root / "paste_rules.yaml",
            refs=root / "refs.jsonl",
            indexes=indexes,
            local_scheduler_trace=root / "local" / "local_scheduler_trace.jsonl",
            writer_checkpoint=root / "checkpoints" / "writer_checkpoint.json",
            sync_checkpoint=root / "checkpoints" / "sync_checkpoint.json",
            portable_bundles=root / "bundles" / "portable",
            hydrated_bundles=root / "bundles" / "hydrated",
            debug_bundles=root / "bundles" / "debug",
            source_fingerprint=root / "source_fingerprint.json",
            archive_link=root / "archive_link.json",
        )

    def is_enabled_for_landing(self) -> bool:
        return self.archive_managed

    def ensure_open(self) -> MetadataPackageManifest:
        for path in (
            self.paths.root,
            self.paths.root / "indexes",
            self.paths.root / "sidecars" / "crops",
            self.paths.root / "sidecars" / "images",
            self.paths.root / "sidecars" / "embeddings",
            self.paths.root / "sidecars" / "pose",
            self.paths.root / "sidecars" / "masks",
            self.paths.root / "sidecars" / "debug",
            self.paths.root / "local",
            self.paths.root / "bundles" / "portable",
            self.paths.root / "bundles" / "hydrated",
            self.paths.root / "bundles" / "debug",
            self.paths.root / "checkpoints",
        ):
            path.mkdir(parents=True, exist_ok=True)
        if not self.paths.paste_rules.is_file():
            write_paste_rules(self.paths.paste_rules, self.package_id)
        manifest = self._manifest("open")
        if not self.paths.manifest.is_file():
            write_json(self.paths.manifest, manifest.to_dict())
        for path in [self.paths.metadata, self.paths.refs, *self.paths.indexes.values()]:
            path.touch(exist_ok=True)
        return manifest

    def mark_state(self, state: str) -> None:
        manifest = self._manifest(state)
        write_json(self.paths.manifest, manifest.to_dict())

    def close_package(self, state: str = "closed") -> None:
        self.mark_state(state)
        if state != "closed" or not self.archive_managed:
            return
        fingerprint = self.compute_source_fingerprint()
        if fingerprint is None or self.event_id is None:
            return
        ArchiveLinkWorker(self.root).link_package(
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

    def delete_package(self, *, explicit: bool = False) -> bool:
        if not explicit:
            return False
        if self.paths.root.exists():
            shutil.rmtree(self.paths.root)
        return True

    def ref_writer(self) -> RefGraphWriter:
        return RefGraphWriter(self.paths.refs)

    def append_indexes_for_event(self, event: Any) -> int:
        payload = event.to_dict() if hasattr(event, "to_dict") else event
        if not isinstance(payload, dict):
            return 0
        rows = self._index_rows(payload)
        written = 0
        for name, row in rows:
            path = self.paths.indexes.get(name)
            if path is None:
                continue
            with path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            written += 1
        return written

    def write_pose_sidecar_for_event(self, event: Any) -> bool:
        payload = event.to_dict() if hasattr(event, "to_dict") else event
        if not isinstance(payload, dict) or payload.get("record_type") != "pose_observation":
            return False
        event_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        sidecar_payload = event_payload.get("_pose_sidecar_payload")
        refs = payload.get("refs") if isinstance(payload.get("refs"), dict) else {}
        sidecar_ref = str(refs.get("pose_sidecar_ref") or event_payload.get("pose_sidecar_ref") or "").strip()
        if not isinstance(sidecar_payload, dict) or not sidecar_ref:
            return False
        target = (self.paths.root / sidecar_ref).resolve()
        root = self.paths.root.resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"pose sidecar path escapes package root: {sidecar_ref}")
        target.parent.mkdir(parents=True, exist_ok=True)
        write_json(target, sidecar_payload)
        return True

    def write_writer_checkpoint(self, event: Any) -> None:
        payload = event.to_dict() if hasattr(event, "to_dict") else event
        if not isinstance(payload, dict):
            return
        write_json(
            self.paths.writer_checkpoint,
            {
                "package_id": self.package_id,
                "commit_state": "complete",
                "record_id": payload.get("record_id"),
                "record_type": payload.get("record_type"),
                "timestamp_ms": payload.get("timestamp_ms"),
                "updated_at_ms": now_ms(),
            },
        )

    def _manifest(self, state: str) -> MetadataPackageManifest:
        index_files = {name: f"indexes/{name}.jsonl" for name in INDEX_NAMES}
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
            index_files=index_files,
            contains_scheduler_trace=False,
            contains_raw_payload=False,
            sidecar_policy={
                "default_retention": "never_delete",
                "auto_delete_metadata": False,
                "auto_delete_sidecars": False,
                "require_explicit_delete": True,
                "keep_sync_checkpoints": True,
            },
            package_state=str(state),
            event_id=self.event_id,
            source_mode=self.source_mode,
            metadata_landing_mode=self.metadata_landing_mode,
            archive_managed=self.archive_managed,
            archive_link_timing=self.archive_link_timing,
        )

    def _index_rows(self, record: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        base = {
            "record_id": record.get("record_id"),
            "record_type": record.get("record_type"),
            "source_id": record.get("source_id"),
            "frame_id": record.get("frame_id"),
            "timestamp_ms": record.get("timestamp_ms"),
            "object_id": record.get("object_id"),
            "track_id": record.get("track_id"),
        }
        rows: list[tuple[str, dict[str, Any]]] = [("by_time", dict(base))]
        if record.get("frame_id") is not None:
            rows.append(("by_frame", dict(base)))
        if record.get("track_id"):
            rows.append(("by_track", dict(base)))
        if record.get("object_id"):
            rows.append(("by_object", dict(base)))
        refs = record.get("refs") if isinstance(record.get("refs"), dict) else {}
        if refs.get("hook_ref_id"):
            rows.append(("by_hook_ref", {**base, "hook_ref_id": refs.get("hook_ref_id")}))
        if refs.get("memory_ref"):
            rows.append(("by_memory_ref", {**base, "memory_ref": refs.get("memory_ref")}))
        return rows

    def _archive_managed(self) -> bool:
        mode = self.metadata_landing_mode
        source_mode = source_mode_or_default(self.source_mode)
        eligible = {source_mode_or_default(item) for item in self.eligible_source_modes}
        if mode == "disabled":
            return False
        if mode == "offline_only":
            return source_mode in eligible
        if mode == "all_sources":
            return True
        return False

    def _eligible_set(self, value: list[str] | tuple[str, ...] | str) -> set[str]:
        if isinstance(value, str):
            return {item.strip() for item in value.split(",") if item.strip()}
        return {str(item).strip() for item in value if str(item).strip()}
