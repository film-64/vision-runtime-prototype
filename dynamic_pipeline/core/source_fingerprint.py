from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

from .context import now_ms
from .package_manifest import write_json


@dataclass(frozen=True)
class SourceFingerprint:
    schema_version: str
    source_hash: str
    hash_algorithm: str
    source_kind: str
    file_size_bytes: int
    mtime_ms: int
    duration_ms: int | None = None
    frame_count: int | None = None
    fps: float | None = None
    width: int | None = None
    height: int | None = None
    video_probe_status: str | None = None
    video_probe_reason: str | None = None
    hash_completed_at_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def fingerprint_file(path: str | Path, *, source_kind: str = "video", chunk_size: int = 1024 * 1024) -> SourceFingerprint:
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(chunk_size), b""):
            digest.update(chunk)
    stat = path.stat()
    return SourceFingerprint(
        schema_version="source_fingerprint.v1",
        source_hash=f"sha256:{digest.hexdigest()}",
        hash_algorithm="sha256",
        source_kind=str(source_kind or "video"),
        file_size_bytes=int(stat.st_size),
        mtime_ms=int(stat.st_mtime * 1000),
        hash_completed_at_ms=now_ms(),
    )


def build_video_source_fingerprint(path: str | Path, *, chunk_size: int = 1024 * 1024) -> SourceFingerprint:
    base = fingerprint_file(path, source_kind="video", chunk_size=chunk_size)
    try:
        facts = probe_video_source_facts(path)
    except VideoSourceProbeError as exc:
        return SourceFingerprint(
            **{
                **base.to_dict(),
                "video_probe_status": "failed",
                "video_probe_reason": str(exc),
            }
        )
    return SourceFingerprint(
        **{
            **base.to_dict(),
            **facts,
            "video_probe_status": "ok",
            "video_probe_reason": None,
        }
    )


class VideoSourceProbeError(RuntimeError):
    pass


def probe_video_source_facts(path: str | Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise VideoSourceProbeError("ffprobe not found")
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,r_frame_rate,nb_frames,duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        raw = subprocess.check_output(command, stderr=subprocess.STDOUT, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        output = getattr(exc, "output", "") or ""
        reason = output.strip() or str(exc)
        raise VideoSourceProbeError(reason) from exc
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise VideoSourceProbeError("ffprobe returned invalid json") from exc
    streams = data.get("streams") if isinstance(data, dict) else None
    if not streams:
        raise VideoSourceProbeError("ffprobe returned no video stream")
    stream = streams[0] if isinstance(streams[0], dict) else {}
    fps = parse_fps(stream.get("avg_frame_rate")) or parse_fps(stream.get("r_frame_rate"))
    duration_s = parse_float(stream.get("duration"))
    frame_count = parse_int(stream.get("nb_frames"))
    if frame_count is None and duration_s is not None and fps is not None:
        frame_count = int(round(duration_s * fps))
    return {
        "duration_ms": int(round(duration_s * 1000.0)) if duration_s is not None else None,
        "frame_count": frame_count,
        "fps": fps,
        "width": parse_int(stream.get("width")),
        "height": parse_int(stream.get("height")),
    }


def parse_fps(value: Any) -> float | None:
    if value in (None, "", "0/0"):
        return None
    text = str(value)
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        denominator_float = float(denominator)
        return float(numerator) / denominator_float if denominator_float else None
    parsed = float(text)
    return parsed if parsed > 0 else None


def parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    parsed = float(value)
    return parsed if parsed >= 0 else None


def parse_int(value: Any) -> int | None:
    if value in (None, "", "N/A"):
        return None
    return int(float(value))


def write_source_fingerprint(path: str | Path, fingerprint: SourceFingerprint) -> None:
    write_json(path, fingerprint.to_dict())
