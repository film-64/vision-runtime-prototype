from types import SimpleNamespace

from vision_runtime.time_semantics import DetectorClock, before_run_time_decision, merge_time_decision


def timed_task(deadline=10, source=8):
    return SimpleNamespace(
        source_detector_index=source,
        deadline_detector_index=deadline,
        state_generation=3,
    )


def test_detector_clock_watermark_defaults_to_current_detector_index():
    assert DetectorClock(current_detector_index=12).watermark == 12
    assert DetectorClock(current_detector_index=12, allowed_lag=2).watermark == 10


def test_before_run_time_decision_uses_watermark():
    stale = before_run_time_decision(timed_task(deadline=10), current_detector_index=11)
    allowed_with_lag = before_run_time_decision(timed_task(deadline=10), current_detector_index=11, allowed_lag=1)

    assert not stale.allowed
    assert stale.reason == "deadline_expired_before_run"
    assert allowed_with_lag.allowed
    assert allowed_with_lag.watermark == 10


def test_merge_time_decision_rejects_result_that_became_stale_during_execution():
    task_context = timed_task(deadline=14, source=12)

    decision = merge_time_decision(task_context, current_detector_index=16, allowed_lag=1)

    assert not decision.allowed
    assert decision.reason == "deadline_expired_after_run"
    assert decision.watermark == 15
