from vision_runtime.metrics import RuntimeMetrics
from vision_runtime.schedule_core import (
    HeartbeatMode,
    RuntimeFrequency,
    WarningLevel,
    chain_latency_profile,
    heartbeat_profile,
    retry_delay_ms,
    resolve_schedule_state,
)


def test_main_detector_heartbeat_limit_switches_mode():
    fine = heartbeat_profile(100, coarse_main_heartbeat_limit=20)
    coarse = heartbeat_profile(105, coarse_main_heartbeat_limit=20)

    assert fine.main_heartbeats == 20
    assert fine.mode == HeartbeatMode.HEARTBEAT_OFFSET
    assert coarse.main_heartbeats == 21
    assert coarse.mode == HeartbeatMode.NEW_RESULT_DRIVEN


def test_defined_result_enters_low_only_after_concrete_result():
    heartbeat = heartbeat_profile(30)

    probing = resolve_schedule_state(
        bucket_name="identity",
        runtime_state={"state": "unknown", "attempts": 1},
        heartbeat=heartbeat,
        retry_limit=8,
    )
    concrete = resolve_schedule_state(
        bucket_name="identity",
        runtime_state={"state": "min", "label": "known", "min_seen": True, "attempts": 2},
        heartbeat=heartbeat,
        retry_limit=8,
    )

    assert probing.frequency == RuntimeFrequency.NORMAL
    assert probing.concrete_result is False
    assert concrete.frequency == RuntimeFrequency.LOW
    assert concrete.concrete_result is True


def test_completed_fixed_age_window_can_stop():
    heartbeat = heartbeat_profile(30)

    first_sample = resolve_schedule_state(
        bucket_name="age",
        runtime_state={"state": "pass", "label": "range", "attempts": 1},
        heartbeat=heartbeat,
        retry_limit=4,
    )
    finished = resolve_schedule_state(
        bucket_name="age",
        runtime_state={"state": "pass", "label": "range", "attempts": 4, "final": True},
        heartbeat=heartbeat,
        retry_limit=4,
    )

    assert first_sample.frequency == RuntimeFrequency.NORMAL
    assert first_sample.concrete_result is False
    assert finished.frequency == RuntimeFrequency.STOP
    assert finished.concrete_result is True


def test_dynamic_result_is_new_input_driven_when_detector_is_coarse():
    fine = heartbeat_profile(30)
    coarse = heartbeat_profile(150)

    fine_expression = resolve_schedule_state(
        bucket_name="expression",
        runtime_state={"state": "pass", "label": "sample", "final": True},
        heartbeat=fine,
    )
    coarse_expression = resolve_schedule_state(
        bucket_name="expression",
        runtime_state={"state": "pass", "label": "sample", "final": True},
        heartbeat=coarse,
    )

    assert fine_expression.frequency == RuntimeFrequency.HIGH
    assert coarse_expression.frequency == RuntimeFrequency.NORMAL
    assert coarse_expression.heartbeat_mode == HeartbeatMode.NEW_RESULT_DRIVEN


def test_chain_artifact_remains_protected():
    decision = resolve_schedule_state(
        bucket_name="face_roi",
        runtime_state={"label": "artifact"},
        heartbeat=heartbeat_profile(30),
    )

    assert decision.frequency == RuntimeFrequency.HIGH
    assert decision.reason == "chain_artifact_protected"


def test_chain_latency_profile_uses_p50_p99_sum():
    metrics = RuntimeMetrics()
    metrics.jitter_config.enabled = False
    for value in [30, 30, 32, 31, 30]:
        metrics.record_latency("pose", value)
    for value in [8, 8, 9, 8, 8]:
        metrics.record_latency("face_roi", value)
    for value in [39, 40, 42, 41, 160]:
        metrics.record_latency("identity", value)

    profile = chain_latency_profile(metrics, ["pose", "face_roi", "identity"])

    assert profile.p50_ms == 30 + 8 + 41
    assert profile.p99_ms == 32 + 9 + 160
    assert profile.p50_heartbeats == 16
    assert profile.p99_heartbeats == 41
    assert profile.warning == WarningLevel.WATCH


def test_retry_delay_uses_heartbeat_cooldown_multiplier():
    cooldown = retry_delay_ms(
        state_name="unknown_cooldown",
        base_delay_ms=5,
        heartbeat_ms=5,
        open_unknown_retry=True,
        cooldown_heartbeats=4,
    )

    assert cooldown.delay_ms == 20
    assert cooldown.multiplier == 4
    assert cooldown.reason == "unknown_cooldown"
