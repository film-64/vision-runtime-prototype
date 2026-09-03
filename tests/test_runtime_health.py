from vision_runtime.metrics import RuntimeMetrics
from vision_runtime.runtime_health import RuntimeHealthMonitor
import vision_runtime.runtime_health as runtime_health


def test_runtime_health_enters_watch_on_tail_latency():
    metrics = RuntimeMetrics()
    metrics.jitter_config.enabled = False
    for value in [20] * 20 + [180]:
        metrics.record_latency("specialist", value)
    monitor = RuntimeHealthMonitor(metrics=metrics)

    decision = monitor.update()

    assert decision.level == "watch"
    assert "tail_latency" in decision.reasons
    assert metrics.labels["runtime_health_action"] == "freeze_aggressive_ramp"


def test_runtime_health_detects_volatile_scene_with_pressure():
    metrics = RuntimeMetrics()
    metrics.set_gauge("queue_pressure_ticks", 1)
    monitor = RuntimeHealthMonitor(metrics=metrics)

    for state in ["static", "dynamic", "static", "unstable", "normal", "dynamic", "static", "dynamic"]:
        metrics.set_label("scene_state", state)
        decision = monitor.update()

    assert decision.level == "degraded"
    assert "volatile_scene_pressure" in decision.reasons
    assert metrics.gauges["runtime_health_scene_flip_rate"] >= 0.65


def test_runtime_health_uses_queue_relative_to_dynamic_budget():
    metrics = RuntimeMetrics()
    metrics.set_gauge("queue_total", 9)
    metrics.set_gauge("load_control_admission_budget_intervals", 2)
    monitor = RuntimeHealthMonitor(metrics=metrics)

    decision = monitor.update()

    assert decision.level == "critical"
    assert decision.queue_budget_ratio == 4.5
    assert "critical_pressure" in decision.reasons


def test_runtime_health_hysteresis_cools_down_slowly():
    metrics = RuntimeMetrics()
    metrics.set_gauge("queue_pressure_ticks", 6)
    monitor = RuntimeHealthMonitor(metrics=metrics)
    assert monitor.update().level == "critical"

    metrics.set_gauge("queue_pressure_ticks", 0)
    for _ in range(11):
        decision = monitor.update()
    assert decision.level == "critical"

    decision = monitor.update()
    assert decision.level == "degraded"


def test_runtime_health_clear_no_metrics_and_error_edges():
    monitor = RuntimeHealthMonitor(metrics=None)
    assert monitor.update().level == "ok"
    assert monitor.tail_ratio("x") == 1.0
    assert monitor.queue_budget_ratio() == 0.0
    assert monitor.stale_delta() == 0
    assert monitor.level_for(99) == "critical"
    assert monitor.action_for("degraded") == "disable_low_value"
    assert monitor.action_for("ok") == "normal"

    metrics = RuntimeMetrics()
    metrics.gauges["queue_pressure_ticks"] = object()
    metrics.gauges["queue_total"] = object()
    metrics.gauges["load_control_admission_budget_intervals"] = object()
    metrics.gauges["effective_capacity"] = 3
    metrics.counters["tasks_stale"] = 1
    monitor = RuntimeHealthMonitor(metrics=metrics)
    decision = monitor.update()
    assert decision.queue_pressure_ticks == 0
    assert decision.stale_delta == 1
    monitor.clear()
    assert monitor.current_level == "ok"
    assert monitor.last_decision.level == "ok"
    original_levels = runtime_health.HEALTH_LEVELS
    runtime_health.HEALTH_LEVELS = {"odd": 5}
    try:
        assert monitor.level_for(1) == "ok"
    finally:
        runtime_health.HEALTH_LEVELS = original_levels
