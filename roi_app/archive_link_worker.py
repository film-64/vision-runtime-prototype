from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dynamic_pipeline.core.event_registry import read_json_object
from dynamic_pipeline.core.source_archive import SourceArchive
from dynamic_pipeline.core.source_fingerprint import SourceFingerprint


@dataclass(frozen=True)
class ArchiveLinkResult:
    linked: int = 0
    skipped: int = 0
    repaired: int = 0
    errors: tuple[str, ...] = ()


class ArchiveLinkWorker:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.archive = SourceArchive(self.root)

    def link_package(
        self,
        *,
        package_id: str,
        source_hash: str | None = None,
        package_root: str | Path | None = None,
        event_id: int | None = None,
        package_created_at_ms: int | None = None,
        fingerprint: SourceFingerprint | None = None,
        state: str = "closed",
    ) -> dict[str, Any]:
        package_root = Path(package_root) if package_root is not None else self.root / "packages" / str(package_id)
        if fingerprint is None:
            manifest = read_json_object(package_root / "manifest.json", {})
            fingerprint_payload = read_json_object(package_root / "source_fingerprint.json", {})
            fingerprint = self._fingerprint_from_payload(fingerprint_payload)
            if source_hash is not None and fingerprint.source_hash != str(source_hash):
                raise ValueError(f"source_hash mismatch for package {package_id}")
            event_id = int(event_id if event_id is not None else manifest.get("event_id"))
            package_created_at_ms = int(
                package_created_at_ms if package_created_at_ms is not None else manifest.get("created_at_ms") or 0
            )
            state = str(state or manifest.get("package_state") or "closed")
        if event_id is None:
            raise ValueError(f"event_id is required for package {package_id}")
        return self.archive.link_package(
            package_root=package_root,
            package_id=package_id,
            event_id=int(event_id),
            package_created_at_ms=int(package_created_at_ms or 0),
            fingerprint=fingerprint,
            state=state,
        )

    def repair_package(self, package_root: str | Path) -> ArchiveLinkResult:
        package_root = Path(package_root)
        manifest = read_json_object(package_root / "manifest.json", {})
        fingerprint = read_json_object(package_root / "source_fingerprint.json", {})
        if not manifest or not fingerprint:
            return ArchiveLinkResult(skipped=1, errors=("package_missing_manifest_or_fingerprint",))
        if not bool(manifest.get("archive_managed")):
            return ArchiveLinkResult(skipped=1)
        event_id = manifest.get("event_id")
        source_hash = str(fingerprint.get("source_hash") or "")
        if event_id is None or not source_hash:
            return ArchiveLinkResult(skipped=1, errors=("package_missing_event_id_or_source_hash",))
        source_fingerprint = self._fingerprint_from_payload(fingerprint)
        self.link_package(
            package_root=package_root,
            package_id=str(manifest.get("package_id") or package_root.name),
            source_hash=source_hash,
            event_id=int(event_id),
            package_created_at_ms=int(manifest.get("created_at_ms") or 0),
            fingerprint=source_fingerprint,
            state=str(manifest.get("package_state") or "closed"),
        )
        return ArchiveLinkResult(repaired=1)

    def repair_all(self) -> ArchiveLinkResult:
        packages_root = self.root / "packages"
        if not packages_root.is_dir():
            return ArchiveLinkResult()
        linked = 0
        skipped = 0
        repaired = 0
        errors: list[str] = []
        for package_root in sorted(path for path in packages_root.iterdir() if path.is_dir()):
            result = self.repair_package(package_root)
            linked += result.linked
            skipped += result.skipped
            repaired += result.repaired
            errors.extend(result.errors)
        return ArchiveLinkResult(linked=linked, skipped=skipped, repaired=repaired, errors=tuple(errors))

    def _fingerprint_from_payload(self, payload: dict[str, Any]) -> SourceFingerprint:
        source_hash = str(payload.get("source_hash") or "")
        if not source_hash:
            raise ValueError("source_fingerprint missing source_hash")
        return SourceFingerprint(
            schema_version=str(payload.get("schema_version") or "source_fingerprint.v1"),
            source_hash=source_hash,
            hash_algorithm=str(payload.get("hash_algorithm") or "sha256"),
            source_kind=str(payload.get("source_kind") or "video"),
            file_size_bytes=int(payload.get("file_size_bytes") or 0),
            mtime_ms=int(payload.get("mtime_ms") or 0),
            duration_ms=payload.get("duration_ms"),
            frame_count=payload.get("frame_count"),
            fps=payload.get("fps"),
            width=payload.get("width"),
            height=payload.get("height"),
            hash_completed_at_ms=int(payload.get("hash_completed_at_ms") or 0),
        )
