#!/usr/bin/env python3
"""Generate a public, synthetic metadata end-to-end verification package."""

from __future__ import annotations

import argparse
import hashlib
from importlib import metadata as importlib_metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dynamic_pipeline.core.context import BoxSet, FrameContext, ObjectContext, RawCandidate
from dynamic_pipeline.core.metadata import MetadataPatch
from dynamic_pipeline.core.metadata_jsonl import MetadataReplayReader
from dynamic_pipeline.core.runtime_projection import RuntimeProjectionBuilder
from roi_app.metadata_committer import MetadataCommitter
from roi_app.metadata_package_manager import MetadataPackageManager
from roi_app.replay_runtime import ReplayRuntime


EVIDENCE_KIND = "current_synthetic_verification"
DEFAULT_OUTPUT = REPO_ROOT / "docs/evidence/current-synthetic-metadata-e2e"
MARKER_NAME = ".public-synthetic-evidence-root"
SOURCE_NAME = "synthetic-input.ppm"
EXPECTED_FRAME_COUNT = 3
EXPECTED_OBJECT_COUNT = 4
EXPECTED_RECORD_COUNT = 9
RUNTIME_INTERNAL_SENTINELS = (
    "admission_decision_id",
    "local_scheduler_trace",
    "queue_pressure",
)
CORE_IMPLEMENTATION_FILES = (
    "roi_app/metadata_package_manager.py",
    "roi_app/metadata_committer.py",
    "dynamic_pipeline/core/runtime_projection.py",
    "dynamic_pipeline/core/metadata_jsonl.py",
    "dynamic_pipeline/core/package_verify.py",
    "dynamic_pipeline/core/source_archive.py",
    "roi_app/replay_runtime.py",
)


class EvidenceGenerationError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Evidence root to replace. Existing directories require the generator marker.",
    )
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def prepare_output_root(output_root: Path) -> None:
    if output_root.exists():
        marker = output_root / MARKER_NAME
        if not marker.is_file():
            raise EvidenceGenerationError(f"refusing to replace unmarked directory: {output_root}")
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    (output_root / MARKER_NAME).write_text(
        "Generated only by scripts/generate_public_evidence.py\n",
        encoding="utf-8",
    )


def generate_synthetic_ppm(path: Path, *, width: int = 96, height: int = 64) -> None:
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            red = (x * 3 + y) % 256
            green = (y * 5 + x // 2) % 256
            blue = ((x // 12 + y // 8) % 2) * 180 + 32
            pixels.extend((red, green, min(255, blue)))
    path.write_bytes(f"P6\n{width} {height}\n255\n".encode("ascii") + bytes(pixels))


def synthetic_object(
    *,
    frame_id: int,
    object_index: int,
    track_id: str,
    frame_box: list[float],
    class_name: str,
) -> ObjectContext:
    object_id = f"synthetic_object_f{frame_id:03d}_{object_index}"
    obj = ObjectContext(
        object_id=object_id,
        frame_id=frame_id,
        source_id="public_synthetic_source",
        frame_size=(96, 64),
        boxes=BoxSet.from_frame_box(frame_box, (96, 64)),
        raw_candidate=RawCandidate(
            producer="public_synthetic_input_generator",
            class_name=class_name,
            confidence=1.0,
            prompt_names=[class_name],
            attributes={"synthetic": True},
        ),
        track_id=track_id,
        source_track_id=track_id,
        track_version=0,
        detector_index=frame_id,
        source_detector_index=frame_id,
        deadline_detector_index=frame_id,
    )
    obj.runtime.source_row.update(
        {
            "admission_decision_id": "synthetic_non_portable_sentinel",
            "queue_pressure": 0.5,
            "local_scheduler_trace": [{"synthetic": True}],
        }
    )
    return obj


def synthetic_frames() -> list[FrameContext]:
    definitions = (
        (("track_alpha", [8, 10, 30, 34], "synthetic_red_block"),),
        (
            ("track_alpha", [12, 10, 34, 34], "synthetic_red_block"),
            ("track_beta", [56, 18, 82, 46], "synthetic_blue_block"),
        ),
        (("track_beta", [52, 18, 78, 46], "synthetic_blue_block"),),
    )
    frames: list[FrameContext] = []
    for frame_id, objects in enumerate(definitions, start=1):
        frame_objects = [
            synthetic_object(
                frame_id=frame_id,
                object_index=index,
                track_id=track_id,
                frame_box=list(frame_box),
                class_name=class_name,
            )
            for index, (track_id, frame_box, class_name) in enumerate(objects, start=1)
        ]
        frames.append(
            FrameContext(
                frame_id=frame_id,
                source_id="public_synthetic_source",
                timestamp_ms=(frame_id - 1) * 100,
                frame_width=96,
                frame_height=64,
                pixel_format="RGB",
                platform={"kind": "synthetic_public_fixture"},
                objects=frame_objects,
                detector_index=frame_id,
                source_frame_index=frame_id - 1,
                source_pts_ms=float((frame_id - 1) * 100),
                sample_index=frame_id - 1,
            )
        )
    return frames


def synthetic_patches(frames: list[FrameContext]) -> list[MetadataPatch]:
    first = frames[1].objects[0]
    second = frames[1].objects[1]
    return [
        MetadataPatch(
            producer="public_synthetic_evidence_harness",
            bucket="color",
            frame_id=2,
            source_id=first.source_id,
            object_id=first.object_id,
            track_id=first.track_id,
            patch_id="synthetic_patch_color_alpha",
            created_at_ms=100,
            patch={
                "verified": {
                    "color": {
                        "status": "matched",
                        "label": "synthetic_red",
                        "score": 1.0,
                        "producer": "public_synthetic_evidence_harness",
                        "attributes": {
                            "hook_ref_id": "synthetic_hook_alpha",
                            "public_artifact_ref": "synthetic_artifact_alpha",
                        },
                    }
                }
            },
        ),
        MetadataPatch(
            producer="public_synthetic_evidence_harness",
            bucket="color",
            frame_id=2,
            source_id=second.source_id,
            object_id=second.object_id,
            track_id=second.track_id,
            patch_id="synthetic_patch_color_beta",
            created_at_ms=100,
            patch={
                "verified": {
                    "color": {
                        "status": "matched",
                        "label": "synthetic_blue",
                        "score": 1.0,
                        "producer": "public_synthetic_evidence_harness",
                        "attributes": {"memory_ref": "synthetic_memory_beta"},
                    }
                }
            },
        ),
    ]


def create_package(output_root: Path, source_path: Path) -> tuple[MetadataPackageManager, dict[str, Any]]:
    manager = MetadataPackageManager(
        output_root,
        source_id="public_synthetic_source",
        source_mode="Offline",
        metadata_landing_mode="offline_only",
        eligible_source_modes=("Offline",),
        archive_link_timing="post_close_idle",
        source_path=source_path,
        source_kind="synthetic_ppm",
        description="current_synthetic_verification",
    )
    committer = MetadataCommitter(manager, enabled=True, queue_capacity=32, flush_records=1)
    builder = RuntimeProjectionBuilder(manager.recording_id)
    frames = synthetic_frames()
    events = []
    for frame in frames:
        events.append(builder.project_frame(frame))
        events.extend(builder.project_object(obj, frame) for obj in frame.objects)
    events.extend(builder.project_patch(patch) for patch in synthetic_patches(frames))
    if any(event is None for event in events):
        raise EvidenceGenerationError("runtime projection returned an empty event")
    try:
        submitted = [committer.submit(event) for event in events]
        if not all(submitted):
            raise EvidenceGenerationError("metadata committer rejected a generated portable event")
    finally:
        committer.shutdown(timeout_s=5.0)
    status = committer.status().to_dict()
    if status["mode"] != "open" or status["records_written"] != EXPECTED_RECORD_COUNT:
        raise EvidenceGenerationError(f"metadata committer did not close cleanly: {status}")
    return manager, status


def run_real_verifier(output_root: Path, manager: MetadataPackageManager, source_path: Path) -> dict[str, Any]:
    package_rel = manager.paths.root.relative_to(output_root)
    source_rel = source_path.relative_to(output_root)
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools/package_verify.py"),
            str(package_rel),
            "--source",
            str(source_rel),
        ],
        cwd=output_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.stdout.strip():
        (output_root / "verify-result.json").write_text(result.stdout, encoding="utf-8")
    if result.returncode != 0:
        raise EvidenceGenerationError(
            f"package verifier failed with exit {result.returncode}: {result.stderr.strip() or result.stdout.strip()}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise EvidenceGenerationError("package verifier did not emit JSON") from exc
    if not payload.get("ok"):
        raise EvidenceGenerationError(f"package verifier reported failure: {payload}")
    if payload.get("hashes", {}).get("source_hash") != payload.get("hashes", {}).get("source_hash_computed"):
        raise EvidenceGenerationError("package verifier did not reproduce the source hash")
    return payload


def run_real_replay(manager: MetadataPackageManager) -> dict[str, Any]:
    status_messages: list[str] = []
    app = SimpleNamespace(
        config={
            "replay_package_path": str(manager.paths.root.resolve()),
            "video_display_fps": "10",
            "video_loop": "false",
        },
        set_status=status_messages.append,
    )
    runtime = ReplayRuntime(app)
    if not runtime.ensure_loaded():
        raise EvidenceGenerationError(f"ReplayRuntime failed to load package: {status_messages}")
    replayed = []
    while runtime.index < len(runtime.frames):
        frame = runtime.next_frame_context()
        if frame is None:
            raise EvidenceGenerationError("ReplayRuntime returned no frame before reaching the end")
        replayed.append(frame)
    payload = {
        "evidence_kind": EVIDENCE_KIND,
        "synthetic": True,
        "model_inference_performed": False,
        "runtime_class": f"{ReplayRuntime.__module__}.{ReplayRuntime.__name__}",
        "loaded": True,
        "frame_count": len(replayed),
        "object_count": sum(len(frame.objects) for frame in replayed),
        "frame_ids": [frame.frame_id for frame in replayed],
        "objects_by_frame": [
            {
                "frame_id": frame.frame_id,
                "object_ids": [obj.object_id for obj in frame.objects],
                "display_labels": [obj.display.label for obj in frame.objects],
            }
            for frame in replayed
        ],
        "status_messages": status_messages,
    }
    if payload["frame_count"] != EXPECTED_FRAME_COUNT or payload["object_count"] != EXPECTED_OBJECT_COUNT:
        raise EvidenceGenerationError(f"ReplayRuntime reconstructed unexpected counts: {payload}")
    return payload


def package_version(name: str) -> str | None:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return None


def git_value(*args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def environment_payload() -> dict[str, Any]:
    status = git_value("status", "--porcelain") or ""
    return {
        "evidence_kind": EVIDENCE_KIND,
        "synthetic": True,
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "platform": platform.platform(),
        "packages": {
            name: package_version(name)
            for name in ("numpy", "Pillow", "PyYAML", "pytest", "vision-product")
        },
        "git": {
            "head": git_value("rev-parse", "HEAD"),
            "branch": git_value("branch", "--show-current"),
            "worktree_clean": not bool(status),
            "changed_paths_omitted": True,
        },
        "implementation_sha256": {
            path: sha256_file(REPO_ROOT / path)
            for path in (*CORE_IMPLEMENTATION_FILES, "scripts/generate_public_evidence.py")
        },
    }


def assert_package_invariants(manager: MetadataPackageManager, verifier: dict[str, Any]) -> dict[str, Any]:
    manifest = json.loads(manager.paths.manifest.read_text(encoding="utf-8"))
    metadata_text = manager.paths.metadata.read_text(encoding="utf-8")
    replay_summary = MetadataReplayReader(manager.paths.metadata).read_summary().to_dict()
    failures = []
    if manifest.get("package_state") != "closed":
        failures.append("manifest_not_closed")
    if replay_summary["records_read"] != EXPECTED_RECORD_COUNT:
        failures.append("unexpected_record_count")
    if replay_summary["bad_jsonl_lines"] != 0:
        failures.append("bad_jsonl_lines")
    for sentinel in RUNTIME_INTERNAL_SENTINELS:
        if sentinel in metadata_text:
            failures.append(f"runtime_internal_leak:{sentinel}")
    if verifier.get("warnings"):
        failures.append("verifier_warnings")
    required = [
        manager.paths.manifest,
        manager.paths.metadata,
        manager.paths.refs,
        manager.paths.source_fingerprint,
        manager.paths.archive_link,
        *manager.paths.indexes.values(),
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        failures.append("missing_required_files")
    if failures:
        raise EvidenceGenerationError(f"evidence invariant failure: {failures}; missing={missing}")
    return replay_summary


def write_run_config(
    output_root: Path,
    manager: MetadataPackageManager,
    source_path: Path,
    committer_status: dict[str, Any],
    reader_summary: dict[str, Any],
) -> None:
    write_json(
        output_root / "run-config.json",
        {
            "evidence_kind": EVIDENCE_KIND,
            "title": "Current synthetic metadata end-to-end verification",
            "synthetic": True,
            "model_inference_performed": False,
            "historical_video_used": False,
            "private_media_used": False,
            "private_model_weights_used": False,
            "generator": "scripts/generate_public_evidence.py",
            "rerun_command": "python scripts/generate_public_evidence.py",
            "source": {
                "relative_path": str(source_path.relative_to(output_root)),
                "format": "binary PPM (P6)",
                "width": 96,
                "height": 64,
                "generation": "deterministic coordinate-derived RGB values; no random or external input",
                "sha256": sha256_file(source_path),
            },
            "package": {
                "relative_path": str(manager.paths.root.relative_to(output_root)),
                "package_id": manager.package_id,
                "event_id": manager.event_id,
                "source_mode": "Offline",
                "metadata_landing_mode": "offline_only",
            },
            "expected": {
                "frame_count": EXPECTED_FRAME_COUNT,
                "object_count": EXPECTED_OBJECT_COUNT,
                "record_count": EXPECTED_RECORD_COUNT,
                "bad_jsonl_lines": 0,
            },
            "observed": {
                "committer_records_written": committer_status["records_written"],
                "reader_records_read": reader_summary["records_read"],
                "reader_frame_count": reader_summary["frame_count"],
                "reader_object_count": reader_summary["object_count"],
            },
            "real_project_code_paths": list(CORE_IMPLEMENTATION_FILES),
            "harness_only_paths": ["scripts/generate_public_evidence.py"],
        },
    )


def write_readme(output_root: Path, manager: MetadataPackageManager) -> None:
    package_rel = manager.paths.root.relative_to(output_root)
    text = f"""# Current synthetic metadata end-to-end verification

This directory is generated by `python scripts/generate_public_evidence.py`.

It is current synthetic verification. It is not a real-model result, a real-video result, or historical evidence.
The synthetic PPM input and synthetic object facts are created by the harness. Metadata projection, asynchronous
commit, indexes, source fingerprinting, archive linking, package verification, and replay use the repository's
existing production code paths listed in `run-config.json`.

- Package: `{package_rel}`
- Verifier result: `verify-result.json`
- Replay result: `replay-summary.json`
- Environment and source hashes: `environment.json`
- Integrity list: `SHA256SUMS`
"""
    (output_root / "README.md").write_text(text, encoding="utf-8")


def write_sha256sums(output_root: Path) -> None:
    output = output_root / "SHA256SUMS"
    files = sorted(
        path for path in output_root.rglob("*")
        if path.is_file() and path != output
    )
    lines = [f"{sha256_file(path)}  {path.relative_to(output_root)}" for path in files]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate(output_root: Path) -> Path:
    output_root = output_root.resolve()
    prepare_output_root(output_root)
    source_path = output_root / SOURCE_NAME
    generate_synthetic_ppm(source_path)
    manager, committer_status = create_package(output_root, source_path)
    verifier = run_real_verifier(output_root, manager, source_path)
    replay = run_real_replay(manager)
    write_json(output_root / "replay-summary.json", replay)
    reader_summary = assert_package_invariants(manager, verifier)
    write_run_config(output_root, manager, source_path, committer_status, reader_summary)
    write_json(output_root / "environment.json", environment_payload())
    write_readme(output_root, manager)
    write_sha256sums(output_root)
    return manager.paths.root


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        package_root = generate(args.output_dir)
    except Exception as exc:
        print(f"public evidence generation failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "evidence_kind": EVIDENCE_KIND,
                "output_root": str(args.output_dir.resolve()),
                "package_root": str(package_root),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
