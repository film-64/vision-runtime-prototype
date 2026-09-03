from vision_runtime.observation import (
    Evidence,
    EvidenceScope,
    EvidenceStore,
    FrameRef,
    InformationRecord,
    InformationState,
)


def main() -> None:
    evidence_store = EvidenceStore()
    information_state = InformationState(evidence_store)

    observed = FrameRef("camera-a", frame_id=10, generation=1)
    motion_ref = evidence_store.publish(
        Evidence(
            evidence_id="region-a-motion",
            scope=EvidenceScope.SCENE_MOTION,
            producer="cheap-cv",
            frame_ref=observed,
            value={"stable": True},
            confidence=0.93,
            uncertainty=0.07,
            valid_until_frame_id=13,
        )
    )

    region = InformationRecord(
        information_id="region-a",
        source_id="camera-a",
        generation=1,
        value={"bbox": (120, 80, 360, 300), "state": "known"},
        evidence_refs=(motion_ref,),
        observed_frame_id=10,
    )
    information_state.put(region)

    for frame_id in (11, 13, 14):
        now = FrameRef("camera-a", frame_id=frame_id, generation=1)
        support = information_state.support_at(region, at_frame=now)
        action = "reuse" if support.fully_supported else "stronger observation required"
        print(f"frame={frame_id}: {action}")


if __name__ == "__main__":
    main()
