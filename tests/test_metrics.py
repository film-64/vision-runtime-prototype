from vision_runtime.metrics import RuntimeMetrics


def test_jitter_filter_keeps_raw_samples_but_drops_bounded_spike_from_effective_series():
    metrics = RuntimeMetrics()
    metrics.jitter_config.warmup_samples = 0
    metrics.jitter_config.min_baseline_samples = 4
    metrics.jitter_config.spike_multiplier = 2.0
    metrics.jitter_config.spike_floor_ms = 100.0

    for value in [20, 21, 19, 20]:
        metrics.record_latency("stage", value)
    metrics.record_latency("stage", 250)

    assert metrics.last("stage") == 250
    assert metrics.raw_p99("stage") == 250
    assert metrics.p99("stage") < 250
    assert metrics.counters["jitter_spike_dropped_total"] == 1


def test_metrics_snapshot_exposes_control_plane_state():
    metrics = RuntimeMetrics()
    metrics.jitter_config.enabled = False
    metrics.record_latency("stage", 10)
    metrics.set_gauge("queue_total", 2)
    metrics.set_label("scene_state", "dynamic")
    metrics.inc("tasks_stale")

    snapshot = metrics.snapshot()

    assert snapshot["latency_p50_ms"]["stage"] == 10
    assert snapshot["gauges"]["queue_total"] == 2
    assert snapshot["labels"]["scene_state"] == "dynamic"
    assert snapshot["counters"]["tasks_stale"] == 1
