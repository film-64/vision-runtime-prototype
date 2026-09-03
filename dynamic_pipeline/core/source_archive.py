from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Any

from .context import now_ms
from .event_registry import EventRegistry, atomic_write_json, read_json_object
from .package_manifest import write_json
from .source_fingerprint import SourceFingerprint

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def source_hash_slug(source_hash: str) -> str:
    return str(source_hash).replace(":", "_").replace("/", "_")


def _lock(source_hash: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(source_hash, threading.Lock())


class SourceArchive:
    """Small hash-indexed archive used by the public metadata evidence path."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.archive_root = self.root / "archive" / "sources"
        self.hash_registry_path = self.root / "hash_registry.json"
        self.event_registry = EventRegistry(self.root)

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
        with _lock(source_hash):
            source_dir = self.archive_root / source_hash_slug(source_hash)
            source_dir.mkdir(parents=True, exist_ok=True)
            refs_path = source_dir / "event_refs.jsonl"
            rows = self._read_refs(refs_path)
            package_path = str(Path("packages") / package_id)
            if not any(int(row.get("event_id", -1)) == int(event_id) for row in rows):
                row = {
                    "event_id": int(event_id),
                    "package_id": str(package_id),
                    "package_path": package_path,
                    "created_at_ms": int(package_created_at_ms),
                    "state": str(state),
                }
                with refs_path.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                rows.append(row)
            rows.sort(key=lambda item: int(item["event_id"]))
            latest = rows[-1]
            now = now_ms()
            source_archive_path = source_dir / "source_archive.json"
            source_archive = {
                "schema_version": "source_archive.v1",
                "source_hash": source_hash,
                "source_kind": fingerprint.source_kind,
                "first_event_id": int(rows[0]["event_id"]),
                "latest_event_id": int(latest["event_id"]),
                "latest_package_id": str(latest["package_id"]),
                "event_count": len(rows),
                "first_seen_at_ms": int(rows[0].get("created_at_ms") or now),
                "last_seen_at_ms": now,
            }
            latest_event = {
                "schema_version": "latest_event_ref.v1",
                "source_hash": source_hash,
                "latest_event_id": int(latest["event_id"]),
                "latest_package_id": str(latest["package_id"]),
                "latest_package_path": str(latest["package_path"]),
                "updated_at_ms": now,
                "reason": "package_closed",
            }
            atomic_write_json(source_archive_path, source_archive)
            atomic_write_json(source_dir / "latest_event.json", latest_event)
            relative_archive = str(source_archive_path.relative_to(self.root))
            registry = read_json_object(
                self.hash_registry_path,
                {"schema_version": "source_hash_registry.v2", "hash_algorithm": "sha256", "items": {}},
            )
            registry.setdefault("items", {})[source_hash] = {
                "source_hash": source_hash,
                "source_archive_path": relative_archive,
                "first_event_id": int(rows[0]["event_id"]),
                "latest_event_id": int(latest["event_id"]),
                "latest_package_id": str(latest["package_id"]),
                "latest_package_path": str(latest["package_path"]),
                "event_count": len(rows),
                "last_seen_at_ms": now,
            }
            atomic_write_json(self.hash_registry_path, registry)
            self.event_registry.record_latest(
                source_hash=source_hash,
                latest_event_id=int(latest["event_id"]),
                latest_package_id=str(latest["package_id"]),
                latest_package_path=str(latest["package_path"]),
                event_count=len(rows),
            )
            link = {
                "schema_version": "package_archive_link.v1",
                "package_id": str(package_id),
                "event_id": int(event_id),
                "source_hash": source_hash,
                "source_archive_path": relative_archive,
                "is_latest_for_source": int(event_id) == int(latest["event_id"]),
                "linked_at_ms": now,
            }
            write_json(Path(package_root) / "archive_link.json", link)
            return link

    def resolve_by_hash(self, source_hash: str) -> dict[str, Any] | None:
        item = (read_json_object(self.hash_registry_path, {}).get("items") or {}).get(str(source_hash))
        if not isinstance(item, dict):
            return None
        archive_path = self.root / str(item.get("source_archive_path") or "")
        if not archive_path.is_file():
            return None
        source_dir = archive_path.parent
        return {
            "source_hash": str(source_hash),
            "source_archive": read_json_object(archive_path, {}),
            "latest_event": read_json_object(source_dir / "latest_event.json", {}),
            "event_refs": self._read_refs(source_dir / "event_refs.jsonl"),
        }

    @staticmethod
    def _read_refs(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        output = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                output.append(value)
        return output
