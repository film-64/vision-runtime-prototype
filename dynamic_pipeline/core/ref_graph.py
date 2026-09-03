from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Iterable


REF_KEYS = {"hook_ref_id", "public_artifact_ref", "sidecar_ref", "memory_ref", "source_ref", "patch_ref"}


@dataclass(frozen=True)
class RefGraphEdge:
    source_record_id: str
    ref_type: str
    ref_value: Any
    target_record_id: str | None = None
    status: str = "unresolved"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def edges_from_event(event: Any) -> list[RefGraphEdge]:
    payload = event.to_dict() if hasattr(event, "to_dict") else event
    if not isinstance(payload, dict):
        return []
    record_id = str(payload.get("record_id") or "")
    refs = payload.get("refs") if isinstance(payload.get("refs"), dict) else {}
    edges: list[RefGraphEdge] = []
    for key, value in refs.items():
        if key not in REF_KEYS or value is None:
            continue
        edges.append(RefGraphEdge(source_record_id=record_id, ref_type=str(key), ref_value=value))
    return edges


class RefGraphWriter:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append_edges(self, edges: Iterable[RefGraphEdge]) -> int:
        count = 0
        with self.path.open("a", encoding="utf-8") as file:
            for edge in edges:
                file.write(json.dumps(edge.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n")
                count += 1
        return count

    def append_event_refs(self, event: Any) -> int:
        return self.append_edges(edges_from_event(event))
