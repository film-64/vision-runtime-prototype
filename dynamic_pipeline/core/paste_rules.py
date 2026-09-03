from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


PASTE_RULES_SCHEMA_VERSION = "paste_rules.v1"


def default_paste_rules(package_id: str) -> dict[str, Any]:
    return {
        "schema_version": PASTE_RULES_SCHEMA_VERSION,
        "package_id": str(package_id),
        "views": {
            "frame_timeline": {
                "source": "metadata",
                "group_by": "frame_id",
                "order_by": "timestamp_ms",
                "attach": ["objects", "display_summary", "hook_refs"],
            },
            "track_timeline": {
                "source": "metadata",
                "group_by": "track_id",
                "order_by": "timestamp_ms",
                "attach": ["object_observations", "accepted_patches", "hook_refs", "memory_refs"],
            },
            "object_card": {
                "source": "metadata",
                "key": "object_id",
                "attach": ["latest_display_summary", "verified_summary", "unresolved_refs"],
            },
            "aggregate_overview": {
                "source": "metadata",
                "group_by": "source_frame_index",
                "order_by": "source_frame_index",
                "attach": ["layers", "fusion_groups", "coverage_summary"],
            },
        },
        "ref_resolution": {
            "hook_ref": {
                "required": False,
                "missing_behavior": "unresolved_marker",
                "search": ["refs.jsonl", "indexes/by_hook_ref.jsonl", "sidecars/"],
            },
            "sidecar_ref": {"required": False, "missing_behavior": "placeholder"},
            "memory_ref": {"required": False, "missing_behavior": "pending_recall"},
        },
        "redaction": {
            "default": "portable",
            "include_scheduler_trace": False,
            "include_raw_payload": False,
        },
    }


def write_paste_rules(path: str | Path, package_id: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(default_paste_rules(package_id), sort_keys=False), encoding="utf-8")


@dataclass(frozen=True)
class PasteRules:
    package_id: str
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "PasteRules":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return cls(package_id="", raw={})
        return cls(package_id=str(data.get("package_id") or ""), raw=data)

    def mode_allows_scheduler_trace(self, mode: str) -> bool:
        return str(mode) == "debug" and bool((self.raw.get("redaction") or {}).get("include_scheduler_trace", False))
