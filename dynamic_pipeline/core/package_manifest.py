from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from pathlib import Path
from typing import Any

from .context import now_ms
from .event_registry import atomic_write_json


PACKAGE_SCHEMA_VERSION = "metadata_package.v1"
PACKAGE_ID_RE = re.compile(r"[^a-zA-Z0-9_-]+")


def slug_safe(value: str) -> str:
    slug = PACKAGE_ID_RE.sub("_", str(value or "").strip()).strip("_").lower()
    return slug[:80]


def default_package_id(*, event_id: str | int, timestamp_ms: int | None = None, description: str | None = None) -> str:
    import datetime as _dt

    timestamp = int(timestamp_ms if timestamp_ms is not None else now_ms())
    prefix = _dt.datetime.fromtimestamp(timestamp / 1000.0, tz=_dt.timezone.utc).strftime("%Y%m%d%H%M")
    package_id = f"{prefix}_{slug_safe(event_id) or 'event'}"
    description_slug = slug_safe(description or "")
    return f"{package_id}_{description_slug}" if description_slug else package_id


@dataclass
class MetadataPackageManifest:
    schema_version: str
    package_id: str
    display_name: str
    created_at_ms: int
    updated_at_ms: int
    recording_id: str
    source_id: str
    root_kind: str
    metadata_file: str
    paste_rules_file: str
    refs_file: str
    index_files: dict[str, str] = field(default_factory=dict)
    contains_scheduler_trace: bool = False
    contains_raw_payload: bool = False
    sidecar_policy: dict[str, Any] = field(default_factory=dict)
    package_state: str = "open"
    event_id: int | None = None
    source_mode: str = ""
    metadata_landing_mode: str = ""
    archive_managed: bool = False
    archive_link_timing: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    atomic_write_json(path, payload)
