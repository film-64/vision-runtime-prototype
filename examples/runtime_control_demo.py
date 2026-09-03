from types import SimpleNamespace

from vision_runtime.metrics import RuntimeMetrics
from vision_runtime.runtime_health import RuntimeHealthMonitor
from vision_runtime.schedule_core import heartbeat_profile, resolve_schedule_state
from vision_runtime.time_semantics import before_run_time_decision


def main() -> None:
    metrics = RuntimeMetrics()
    metrics.jitter_config.enabled = False

    for value in [20] * 20 + [180]:
        metrics.record_latency("specialist", value)

    monitor = RuntimeHealthMonitor(metrics)
    tail_decision = monitor.update()

    metrics.set_gauge("queue_total", 9)
    metrics.set_gauge("load_control_admission_budget_intervals", 2)
    pressure_decision = monitor.update()

    heartbeat = heartbeat_profile(105, coarse_main_heartbeat_limit=20)
    pose_schedule = resolve_schedule_state(
        bucket_name="pose",
        runtime_state={"state": "pass"},
        heartbeat=heartbeat,
    )
    identity_schedule = resolve_schedule_state(
        bucket_name="identity",
        runtime_state={"state": "min", "label": "known", "min_seen": True},
        heartbeat=heartbeat,
    )

    stale_task = SimpleNamespace(
        source_detector_index=8,
        deadline_detector_index=10,
        state_generation=3,
    )
    time_decision = before_run_time_decision(stale_task, current_detector_index=11)

    print("runtime health / tail:", tail_decision.level, tail_decision.action, tail_decision.reasons)
    print("runtime health / pressure:", pressure_decision.level, pressure_decision.action, pressure_decision.queue_budget_ratio)
    print("detector heartbeat mode:", heartbeat.mode.value, heartbeat.main_heartbeats)
    print("pose schedule:", pose_schedule.frequency.value, pose_schedule.reason)
    print("identity schedule:", identity_schedule.frequency.value, identity_schedule.reason)
    print("stale task allowed:", time_decision.allowed, time_decision.reason)


if __name__ == "__main__":
    main()
