from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PackageIdentity:
    event_id: int | None
    package_id: str
    package_root: Path
    created_at_ms: int
    source_mode: str
    metadata_landing_mode: str
    archive_managed: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["package_root"] = str(self.package_root)
        return payload
