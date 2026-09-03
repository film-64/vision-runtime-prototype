from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Iterable

from .context import new_id, now_ms


PORTABLE_FILES = (
    "manifest.json",
    "metadata.jsonl",
    "refs.jsonl",
    "paste_rules.yaml",
    "indexes/by_frame.jsonl",
    "indexes/by_track.jsonl",
    "indexes/by_object.jsonl",
    "indexes/by_hook_ref.jsonl",
    "indexes/by_memory_ref.jsonl",
    "indexes/by_time.jsonl",
)


@dataclass
class BundleManifest:
    bundle_schema: str
    bundle_id: str
    bundle_type: str
    package_id: str
    created_at_ms: int
    base_checkpoint: int
    last_sequence_id: int
    contains_scheduler_trace: bool
    contains_raw_payload: bool
    files: list[str] = field(default_factory=list)
    checksums: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_bundle(
    package_root: str | Path,
    bundle_root: str | Path,
    *,
    bundle_type: str = "portable",
    include_sidecars: Iterable[str] | None = None,
    include_scheduler_trace: bool = False,
) -> BundleManifest:
    package_root = Path(package_root)
    bundle_root = Path(bundle_root)
    bundle_type = str(bundle_type)
    if bundle_type == "portable" and include_scheduler_trace:
        raise ValueError("portable bundle must not include scheduler trace")
    package_id = package_root.name
    bundle_id = new_id(f"{bundle_type}_bundle")
    output_dir = bundle_root / bundle_id
    output_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for rel in PORTABLE_FILES:
        src = package_root / rel
        if src.is_file():
            dst = output_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(rel)
    if include_sidecars:
        for rel in include_sidecars:
            src = package_root / rel
            if src.is_file():
                dst = output_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied.append(str(rel))
    if include_scheduler_trace:
        rel = "local/local_scheduler_trace.jsonl"
        src = package_root / rel
        if src.is_file():
            dst = output_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(rel)
    manifest = BundleManifest(
        bundle_schema="metadata_bundle.v1",
        bundle_id=bundle_id,
        bundle_type=bundle_type,
        package_id=package_id,
        created_at_ms=now_ms(),
        base_checkpoint=0,
        last_sequence_id=_last_sequence_id(package_root / "metadata.jsonl"),
        contains_scheduler_trace=include_scheduler_trace,
        contains_raw_payload=False,
        files=sorted(copied),
        checksums={rel: file_sha256(output_dir / rel) for rel in copied if (output_dir / rel).is_file()},
    )
    (output_dir / "bundle_manifest.json").write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify_bundle(bundle_dir: str | Path) -> tuple[bool, list[str]]:
    bundle_dir = Path(bundle_dir)
    manifest_path = bundle_dir / "bundle_manifest.json"
    if not manifest_path.is_file():
        return False, ["missing_bundle_manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for rel, expected in (manifest.get("checksums") or {}).items():
        path = bundle_dir / rel
        if not path.is_file():
            errors.append(f"missing:{rel}")
        elif file_sha256(path) != expected:
            errors.append(f"checksum:{rel}")
    return not errors, errors


def _last_sequence_id(path: Path) -> int:
    if not path.is_file():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                count += 1
    return count
