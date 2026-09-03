from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_public_synthetic_metadata_evidence_end_to_end(tmp_path):
    output = tmp_path / "public-evidence"
    result = subprocess.run(
        [sys.executable, "scripts/generate_public_evidence.py", "--output-dir", str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    command_result = json.loads(result.stdout)
    assert command_result["ok"] is True
    assert command_result["evidence_kind"] == "current_synthetic_verification"

    run_config = json.loads((output / "run-config.json").read_text(encoding="utf-8"))
    package = output / run_config["package"]["relative_path"]
    assert run_config["synthetic"] is True
    assert run_config["model_inference_performed"] is False
    assert run_config["private_media_used"] is False

    for relative_path in (
        "manifest.json",
        "metadata.jsonl",
        "refs.jsonl",
        "source_fingerprint.json",
        "archive_link.json",
        "indexes/by_frame.jsonl",
        "indexes/by_track.jsonl",
        "indexes/by_object.jsonl",
        "indexes/by_hook_ref.jsonl",
        "indexes/by_memory_ref.jsonl",
        "indexes/by_time.jsonl",
    ):
        assert (package / relative_path).is_file()

    verified = json.loads((output / "verify-result.json").read_text(encoding="utf-8"))
    assert verified["ok"] is True
    assert verified["warnings"] == []
    assert verified["hashes"]["source_hash"] == verified["hashes"]["source_hash_computed"]
    assert verified["counts"]["metadata_frames"] == 3
    assert verified["counts"]["metadata_objects"] == 4
    assert verified["counts"]["metadata_records"] == 9

    replay = json.loads((output / "replay-summary.json").read_text(encoding="utf-8"))
    assert replay["loaded"] is True
    assert replay["frame_ids"] == [1, 2, 3]
    assert replay["frame_count"] == 3
    assert replay["object_count"] == 4

    sums = (output / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert sums
    for line in sums:
        digest, relative_path = line.split("  ", 1)
        assert file_sha256(output / relative_path) == digest

    metadata_text = (package / "metadata.jsonl").read_text(encoding="utf-8")
    assert "synthetic_red_block" in metadata_text
    assert "public_synthetic_evidence_harness" in metadata_text
    assert "admission_decision_id" not in metadata_text
    assert "local_scheduler_trace" not in metadata_text
    assert "queue_pressure" not in metadata_text


def test_public_evidence_generator_refuses_unmarked_output_directory(tmp_path):
    output = tmp_path / "not-owned-by-generator"
    output.mkdir()
    (output / "keep.txt").write_text("keep", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/generate_public_evidence.py", "--output-dir", str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "refusing to replace unmarked directory" in result.stderr
    assert (output / "keep.txt").read_text(encoding="utf-8") == "keep"
