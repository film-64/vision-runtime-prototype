from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Any

from .context import now_ms


ARCHIVE_REGISTRY_SCHEMA_VERSION = "metadata_archive_registry.v2"
HASH_REGISTRY_SCHEMA_VERSION = "source_hash_registry.v2"


_REGISTRY_LOCK = threading.Lock()


def atomic_write_json(path: str | Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    with tmp.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2, sort_keys=True)
        file.write("\n")
        file.flush()
        try:
            import os

            os.fsync(file.fileno())
        except OSError:
            pass
    tmp.replace(path)


def read_json_object(path: str | Path, default: dict[str, Any]) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        return dict(default)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else dict(default)
    except json.JSONDecodeError:
        return dict(default)


class EventRegistry:
    def __init__(self, root: str | Path, *, start_event_id: int = 10000):
        self.root = Path(root)
        self.path = self.root / "archive_registry.json"
        self.start_event_id = int(start_event_id)

    def allocate_event_id(self) -> int:
        with _REGISTRY_LOCK:
            registry = self._load()
            event_id = int(registry.get("next_event_id") or self.start_event_id)
            registry["next_event_id"] = event_id + 1
            registry["updated_at_ms"] = now_ms()
            atomic_write_json(self.path, registry)
            return event_id

    def record_latest(self, *, source_hash: str, latest_event_id: int, latest_package_id: str, latest_package_path: str, event_count: int) -> None:
        with _REGISTRY_LOCK:
            registry = self._load()
            registry.setdefault("latest_by_source_hash", {})[source_hash] = {
                "source_hash": source_hash,
                "latest_event_id": int(latest_event_id),
                "latest_package_id": str(latest_package_id),
                "latest_package_path": str(latest_package_path),
                "event_count": int(event_count),
                "updated_at_ms": now_ms(),
            }
            registry["updated_at_ms"] = now_ms()
            atomic_write_json(self.path, registry)

    def _load(self) -> dict[str, Any]:
        now = now_ms()
        return read_json_object(
            self.path,
            {
                "schema_version": ARCHIVE_REGISTRY_SCHEMA_VERSION,
                "next_event_id": self.start_event_id,
                "created_at_ms": now,
                "updated_at_ms": now,
                "latest_by_source_hash": {},
            },
        )
