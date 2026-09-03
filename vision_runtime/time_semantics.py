from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DetectorClock:
    current_detector_index: int
    allowed_lag: int = 0

    @property
    def watermark(self) -> int:
        return max(0, int(self.current_detector_index) - max(0, int(self.allowed_lag or 0)))


@dataclass(frozen=True)
class TaskTimeSemantics:
    source_detector_index: int
    deadline_detector_index: int
    state_generation: int = 0

    @classmethod
    def from_task(cls, task) -> "TaskTimeSemantics":
        return cls(
            source_detector_index=int(getattr(task, "source_detector_index", 0) or 0),
            deadline_detector_index=int(getattr(task, "deadline_detector_index", 0) or 0),
            state_generation=int(getattr(task, "state_generation", getattr(task, "generation", 0)) or 0),
        )

    @classmethod
    def from_task_context(cls, task_context) -> "TaskTimeSemantics":
        return cls(
            source_detector_index=int(getattr(task_context, "source_detector_index", 0) or 0),
            deadline_detector_index=int(getattr(task_context, "deadline_detector_index", 0) or 0),
            state_generation=int(getattr(task_context, "state_generation", 0) or 0),
        )


@dataclass(frozen=True)
class TimeDecision:
    allowed: bool
    reason: str
    watermark: int
    current_detector_index: int
    source_detector_index: int
    deadline_detector_index: int


def before_run_time_decision(task, current_detector_index: int, *, allowed_lag: int = 0) -> TimeDecision:
    return time_decision(
        TaskTimeSemantics.from_task(task),
        current_detector_index,
        allowed_lag=allowed_lag,
        stale_reason="deadline_expired_before_run",
    )


def merge_time_decision(task_context, current_detector_index: int, *, allowed_lag: int = 0) -> TimeDecision:
    return time_decision(
        TaskTimeSemantics.from_task_context(task_context),
        current_detector_index,
        allowed_lag=allowed_lag,
        stale_reason="deadline_expired_after_run",
    )


def time_decision(
    task_time: TaskTimeSemantics,
    current_detector_index: int,
    *,
    allowed_lag: int = 0,
    stale_reason: str,
) -> TimeDecision:
    clock = DetectorClock(current_detector_index=int(current_detector_index), allowed_lag=int(allowed_lag or 0))
    deadline = int(task_time.deadline_detector_index or 0)
    stale = bool(deadline and deadline < clock.watermark)
    return TimeDecision(
        allowed=not stale,
        reason=stale_reason if stale else "ok",
        watermark=clock.watermark,
        current_detector_index=int(current_detector_index),
        source_detector_index=int(task_time.source_detector_index or 0),
        deadline_detector_index=deadline,
    )
