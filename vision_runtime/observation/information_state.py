from __future__ import annotations

"""Minimal information-state layer for the public Observation slice.

Information records describe what the runtime currently carries forward. They
reference evidence rather than replacing it, and they do not own model
execution or scheduling policy.
"""

from dataclasses import dataclass
from typing import Any

from .evidence import EvidenceRef, EvidenceStore, FrameRef, ObservationContractError


@dataclass(frozen=True)
class InformationRecord:
    information_id: str
    source_id: str
    generation: int
    value: Any
    evidence_refs: tuple[EvidenceRef, ...]
    observed_frame_id: int

    def __post_init__(self) -> None:
        if not self.information_id.strip():
            raise ObservationContractError("information_id is required")
        if not self.source_id.strip():
            raise ObservationContractError("source_id is required")
        if self.generation < 0 or self.observed_frame_id < 0:
            raise ObservationContractError("generation and observed_frame_id must be >= 0")
        if not self.evidence_refs:
            raise ObservationContractError("information must cite at least one evidence ref")
        for ref in self.evidence_refs:
            if ref.source_id != self.source_id:
                raise ObservationContractError("information evidence cannot cross source_id")
            if ref.generation != self.generation:
                raise ObservationContractError("information evidence cannot cross generation")


@dataclass(frozen=True)
class InformationSupport:
    record: InformationRecord
    fresh_refs: tuple[EvidenceRef, ...]
    stale_refs: tuple[EvidenceRef, ...]

    @property
    def fully_supported(self) -> bool:
        return bool(self.record.evidence_refs) and not self.stale_refs


class InformationState:
    """Small registry linking carried information to explicit evidence.

    The state intentionally makes no inference about *why* a stale item should
    be refreshed. That decision remains a caller/runtime policy concern.
    """

    def __init__(self, evidence: EvidenceStore) -> None:
        self._evidence = evidence
        self._records: dict[tuple[str, int, str], InformationRecord] = {}

    @staticmethod
    def _key(source_id: str, generation: int, information_id: str) -> tuple[str, int, str]:
        return (source_id, generation, information_id)

    def put(self, record: InformationRecord) -> None:
        for ref in record.evidence_refs:
            evidence = self._evidence.get(ref)
            if evidence.frame_ref.frame_id > record.observed_frame_id:
                raise ObservationContractError("information cannot cite evidence from a future frame")
        key = self._key(record.source_id, record.generation, record.information_id)
        previous = self._records.get(key)
        if previous is not None and record.observed_frame_id < previous.observed_frame_id:
            raise ObservationContractError("information observation frame cannot move backwards")
        self._records[key] = record

    def get(self, information_id: str, *, source_id: str, generation: int) -> InformationRecord | None:
        return self._records.get(self._key(source_id, generation, information_id))

    def support_at(self, record: InformationRecord, *, at_frame: FrameRef) -> InformationSupport:
        if at_frame.source_id != record.source_id or at_frame.generation != record.generation:
            raise ObservationContractError("support query must match information source/generation")
        fresh: list[EvidenceRef] = []
        stale: list[EvidenceRef] = []
        for ref in record.evidence_refs:
            if self._evidence.is_fresh(ref, at_frame=at_frame):
                fresh.append(ref)
            else:
                stale.append(ref)
        return InformationSupport(record, tuple(fresh), tuple(stale))
