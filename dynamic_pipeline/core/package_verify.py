from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

import yaml

from .metadata_jsonl import MetadataReplayReader
from .package_manifest import PACKAGE_SCHEMA_VERSION
from .protocol_bundle import file_sha256
from .source_fingerprint import fingerprint_file


@dataclass
class PackageVerifyResult:
    ok: bool
    package_root: str
    package_id: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    hashes: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_package(package_root: str | Path, *, source_path: str | Path | None = None) -> PackageVerifyResult:
    root = Path(package_root)
    result = PackageVerifyResult(ok=False, package_root=str(root))
    manifest = _load_json(root / "manifest.json", result, "manifest")
    if manifest:
        result.package_id = str(manifest.get("package_id") or "")
        _verify_manifest(root, manifest, result)

    metadata_file = str(manifest.get("metadata_file") or "metadata.jsonl") if manifest else "metadata.jsonl"
    refs_file = str(manifest.get("refs_file") or "refs.jsonl") if manifest else "refs.jsonl"
    paste_rules_file = str(manifest.get("paste_rules_file") or "paste_rules.yaml") if manifest else "paste_rules.yaml"

    record_ids = _verify_metadata(root / metadata_file, result)
    _verify_refs(root / refs_file, result)
    _verify_paste_rules(root / paste_rules_file, result)
    _record_package_file_hashes(root, manifest, result)
    _verify_indexes(root, manifest, record_ids, result)
    _verify_source_hash(root, source_path, result)
    _verify_archive_link(root, result)

    result.ok = not result.errors
    return result


def _verify_manifest(root: Path, manifest: dict[str, Any], result: PackageVerifyResult) -> None:
    if manifest.get("schema_version") != PACKAGE_SCHEMA_VERSION:
        result.errors.append("manifest:schema_version")
    if manifest.get("package_id") != root.name:
        result.errors.append("manifest:package_id_mismatch")
    for key in ("metadata_file", "refs_file", "paste_rules_file"):
        if not manifest.get(key):
            result.errors.append(f"manifest:missing_{key}")


def _verify_metadata(path: Path, result: PackageVerifyResult) -> set[str]:
    record_ids: set[str] = set()
    if not path.is_file():
        result.errors.append(f"missing:{path.name}")
        return record_ids
    summary = MetadataReplayReader(path).read_summary()
    result.counts["metadata_records"] = summary.records_read
    result.counts["metadata_bad_jsonl_lines"] = summary.bad_jsonl_lines
    result.counts["metadata_frames"] = summary.frame_count()
    result.counts["metadata_objects"] = summary.object_count()
    result.counts["metadata_patches"] = sum(len(items) for items in summary.patches_by_object.values())
    if summary.bad_jsonl_lines:
        result.errors.append("metadata:bad_jsonl")
    previous_record_ids: set[str] = set()
    for _line_number, record, error in MetadataReplayReader(path).iter_records():
        if error or not isinstance(record, dict):
            continue
        record_id = str(record.get("record_id") or "")
        if not record_id:
            result.errors.append("metadata:missing_record_id")
            continue
        if record_id in previous_record_ids:
            result.errors.append(f"metadata:duplicate_record_id:{record_id}")
        previous_record_ids.add(record_id)
        record_ids.add(record_id)
        timeline = record.get("timeline") if isinstance(record.get("timeline"), dict) else {}
        if timeline and str(timeline.get("record_id") or "") != record_id:
            result.errors.append(f"metadata:timeline_record_id_mismatch:{record_id}")
        if str(record.get("schema_version") or "") != "durable_metadata.v1":
            result.errors.append(f"metadata:schema_version:{record_id}")
    return record_ids


def _verify_refs(path: Path, result: PackageVerifyResult) -> None:
    if not path.is_file():
        result.errors.append(f"missing:{path.name}")
        return
    rows = 0
    bad = 0
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            rows += 1
            try:
                json.loads(line)
            except json.JSONDecodeError:
                bad += 1
    result.counts["refs"] = rows
    if bad:
        result.errors.append("refs:bad_jsonl")


def _verify_paste_rules(path: Path, result: PackageVerifyResult) -> None:
    if not path.is_file():
        result.errors.append(f"missing:{path.name}")
        return
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        result.errors.append("paste_rules:bad_yaml")
        return
    if not isinstance(data, dict) or data.get("schema_version") != "paste_rules.v1":
        result.errors.append("paste_rules:schema_version")


def _verify_indexes(root: Path, manifest: dict[str, Any], record_ids: set[str], result: PackageVerifyResult) -> None:
    index_files = manifest.get("index_files") if isinstance(manifest.get("index_files"), dict) else {}
    for name, rel_path in index_files.items():
        path = root / str(rel_path)
        if not path.is_file():
            result.errors.append(f"missing:{rel_path}")
            continue
        rows = 0
        bad = 0
        unknown_refs = 0
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                rows += 1
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    bad += 1
                    continue
                row_record_id = str(row.get("record_id") or "")
                if row_record_id and record_ids and row_record_id not in record_ids:
                    unknown_refs += 1
        result.counts[f"index_{name}"] = rows
        if bad:
            result.errors.append(f"index:{name}:bad_jsonl")
        if unknown_refs:
            result.errors.append(f"index:{name}:unknown_record_id")


def _verify_source_hash(root: Path, source_path: str | Path | None, result: PackageVerifyResult) -> None:
    fingerprint_path = root / "source_fingerprint.json"
    fingerprint = _load_json(fingerprint_path, result, "source_fingerprint", missing_ok=True)
    if not fingerprint:
        result.warnings.append("source_hash:not_recorded")
        return
    recorded_hash = str(fingerprint.get("source_hash") or "")
    result.hashes["source_hash"] = recorded_hash
    if not source_path:
        result.warnings.append("source_hash:not_recomputed")
        return
    source = Path(source_path)
    if not source.is_file():
        result.errors.append("source_hash:source_missing")
        return
    computed = fingerprint_file(source, source_kind=str(fingerprint.get("source_kind") or "video"))
    result.hashes["source_hash_computed"] = computed.source_hash
    if computed.source_hash != recorded_hash:
        result.errors.append("source_hash:mismatch")


def _verify_archive_link(root: Path, result: PackageVerifyResult) -> None:
    link_path = root / "archive_link.json"
    if not link_path.is_file():
        result.warnings.append("archive_link:not_recorded")
        return
    link = _load_json(link_path, result, "archive_link")
    if not link:
        return
    link_hash = str(link.get("source_hash") or "")
    if result.hashes.get("source_hash") and link_hash != result.hashes["source_hash"]:
        result.errors.append("archive_link:source_hash_mismatch")
    archive_path = root.parents[1] / str(link.get("source_archive_path") or "")
    if not archive_path.is_file():
        result.errors.append("archive_link:source_archive_missing")


def _record_package_file_hashes(root: Path, manifest: dict[str, Any], result: PackageVerifyResult) -> None:
    file_map = {
        "manifest_hash": "manifest.json",
        "metadata_hash": str(manifest.get("metadata_file") or "metadata.jsonl"),
        "refs_hash": str(manifest.get("refs_file") or "refs.jsonl"),
        "paste_rules_hash": str(manifest.get("paste_rules_file") or "paste_rules.yaml"),
        "source_fingerprint_hash": "source_fingerprint.json",
        "archive_link_hash": "archive_link.json",
    }
    for key, rel_path in file_map.items():
        path = root / rel_path
        if path.is_file():
            result.hashes[key] = f"sha256:{file_sha256(path)}"


def _load_json(path: Path, result: PackageVerifyResult, name: str, *, missing_ok: bool = False) -> dict[str, Any]:
    if not path.is_file():
        if not missing_ok:
            result.errors.append(f"missing:{path.name}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        result.errors.append(f"{name}:bad_json")
        return {}
    if not isinstance(value, dict):
        result.errors.append(f"{name}:not_object")
        return {}
    return value
