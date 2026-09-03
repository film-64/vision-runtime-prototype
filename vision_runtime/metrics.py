from __future__ import annotations

from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
import time
from typing import Iterator


def perf_ms() -> float:
    return time.perf_counter() * 1000.0


@dataclass
class MetricsJitterFilterConfig:
    enabled: bool = True
    warmup_samples: int = 3
    min_baseline_samples: int = 12
    spike_multiplier: float = 2.5
    spike_floor_ms: float = 120.0
    max_consecutive_drops: int = 3


@dataclass
class RuntimeMetrics:
    """Model-free runtime metrics used by scheduling and health decisions.

    This is a curated extraction of the yoloe26-smoke metrics contract. The
    showcase keeps the latency/counter/gauge/label behavior needed by the
    runtime-control examples and drops application-specific status formatting.
    """

    window: int = 240
    latencies: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(lambda: deque(maxlen=240)))
    filtered_latencies: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(lambda: deque(maxlen=240)))
    sample_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    jitter_drop_streaks: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    jitter_config: MetricsJitterFilterConfig = field(default_factory=MetricsJitterFilterConfig)
    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    gauges: dict[str, float] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)

    @contextmanager
    def timer(self, name: str) -> Iterator[None]:
        start = perf_ms()
        try:
            yield
        finally:
            self.record_latency(name, perf_ms() - start)

    def record_latency(self, name: str, elapsed_ms: float) -> None:
        series = self.latencies[name]
        if series.maxlen != self.window:
            self.latencies[name] = deque(series, maxlen=self.window)
            series = self.latencies[name]
        elapsed = float(elapsed_ms)
        series.append(elapsed)
        self.record_filtered_latency(name, elapsed)

    def configure_jitter_filter(self, config) -> None:
        if config is None:
            return
        self.jitter_config = MetricsJitterFilterConfig(
            enabled=bool(getattr(config, "enabled", self.jitter_config.enabled)),
            warmup_samples=max(0, int(getattr(config, "warmup_samples", self.jitter_config.warmup_samples))),
            min_baseline_samples=max(1, int(getattr(config, "min_baseline_samples", self.jitter_config.min_baseline_samples))),
            spike_multiplier=max(1.0, float(getattr(config, "spike_multiplier", self.jitter_config.spike_multiplier))),
            spike_floor_ms=max(0.0, float(getattr(config, "spike_floor_ms", self.jitter_config.spike_floor_ms))),
            max_consecutive_drops=max(0, int(getattr(config, "max_consecutive_drops", self.jitter_config.max_consecutive_drops))),
        )

    def record_filtered_latency(self, name: str, elapsed: float) -> None:
        cfg = self.jitter_config
        series = self.filtered_latencies[name]
        if series.maxlen != self.window:
            self.filtered_latencies[name] = deque(series, maxlen=self.window)
            series = self.filtered_latencies[name]

        self.sample_counts[name] += 1
        sample_index = self.sample_counts[name]
        if not cfg.enabled or self.is_filter_exempt(name):
            series.append(elapsed)
            self.jitter_drop_streaks[name] = 0
            return
        if sample_index <= cfg.warmup_samples:
            self.inc(f"jitter_warmup_skipped_{name}")
            self.inc("jitter_warmup_skipped_total")
            return
        if len(series) >= cfg.min_baseline_samples and self.is_latency_spike(series, elapsed, cfg):
            self.jitter_drop_streaks[name] += 1
            if self.jitter_drop_streaks[name] <= cfg.max_consecutive_drops:
                self.inc(f"jitter_spike_dropped_{name}")
                self.inc("jitter_spike_dropped_total")
                self.set_gauge(f"jitter_last_dropped_{name}_ms", elapsed)
                return
        self.jitter_drop_streaks[name] = 0
        series.append(elapsed)

    def is_filter_exempt(self, name: str) -> bool:
        return name.startswith("warmup")

    def is_latency_spike(self, series: deque[float], elapsed: float, cfg: MetricsJitterFilterConfig) -> bool:
        baseline = self.percentile_from_values(series, 0.95)
        threshold = max(cfg.spike_floor_ms, baseline * cfg.spike_multiplier)
        return elapsed > threshold

    def inc(self, name: str, value: int = 1) -> None:
        self.counters[name] += int(value)

    def set_gauge(self, name: str, value: float) -> None:
        self.gauges[name] = float(value)

    def set_label(self, name: str, value: str) -> None:
        self.labels[name] = str(value)

    def reset(self) -> None:
        self.latencies.clear()
        self.filtered_latencies.clear()
        self.sample_counts.clear()
        self.jitter_drop_streaks.clear()
        self.counters.clear()
        self.gauges.clear()
        self.labels.clear()

    def avg(self, name: str) -> float:
        values = self.filtered_latencies.get(name)
        return sum(values) / len(values) if values else 0.0

    def last(self, name: str) -> float:
        values = self.latencies.get(name)
        return values[-1] if values else 0.0

    def max(self, name: str) -> float:
        values = self.latencies.get(name)
        return max(values) if values else 0.0

    def p95(self, name: str) -> float:
        values = list(self.filtered_latencies.get(name, []))
        return self.percentile_from_values(values, 0.95) if values else 0.0

    def p50(self, name: str) -> float:
        values = list(self.filtered_latencies.get(name, []))
        return self.percentile_from_values(values, 0.50) if values else 0.0

    def p99(self, name: str) -> float:
        values = list(self.filtered_latencies.get(name, []))
        return self.percentile_from_values(values, 0.99) if values else 0.0

    def raw_p95(self, name: str) -> float:
        values = list(self.latencies.get(name, []))
        return self.percentile_from_values(values, 0.95) if values else 0.0

    def raw_p99(self, name: str) -> float:
        values = list(self.latencies.get(name, []))
        return self.percentile_from_values(values, 0.99) if values else 0.0

    def percentile_from_values(self, values, percentile: float) -> float:
        ordered = sorted(float(value) for value in values)
        if not ordered:
            return 0.0
        index = min(len(ordered) - 1, int(round((len(ordered) - 1) * float(percentile))))
        return ordered[index]

    def snapshot(self) -> dict:
        return {
            "latency_p50_ms": {name: round(self.p50(name), 3) for name in sorted(self.latencies)},
            "latency_p95_ms": {name: round(self.p95(name), 3) for name in sorted(self.latencies)},
            "latency_p99_ms": {name: round(self.p99(name), 3) for name in sorted(self.latencies)},
            "counters": dict(sorted(self.counters.items())),
            "gauges": {name: round(value, 3) for name, value in sorted(self.gauges.items())},
            "labels": dict(sorted(self.labels.items())),
        }
