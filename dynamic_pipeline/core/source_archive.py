from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Any

from .context import now_ms
from .event_registry import EventRegistry, atomic_write_json, read_json_object
from .package_manifest import write_json
from .source_fingerprint import SourceFingerprint


_SOURCE_LOCKS: dict[str, threading.Lock] = {}
_SOURCE_LOCKS_GUARD = threading.Lock()


def source_hash_slug(source_hash: str) -> str:
    return str(source_hash).replace(":", "_").replace("/", "_")


def _source_lock(source_hash: str) -> threading.Lock:
    with _SOURCE_LOCKS_GUARD:
        return _SOURCE_LOCKS.setdefault(source_hash, threading.Lock())


class SourceArchive:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.archive_root = self.root / "archive" / "sources"
        self.hash_registry_path = self.root / "hash_registry.json"
        self.event_registry = EventRegistry(self.root)

    def resolve_by_hash(self, source_hash: str) -> dict[str, Any] | None:
        source_hash = str(source_hash or "")
        if not source_hash:
            return None
        registry_item = self._hash_registry_item(source_hash)
        source_archive_path = self._source_archive_path(source_hash, registry_item)
        if not source_archive_path.is_file():
            return None
        source_archive = read_json_object(source_archive_path, {})
        source_dir = source_archive_path.parent
        latest_event = read_json_object(source_dir / "latest_event.json", {})
        latest_aggregate_event = read_json_object(source_dir / "latest_aggregate_event.json", {})
        history = self._read_event_refs(source_dir / "event_refs.jsonl")
        return {
            "schema_version": "source_archive_resolution.v1",
            "source_hash": source_hash,
            "source_archive_path": self._relative_archive_path(source_archive_path),
            "source_archive": source_archive,
            "latest_event": latest_event,
            "latest_aggregate_event": latest_aggregate_event,
            "event_refs": history,
            "event_count": len(history),
            "registry_item": registry_item,
        }

    def history_for_hash(self, source_hash: str) -> list[dict[str, Any]]:
        resolved = self.resolve_by_hash(source_hash)
        if not resolved:
            return []
        return list(resolved.get("event_refs") or [])

    def set_latest_event(self, source_hash: str, event_id: int, *, reason: str = "explicit_writer") -> dict[str, Any]:
        source_hash = str(source_hash or "")
        with _source_lock(source_hash):
            source_archive_path = self._source_archive_path(source_hash, self._hash_registry_item(source_hash))
            if not source_archive_path.is_file():
                raise FileNotFoundError(f"source archive not found for {source_hash}")
            source_dir = source_archive_path.parent
            event_refs = self._read_event_refs(source_dir / "event_refs.jsonl")
            selected = None
            for row in event_refs:
                if int(row.get("event_id") or -1) == int(event_id):
                    selected = row
                    break
            if selected is None:
                raise ValueError(f"event_id {event_id} is not linked to {source_hash}")
            source_archive = read_json_object(source_archive_path, {})
            source_archive.update(
                {
                    "latest_event_id": int(selected["event_id"]),
                    "latest_package_id": str(selected["package_id"]),
                    "event_count": len(event_refs),
                    "last_seen_at_ms": now_ms(),
                }
            )
            latest_event = {
                "schema_version": "latest_event_ref.v1",
                "source_hash": source_hash,
                "latest_event_id": int(selected["event_id"]),
                "latest_package_id": str(selected["package_id"]),
                "latest_package_path": str(selected["package_path"]),
                "updated_at_ms": now_ms(),
                "reason": str(reason or "explicit_writer"),
            }
            atomic_write_json(source_archive_path, source_archive)
            atomic_write_json(source_dir / "latest_event.json", latest_event)
            self._update_hash_registry(
                source_hash=source_hash,
                source_archive_path=self._relative_archive_path(source_archive_path),
                first_event_id=int(source_archive.get("first_event_id") or event_refs[0]["event_id"]),
                latest_event_id=int(selected["event_id"]),
                latest_package_id=str(selected["package_id"]),
                latest_package_path=str(selected["package_path"]),
                event_count=len(event_refs),
                package_created_at_ms=int(selected.get("created_at_ms") or 0),
            )
            self.event_registry.record_latest(
                source_hash=source_hash,
                latest_event_id=int(selected["event_id"]),
                latest_package_id=str(selected["package_id"]),
                latest_package_path=str(selected["package_path"]),
                event_count=len(event_refs),
            )
            self._refresh_package_latest_flags(source_hash, event_refs, int(selected["event_id"]))
            return latest_event

    def set_latest_aggregate_event(
        self,
        source_hash: str,
        *,
        package_id: str,
        package_path: str | None = None,
        package_root: str | Path | None = None,
        reason: str = "aggregate_build",
    ) -> dict[str, Any]:
        source_hash = str(source_hash or "")
        package_id = str(package_id or "")
        if not source_hash or not package_id:
            raise ValueError("source_hash and package_id are required for latest aggregate event")
        with _source_lock(source_hash):
            source_archive_path = self._source_archive_path(source_hash, self._hash_registry_item(source_hash))
            if not source_archive_path.is_file():
                raise FileNotFoundError(f"source archive not found for {source_hash}")
            source_dir = source_archive_path.parent
            package_path = str(package_path or Path("packages") / package_id)
            now = now_ms()
            source_archive = read_json_object(source_archive_path, {})
            source_archive.update(
                {
                    "latest_aggregate_package_id": package_id,
                    "latest_aggregate_package_path": package_path,
                    "latest_aggregate_updated_at_ms": now,
                    "last_seen_at_ms": now,
                }
            )
            latest_aggregate_event = {
                "schema_version": "latest_aggregate_event_ref.v1",
                "source_hash": source_hash,
                "latest_package_id": package_id,
                "latest_package_path": package_path,
                "updated_at_ms": now,
                "reason": str(reason or "aggregate_build"),
            }
            atomic_write_json(source_archive_path, source_archive)
            atomic_write_json(source_dir / "latest_aggregate_event.json", latest_aggregate_event)
            self._update_hash_registry_aggregate(
                source_hash=source_hash,
                latest_aggregate_package_id=package_id,
                latest_aggregate_package_path=package_path,
            )
            if package_root is not None:
                link = {
                    "schema_version": "package_archive_link.v1",
                    "package_kind": "aggregate",
                    "package_id": package_id,
                    "source_hash": source_hash,
                    "source_archive_path": self._relative_archive_path(source_archive_path),
                    "is_latest_aggregate_for_source": True,
                    "linked_at_ms": now,
                }
                write_json(Path(package_root) / "archive_link.json", link)
            return latest_aggregate_event

    def rebuild_source_archive(self, source_hash: str, *, source_kind: str = "video") -> dict[str, Any] | None:
        source_hash = str(source_hash or "")
        if not source_hash:
            return None
        with _source_lock(source_hash):
            rows = self._scan_package_links(source_hash)
            if not rows:
                return None
            rows = self._dedupe_event_refs(rows)
            source_dir = self.archive_root / source_hash_slug(source_hash)
            source_dir.mkdir(parents=True, exist_ok=True)
            event_refs_path = source_dir / "event_refs.jsonl"
            with event_refs_path.open("w", encoding="utf-8") as file:
                for row in rows:
                    file.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            self._write_source_records(
                source_hash=source_hash,
                source_kind=source_kind,
                event_refs=rows,
                package_created_at_ms=int(rows[0].get("created_at_ms") or 0),
                state_reason="repair_rebuild",
                package_root=None,
                link_package_id=None,
                link_event_id=None,
            )
        aggregate_row = self._scan_latest_aggregate_link(source_hash)
        if aggregate_row is not None:
            self.set_latest_aggregate_event(
                source_hash,
                package_id=str(aggregate_row["package_id"]),
                package_path=str(aggregate_row["package_path"]),
                package_root=self.root / str(aggregate_row["package_path"]),
                reason="repair_rebuild",
            )
        return self.resolve_by_hash(source_hash)

    def link_package(
        self,
        *,
        package_root: str | Path,
        package_id: str,
        event_id: int,
        package_created_at_ms: int,
        fingerprint: SourceFingerprint,
        state: str = "closed",
    ) -> dict[str, Any]:
        source_hash = fingerprint.source_hash
        with _source_lock(source_hash):
            source_dir = self.archive_root / source_hash_slug(source_hash)
            source_dir.mkdir(parents=True, exist_ok=True)
            event_refs_path = source_dir / "event_refs.jsonl"
            event_refs = self._read_event_refs(event_refs_path)
            rel_package_path = str(Path("packages") / package_id)
            if not any(int(row.get("event_id") or -1) == int(event_id) for row in event_refs):
                event_refs.append(
                    {
                        "event_id": int(event_id),
                        "package_id": str(package_id),
                        "package_path": rel_package_path,
                        "created_at_ms": int(package_created_at_ms),
                        "state": str(state),
                    }
                )
                with event_refs_path.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(event_refs[-1], ensure_ascii=False, separators=(",", ":")) + "\n")
            return self._write_source_records(
                source_hash=source_hash,
                source_kind=fingerprint.source_kind,
                event_refs=event_refs,
                package_created_at_ms=package_created_at_ms,
                state_reason="package_closed",
                package_root=Path(package_root),
                link_package_id=str(package_id),
                link_event_id=int(event_id),
            )

    def _read_event_refs(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    rows.append(value)
        return self._dedupe_event_refs(rows)

    def _write_source_records(
        self,
        *,
        source_hash: str,
        source_kind: str,
        event_refs: list[dict[str, Any]],
        package_created_at_ms: int,
        state_reason: str,
        package_root: Path | None,
        link_package_id: str | None,
        link_event_id: int | None,
    ) -> dict[str, Any]:
        event_refs_sorted = self._dedupe_event_refs(event_refs)
        source_dir = self.archive_root / source_hash_slug(source_hash)
        source_archive_path = source_dir / "source_archive.json"
        latest_event_path = source_dir / "latest_event.json"
        existing = read_json_object(source_archive_path, {})
        first_event_id = int(event_refs_sorted[0]["event_id"])
        latest_row = event_refs_sorted[-1]
        latest_event_id = int(latest_row["event_id"])
        latest_package_id = str(latest_row["package_id"])
        latest_package_path = str(latest_row["package_path"])
        now = now_ms()
        source_archive = {
            "schema_version": "source_archive.v1",
            "source_hash": source_hash,
            "source_kind": source_kind,
            "first_event_id": first_event_id,
            "latest_event_id": latest_event_id,
            "latest_package_id": latest_package_id,
            "event_count": len(event_refs_sorted),
            "first_seen_at_ms": int(existing.get("first_seen_at_ms") or package_created_at_ms or now),
            "last_seen_at_ms": now,
        }
        latest_event = {
            "schema_version": "latest_event_ref.v1",
            "source_hash": source_hash,
            "latest_event_id": latest_event_id,
            "latest_package_id": latest_package_id,
            "latest_package_path": latest_package_path,
            "updated_at_ms": now,
            "reason": state_reason,
        }
        atomic_write_json(source_archive_path, source_archive)
        atomic_write_json(latest_event_path, latest_event)
        relative_archive_path = self._relative_archive_path(source_archive_path)
        self._update_hash_registry(
            source_hash=source_hash,
            source_archive_path=relative_archive_path,
            first_event_id=first_event_id,
            latest_event_id=latest_event_id,
            latest_package_id=latest_package_id,
            latest_package_path=latest_package_path,
            event_count=len(event_refs_sorted),
            package_created_at_ms=package_created_at_ms,
        )
        self.event_registry.record_latest(
            source_hash=source_hash,
            latest_event_id=latest_event_id,
            latest_package_id=latest_package_id,
            latest_package_path=latest_package_path,
            event_count=len(event_refs_sorted),
        )
        self._refresh_package_latest_flags(source_hash, event_refs_sorted, latest_event_id)
        if package_root is None or link_package_id is None or link_event_id is None:
            return source_archive
        link = {
            "schema_version": "package_archive_link.v1",
            "package_id": str(link_package_id),
            "event_id": int(link_event_id),
            "source_hash": source_hash,
            "source_archive_path": relative_archive_path,
            "is_latest_for_source": int(link_event_id) == latest_event_id,
            "linked_at_ms": now,
        }
        write_json(package_root / "archive_link.json", link)
        return link

    def _hash_registry_item(self, source_hash: str) -> dict[str, Any]:
        registry = read_json_object(
            self.hash_registry_path,
            {
                "schema_version": "source_hash_registry.v2",
                "hash_algorithm": "sha256",
                "items": {},
            },
        )
        item = (registry.get("items") or {}).get(source_hash, {})
        return item if isinstance(item, dict) else {}

    def _source_archive_path(self, source_hash: str, registry_item: dict[str, Any] | None = None) -> Path:
        registry_item = registry_item or {}
        configured = str(registry_item.get("source_archive_path") or "")
        if configured:
            return self.root / configured
        return self.archive_root / source_hash_slug(source_hash) / "source_archive.json"

    def _relative_archive_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)

    def _dedupe_event_refs(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_event: dict[int, dict[str, Any]] = {}
        for row in rows:
            try:
                event_id = int(row.get("event_id") or -1)
            except Exception:
                continue
            if event_id < 0:
                continue
            by_event[event_id] = {
                "event_id": event_id,
                "package_id": str(row.get("package_id") or ""),
                "package_path": str(row.get("package_path") or Path("packages") / str(row.get("package_id") or "")),
                "created_at_ms": int(row.get("created_at_ms") or 0),
                "state": str(row.get("state") or "closed"),
            }
        return [by_event[key] for key in sorted(by_event)]

    def _refresh_package_latest_flags(self, source_hash: str, event_refs: list[dict[str, Any]], latest_event_id: int) -> None:
        for row in event_refs:
            package_path = self.root / str(row.get("package_path") or "")
            link_path = package_path / "archive_link.json"
            if not link_path.is_file():
                continue
            link = read_json_object(link_path, {})
            if str(link.get("source_hash") or "") != source_hash:
                continue
            link["is_latest_for_source"] = int(row.get("event_id") or -1) == int(latest_event_id)
            atomic_write_json(link_path, link)

    def _scan_package_links(self, source_hash: str) -> list[dict[str, Any]]:
        packages_root = self.root / "packages"
        if not packages_root.is_dir():
            return []
        rows: list[dict[str, Any]] = []
        for link_path in sorted(packages_root.glob("*/archive_link.json")):
            link = read_json_object(link_path, {})
            if str(link.get("source_hash") or "") != source_hash:
                continue
            package_id = str(link.get("package_id") or link_path.parent.name)
            event_id = int(link.get("event_id") or -1)
            manifest = read_json_object(link_path.parent / "manifest.json", {})
            created_at_ms = int(manifest.get("created_at_ms") or 0)
            rows.append(
                {
                    "event_id": event_id,
                    "package_id": package_id,
                    "package_path": str(Path("packages") / package_id),
                    "created_at_ms": created_at_ms,
                    "state": str(manifest.get("package_state") or "closed"),
                }
            )
        return rows

    def _scan_latest_aggregate_link(self, source_hash: str) -> dict[str, Any] | None:
        packages_root = self.root / "packages"
        if not packages_root.is_dir():
            return None
        rows: list[dict[str, Any]] = []
        for link_path in sorted(packages_root.glob("*/archive_link.json")):
            link = read_json_object(link_path, {})
            if str(link.get("source_hash") or "") != source_hash:
                continue
            if str(link.get("package_kind") or "") != "aggregate":
                continue
            if not bool(link.get("is_latest_aggregate_for_source")):
                continue
            package_id = str(link.get("package_id") or link_path.parent.name)
            manifest = read_json_object(link_path.parent / "manifest.json", {})
            rows.append(
                {
                    "package_id": package_id,
                    "package_path": str(Path("packages") / package_id),
                    "created_at_ms": int(manifest.get("created_at_ms") or link.get("linked_at_ms") or 0),
                }
            )
        return rows[-1] if rows else None

    def _update_hash_registry(
        self,
        *,
        source_hash: str,
        source_archive_path: str,
        first_event_id: int,
        latest_event_id: int,
        latest_package_id: str,
        latest_package_path: str,
        event_count: int,
        package_created_at_ms: int,
    ) -> None:
        now = now_ms()
        registry = read_json_object(
            self.hash_registry_path,
            {
                "schema_version": "source_hash_registry.v2",
                "hash_algorithm": "sha256",
                "items": {},
            },
        )
        existing = (registry.get("items") or {}).get(source_hash, {})
        registry.setdefault("items", {})[source_hash] = {
            "source_hash": source_hash,
            "source_archive_path": source_archive_path,
            "first_event_id": int(existing.get("first_event_id") or first_event_id),
            "latest_event_id": int(latest_event_id),
            "latest_package_id": latest_package_id,
            "latest_package_path": latest_package_path,
            "event_count": int(event_count),
            "first_seen_at_ms": int(existing.get("first_seen_at_ms") or package_created_at_ms),
            "last_seen_at_ms": now,
        }
        atomic_write_json(self.hash_registry_path, registry)

    def _update_hash_registry_aggregate(
        self,
        *,
        source_hash: str,
        latest_aggregate_package_id: str,
        latest_aggregate_package_path: str,
    ) -> None:
        registry = read_json_object(
            self.hash_registry_path,
            {
                "schema_version": "source_hash_registry.v2",
                "hash_algorithm": "sha256",
                "items": {},
            },
        )
        item = dict((registry.get("items") or {}).get(source_hash, {}))
        item.update(
            {
                "source_hash": source_hash,
                "latest_aggregate_package_id": str(latest_aggregate_package_id),
                "latest_aggregate_package_path": str(latest_aggregate_package_path),
                "latest_aggregate_updated_at_ms": now_ms(),
            }
        )
        registry.setdefault("items", {})[source_hash] = item
        atomic_write_json(self.hash_registry_path, registry)
