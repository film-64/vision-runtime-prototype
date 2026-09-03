import pytest

from vision_runtime.observation import (
    Evidence,
    EvidenceScope,
    EvidenceStore,
    FrameRef,
    InformationRecord,
    InformationState,
    ObservationContractError,
)


def frame(frame_id: int, *, source: str = "camera-a", generation: int = 1) -> FrameRef:
    return FrameRef(source_id=source, frame_id=frame_id, generation=generation)


def evidence(
    evidence_id: str,
    scope: EvidenceScope,
    at: FrameRef,
    *,
    version: int = 1,
    valid_until: int | None = None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        scope=scope,
        producer="test-producer",
        frame_ref=at,
        value={"present": True},
        confidence=0.9,
        uncertainty=0.1,
        version=version,
        valid_until_frame_id=valid_until,
    )


def test_evidence_identity_is_scoped_by_source_and_generation() -> None:
    store = EvidenceStore()
    a = store.publish(evidence("motion", EvidenceScope.SCENE_MOTION, frame(1, source="camera-a")))
    b = store.publish(evidence("motion", EvidenceScope.SCENE_MOTION, frame(1, source="camera-b")))
    g2 = store.publish(
        evidence("motion", EvidenceScope.SCENE_MOTION, frame(1, source="camera-a", generation=2))
    )

    assert a != b
    assert a != g2
    assert b != g2


def test_version_must_advance_exactly_once_and_keep_contract_identity() -> None:
    store = EvidenceStore()
    store.publish(evidence("motion", EvidenceScope.SCENE_MOTION, frame(1)))

    with pytest.raises(ObservationContractError):
        store.publish(evidence("motion", EvidenceScope.SCENE_MOTION, frame(2), version=3))

    store.publish(evidence("motion", EvidenceScope.SCENE_MOTION, frame(2), version=2))

    with pytest.raises(ObservationContractError):
        store.publish(evidence("motion", EvidenceScope.SCENE_STRUCTURE, frame(3), version=3))


def test_historical_query_never_exposes_future_evidence() -> None:
    store = EvidenceStore()
    store.publish(evidence("motion", EvidenceScope.SCENE_MOTION, frame(10)))

    assert store.query(at_frame=frame(8), scopes=(EvidenceScope.SCENE_MOTION,)) == ()
    assert [item.frame_ref.frame_id for item in store.query(at_frame=frame(10))] == [10]


def test_historical_query_selects_latest_version_not_after_frame() -> None:
    store = EvidenceStore()
    store.publish(evidence("motion", EvidenceScope.SCENE_MOTION, frame(2)))
    store.publish(evidence("motion", EvidenceScope.SCENE_MOTION, frame(8), version=2))

    assert [item.version for item in store.query(at_frame=frame(5))] == [1]
    assert [item.version for item in store.query(at_frame=frame(9))] == [2]


def test_expiry_and_explicit_invalidation_remove_fresh_support() -> None:
    store = EvidenceStore()
    expiring = store.publish(
        evidence("structure", EvidenceScope.SCENE_STRUCTURE, frame(2), valid_until=4)
    )
    persistent = store.publish(evidence("motion", EvidenceScope.SCENE_MOTION, frame(2)))

    assert store.is_fresh(expiring, at_frame=frame(4))
    assert not store.is_fresh(expiring, at_frame=frame(5))
    assert store.is_fresh(persistent, at_frame=frame(5))

    store.invalidate(persistent, at_frame=frame(5), reason="validation failed")
    assert not store.is_fresh(persistent, at_frame=frame(5))


def test_information_carries_explicit_evidence_and_reports_staleness() -> None:
    store = EvidenceStore()
    motion = store.publish(
        evidence("motion", EvidenceScope.SCENE_MOTION, frame(2), valid_until=6)
    )
    state = InformationState(store)
    record = InformationRecord(
        information_id="region-a",
        source_id="camera-a",
        generation=1,
        value={"bbox": (10, 10, 30, 30)},
        evidence_refs=(motion,),
        observed_frame_id=2,
    )
    state.put(record)

    assert state.support_at(record, at_frame=frame(6)).fully_supported
    support = state.support_at(record, at_frame=frame(7))
    assert not support.fully_supported
    assert support.stale_refs == (motion,)


def test_information_cannot_cite_cross_generation_evidence() -> None:
    store = EvidenceStore()
    motion = store.publish(
        evidence("motion", EvidenceScope.SCENE_MOTION, frame(2, generation=2))
    )

    with pytest.raises(ObservationContractError):
        InformationRecord(
            information_id="region-a",
            source_id="camera-a",
            generation=1,
            value="known",
            evidence_refs=(motion,),
            observed_frame_id=2,
        )
