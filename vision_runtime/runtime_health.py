from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


HEALTH_LEVELS = {"ok": 0, "watch": 1, "degraded": 2, "critical": 3}


@dataclass(frozen=True)
class RuntimeHealthDecision:
    level: str
    severity: int
    action: str
    tail_ratio: float
    specialist_tail_ratio: float
    queue_pressure_ticks: int
    queue_budget_ratio: float
    stale_delta: int
    scene_flip_rate: float
    scene_state: str
    reasons: tuple[str, ...] = field(default_factory=tuple)


class RuntimeHealthMonitor:
    def __init__(self, metrics=None, window: int = 24):
        self.metrics = metrics
        self.scene_window = deque(maxlen=max(4, int(window)))
        self.current_level = "ok"
        self.last_stale_total = 0
        self.clear_count = 0
        self.last_decision = RuntimeHealthDecision(
            level="ok",
            severity=0,
            action="normal",
            tail_ratio=1.0,
            specialist_tail_ratio=1.0,
            queue_pressure_ticks=0,
            queue_budget_ratio=0.0,
            stale_delta=0,
            scene_flip_rate=0.0,
            scene_state="normal",
            reasons=(),
        )

    def clear(self):
        self.scene_window.clear()
        self.current_level = "ok"
        self.last_stale_total = 0
        self.clear_count = 0
        self.last_decision = RuntimeHealthDecision(
            level="ok",
            severity=0,
            action="normal",
            tail_ratio=1.0,
            specialist_tail_ratio=1.0,
            queue_pressure_ticks=0,
            queue_budget_ratio=0.0,
            stale_delta=0,
            scene_flip_rate=0.0,
            scene_state="normal",
            reasons=(),
        )
        self.publish(self.last_decision)

    def update(self) -> RuntimeHealthDecision:
        metrics = self.metrics
        labels = getattr(metrics, "labels", {}) if metrics is not None else {}
        gauges = getattr(metrics, "gauges", {}) if metrics is not None else {}
        scene_state = str(labels.get("scene_state", "normal") or "normal")
        self.scene_window.append(scene_state)
        scene_flip_rate = self.scene_flip_rate()
        tail_ratio = self.tail_ratio("total_frame")
        specialist_tail_ratio = max(
            self.tail_ratio("specialist"),
            self.tail_ratio("specialist_face_roi"),
            self.tail_ratio("face_roi_per_crop"),
        )
        try:
            queue_pressure = int(float(gauges.get("queue_pressure_ticks", 0.0) or 0.0))
        except Exception:
            queue_pressure = 0
        queue_budget_ratio = self.queue_budget_ratio()
        stale_delta = self.stale_delta()

        severity = 0
        reasons: list[str] = []
        if scene_flip_rate >= 0.45 and len(self.scene_window) >= 8:
            severity = max(severity, 1)
            reasons.append("volatile_scene")
        if tail_ratio >= 4.0 or specialist_tail_ratio >= 4.0:
            severity = max(severity, 1)
            reasons.append("tail_latency")
        if queue_pressure >= 2 or queue_budget_ratio >= 1.0:
            severity = max(severity, 1)
            reasons.append("queue_watch")
        if scene_flip_rate >= 0.65 and (queue_pressure >= 1 or queue_budget_ratio >= 1.0):
            severity = max(severity, 2)
            reasons.append("volatile_scene_pressure")
        if queue_pressure >= 4 or queue_budget_ratio >= 2.0 or stale_delta > 0:
            severity = max(severity, 2)
            reasons.append("degraded_pressure")
        if queue_pressure >= 6 or queue_budget_ratio >= 4.0 or stale_delta >= 3:
            severity = max(severity, 3)
            reasons.append("critical_pressure")

        level = self.apply_hysteresis(severity)
        decision = RuntimeHealthDecision(
            level=level,
            severity=HEALTH_LEVELS[level],
            action=self.action_for(level),
            tail_ratio=float(tail_ratio),
            specialist_tail_ratio=float(specialist_tail_ratio),
            queue_pressure_ticks=int(queue_pressure),
            queue_budget_ratio=float(queue_budget_ratio),
            stale_delta=int(stale_delta),
            scene_flip_rate=float(scene_flip_rate),
            scene_state=scene_state,
            reasons=tuple(reasons),
        )
        self.last_decision = decision
        self.publish(decision)
        return decision

    def apply_hysteresis(self, observed_severity: int) -> str:
        current = HEALTH_LEVELS.get(self.current_level, 0)
        if observed_severity > current:
            self.current_level = self.level_for(observed_severity)
            self.clear_count = 0
            return self.current_level
        if observed_severity == current:
            self.clear_count = 0
            return self.current_level
        self.clear_count += 1
        required_clear = 4 if current <= 1 else 8 if current == 2 else 12
        if self.clear_count >= required_clear:
            self.current_level = self.level_for(max(0, current - 1))
            self.clear_count = 0
        return self.current_level

    def level_for(self, severity: int) -> str:
        for level, value in HEALTH_LEVELS.items():
            if value == max(0, min(3, int(severity))):
                return level
        return "ok"

    def action_for(self, level: str) -> str:
        if level == "critical":
            return "minimum_identity_path"
        if level == "degraded":
            return "disable_low_value"
        if level == "watch":
            return "freeze_aggressive_ramp"
        return "normal"

    def scene_flip_rate(self) -> float:
        if len(self.scene_window) < 2:
            return 0.0
        flips = sum(1 for left, right in zip(self.scene_window, list(self.scene_window)[1:]) if left != right)
        return flips / max(1, len(self.scene_window) - 1)

    def tail_ratio(self, name: str) -> float:
        if self.metrics is None:
            return 1.0
        p50 = max(1.0, float(self.metrics.p50(name) or 0.0))
        p99 = float(self.metrics.p99(name) or 0.0)
        if p99 <= 0:
            return 1.0
        return max(1.0, p99 / p50)

    def queue_budget_ratio(self) -> float:
        if self.metrics is None:
            return 0.0
        gauges = getattr(self.metrics, "gauges", {})
        try:
            queue_total = float(gauges.get("queue_total", 0.0) or 0.0)
        except Exception:
            queue_total = 0.0
        budget = 0.0
        for name in ("load_control_admission_budget_intervals", "effective_capacity", "load_control_effective_capacity"):
            try:
                budget = float(gauges.get(name, 0.0) or 0.0)
            except Exception:
                budget = 0.0
            if budget > 0:
                break
        return max(0.0, queue_total / max(1.0, budget))

    def stale_delta(self) -> int:
        if self.metrics is None:
            return 0
        counters = getattr(self.metrics, "counters", {})
        current = int(counters.get("tasks_stale", 0) or 0) + int(counters.get("tasks_stale_result", 0) or 0)
        delta = max(0, current - int(self.last_stale_total))
        self.last_stale_total = current
        return delta

    def publish(self, decision: RuntimeHealthDecision) -> None:
        if self.metrics is None:
            return
        self.metrics.set_label("runtime_health_level", decision.level)
        self.metrics.set_label("runtime_health_action", decision.action)
        self.metrics.set_label("runtime_health_reasons", ",".join(decision.reasons))
        self.metrics.set_gauge("runtime_health_severity", decision.severity)
        self.metrics.set_gauge("runtime_health_tail_ratio", decision.tail_ratio)
        self.metrics.set_gauge("runtime_health_specialist_tail_ratio", decision.specialist_tail_ratio)
        self.metrics.set_gauge("runtime_health_scene_flip_rate", decision.scene_flip_rate)
        self.metrics.set_gauge("runtime_health_queue_budget_ratio", decision.queue_budget_ratio)
        self.metrics.set_gauge("runtime_health_stale_delta", decision.stale_delta)
