from __future__ import annotations

"""Small public evidence contracts extracted from the Observation work.

This module deliberately owns provenance, versioning, freshness and historical
visibility only. It does not create semantic tasks, admit work or schedule
models.
"""

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Iterable


class ObservationContractError(ValueError):
    """Raised when a public Observation invariant is violated."""


class EvidenceScope(str, Enum):
    SCENE_MOTION = "scene.motion"
    SCENE_STRUCTURE = "scene.structure"
    INFORMATION_PRIOR = "scene.information_prior"
    SPATIAL_UNCERTAINTY = "spatial.uncertainty"
    HUMAN_PRESENCE = "human.presence"
    TEXT_PRESENCE = "text.presence"
    RECOGNIZED_TEXT = "text.recognized"


@dataclass(frozen=True)
class FrameRef:
    source_id: str
    frame_id: int
    generation: int = 0

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ObservationContractError("source_id is required")
        if self.frame_id < 0:
            raise ObservationContractError("frame_id must be >= 0")
        if self.generation < 0:
            raise ObservationContractError("generation must be >= 0")


@dataclass(frozen=True)
class EvidenceRef:
    source_id: str
    generation: int
    evidence_id: str
    version: int

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.evidence_id.strip():
            raise ObservationContractError("evidence reference identity is required")
        if self.generation < 0:
            raise ObservationContractError("generation must be >= 0")
        if self.version < 1:
            raise ObservationContractError("version must be >= 1")


@dataclass(frozen=True)
class Evidence:
    """One immutable evidence fact.

    `valid_until_frame_id` is optional. When absent, the producer has not placed
    a frame-based expiry on the fact; callers may still invalidate it explicitly.
    """

    evidence_id: str
    scope: EvidenceScope
    producer: str
    frame_ref: FrameRef
    value: Any
    confidence: float
    uncertainty: float = 0.0
    version: int = 1
    valid_until_frame_id: int | None = None

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise ObservationContractError("evidence_id is required")
        if not self.producer.strip():
            raise ObservationContractError("producer is required")
        if self.version < 1:
            raise ObservationContractError("version must be >= 1")
        if not isfinite(float(self.confidence)) or not 0.0 <= float(self.confidence) <= 1.0:
            raise ObservationContractError("confidence must be finite and in [0, 1]")
        if not isfinite(float(self.uncertainty)) or float(self.uncertainty) < 0.0:
            raise ObservationContractError("uncertainty must be finite and >= 0")
        if self.valid_until_frame_id is not None and self.valid_until_frame_id < self.frame_ref.frame_id:
            raise ObservationContractError("valid_until_frame_id cannot precede produced frame")

    @property
    def ref(self) -> EvidenceRef:
        return EvidenceRef(
            source_id=self.frame_ref.source_id,
            generation=self.frame_ref.generation,
            evidence_id=self.evidence_id,
            version=self.version,
        )

    def fresh_at(self, frame_ref: FrameRef) -> bool:
        if frame_ref.source_id != self.frame_ref.source_id:
            return False
        if frame_ref.generation != self.frame_ref.generation:
            return False
        if frame_ref.frame_id < self.frame_ref.frame_id:
            return False
        if self.valid_until_frame_id is None:
            return True
        return frame_ref.frame_id <= self.valid_until_frame_id


@dataclass(frozen=True)
class EvidenceInvalidation:
    evidence_ref: EvidenceRef
    reason: str
    invalidated_at_frame: FrameRef


class EvidenceStore:
    """Append-only evidence facts with source/generation-scoped identity.

    Material changes publish a new version. Historical queries cannot observe a
    version produced by a later frame. Invalidation is explicit and separate
    from the evidence fact itself.
    """

    def __init__(self) -> None:
        self._versions: dict[tuple[str, int, str], list[Evidence]] = {}
        self._invalidated: dict[EvidenceRef, EvidenceInvalidation] = {}

    @staticmethod
    def _key(source_id: str, generation: int, evidence_id: str) -> tuple[str, int, str]:
        return (source_id, generation, evidence_id)

    def publish(self, evidence: Evidence) -> EvidenceRef:
        key = self._key(
            evidence.frame_ref.source_id,
            evidence.frame_ref.generation,
            evidence.evidence_id,
        )
        versions = self._versions.setdefault(key, [])
        if not versions:
            if evidence.version != 1:
                raise ObservationContractError("first evidence version must be 1")
        else:
            latest = versions[-1]
            expected = latest.version + 1
            if evidence.version != expected:
                raise ObservationContractError(
                    f"evidence version must advance exactly once: expected {expected}, got {evidence.version}"
                )
            if evidence.scope != latest.scope:
                raise ObservationContractError("evidence identity cannot silently change scope")
            if evidence.producer != latest.producer:
                raise ObservationContractError("evidence identity cannot silently change producer")
            if evidence.frame_ref.frame_id < latest.frame_ref.frame_id:
                raise ObservationContractError("evidence version frame cannot move backwards")
        versions.append(evidence)
        return evidence.ref

    def get(self, ref: EvidenceRef) -> Evidence:
        versions = self._versions.get(self._key(ref.source_id, ref.generation, ref.evidence_id), ())
        for evidence in versions:
            if evidence.version == ref.version:
                return evidence
        raise KeyError(ref)

    def latest(
        self,
        evidence_id: str,
        *,
        source_id: str,
        generation: int,
        at_frame: FrameRef | None = None,
    ) -> Evidence | None:
        versions = self._versions.get(self._key(source_id, generation, evidence_id))
        if not versions:
            return None
        if at_frame is None:
            return versions[-1]
        if at_frame.source_id != source_id or at_frame.generation != generation:
            raise ObservationContractError("historical query must match source/generation")
        for evidence in reversed(versions):
            if evidence.frame_ref.frame_id <= at_frame.frame_id:
                return evidence
        return None

    def invalidate(self, ref: EvidenceRef, *, at_frame: FrameRef, reason: str) -> None:
        evidence = self.get(ref)
        if evidence.frame_ref.source_id != at_frame.source_id:
            raise ObservationContractError("cannot invalidate evidence from another source")
        if evidence.frame_ref.generation != at_frame.generation:
            raise ObservationContractError("cannot invalidate evidence from another generation")
        if evidence.frame_ref.frame_id > at_frame.frame_id:
            raise ObservationContractError("cannot invalidate evidence from a future frame")
        if not reason.strip():
            raise ObservationContractError("invalidation reason is required")
        self._invalidated[ref] = EvidenceInvalidation(ref, reason, at_frame)

    def is_fresh(self, ref: EvidenceRef, *, at_frame: FrameRef) -> bool:
        if ref in self._invalidated:
            return False
        return self.get(ref).fresh_at(at_frame)

    def query(
        self,
        *,
        at_frame: FrameRef,
        scopes: Iterable[EvidenceScope] | None = None,
        latest_only: bool = True,
        fresh_only: bool = True,
    ) -> tuple[Evidence, ...]:
        wanted = None if scopes is None else set(scopes)
        output: list[Evidence] = []
        for (source_id, generation, _), versions in self._versions.items():
            if source_id != at_frame.source_id or generation != at_frame.generation:
                continue
            if latest_only:
                candidates: tuple[Evidence, ...] = ()
                for evidence in reversed(versions):
                    if evidence.frame_ref.frame_id <= at_frame.frame_id:
                        candidates = (evidence,)
                        break
            else:
                candidates = tuple(
                    evidence for evidence in versions if evidence.frame_ref.frame_id <= at_frame.frame_id
                )
            for evidence in candidates:
                if wanted is not None and evidence.scope not in wanted:
                    continue
                if fresh_only and not self.is_fresh(evidence.ref, at_frame=at_frame):
                    continue
                output.append(evidence)
        output.sort(key=lambda item: (item.scope.value, item.evidence_id, item.frame_ref.frame_id, item.version))
        return tuple(output)
