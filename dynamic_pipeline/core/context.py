from __future__ import annotations

from dataclasses import dataclass, field
import time
import uuid
from typing import Any


def now_ms() -> int:
    return int(time.time() * 1000)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class BoxSet:
    frame_xyxy: list[float]
    screen_xyxy: list[float] | None = None
    display_norm_xyxy: list[float] | None = None

    @classmethod
    def from_frame_box(
        cls,
        frame_xyxy: list[float],
        frame_size: tuple[int, int],
        *,
        screen_xyxy: list[float] | None = None,
    ) -> "BoxSet":
        width, height = frame_size
        values = [float(v) for v in frame_xyxy]
        normalized = [0.0, 0.0, 0.0, 0.0]
        if width > 0 and height > 0:
            normalized = [
                max(0.0, min(1.0, values[0] / width)),
                max(0.0, min(1.0, values[1] / height)),
                max(0.0, min(1.0, values[2] / width)),
                max(0.0, min(1.0, values[3] / height)),
            ]
        return cls(values, screen_xyxy=screen_xyxy, display_norm_xyxy=normalized)


@dataclass
class RawCandidate:
    producer: str
    class_name: str
    confidence: float
    prompt_names: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationField:
    status: str = "not_run"
    label: str | None = None
    score: float | None = None
    producer: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerifiedState:
    identity: VerificationField = field(default_factory=VerificationField)
    age: VerificationField = field(default_factory=VerificationField)
    expression: VerificationField = field(default_factory=VerificationField)
    color: VerificationField = field(default_factory=VerificationField)
    clothing_attribute: VerificationField = field(default_factory=VerificationField)
    closed_class: VerificationField = field(default_factory=VerificationField)
    ocr: VerificationField = field(default_factory=VerificationField)
    pose: VerificationField = field(default_factory=VerificationField)
    hand: VerificationField = field(default_factory=VerificationField)
    pet: VerificationField = field(default_factory=VerificationField)


@dataclass
class DisplayObject:
    label: str
    score: float


@dataclass
class RuntimeState:
    source_row: dict[str, Any] = field(default_factory=dict)


@dataclass
class ObjectContext:
    object_id: str
    frame_id: int
    source_id: str
    frame_size: tuple[int, int]
    boxes: BoxSet
    raw_candidate: RawCandidate
    verified: VerifiedState = field(default_factory=VerifiedState)
    display: DisplayObject | None = None
    runtime: RuntimeState = field(default_factory=RuntimeState)
    track_id: str | None = None
    source_track_id: str | None = None
    track_version: int = 0
    detector_index: int = 0
    source_detector_index: int = 0
    deadline_detector_index: int = 0

    def __post_init__(self) -> None:
        if self.display is None:
            label = self.raw_candidate.prompt_names[0] if self.raw_candidate.prompt_names else self.raw_candidate.class_name
            self.display = DisplayObject(label=label, score=float(self.raw_candidate.confidence))


@dataclass
class FrameContext:
    frame_id: int
    source_id: str
    timestamp_ms: int
    frame_width: int
    frame_height: int
    prompt_version: int = 0
    pixel_format: str | None = None
    platform: dict[str, Any] = field(default_factory=dict)
    objects: list[ObjectContext] = field(default_factory=list)
    detector_index: int = 0
    source_frame_index: int | None = None
    source_pts_ms: float | None = None
    sample_index: int | None = None

    @property
    def frame_size(self) -> tuple[int, int]:
        return self.frame_width, self.frame_height
