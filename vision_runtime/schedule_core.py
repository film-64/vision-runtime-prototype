from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import ceil
from typing import Any, Iterable


"""Core scheduling rules extracted from the yoloe26-smoke runtime.

Frequency is a runtime state-machine result. A bucket is not statically low or
high because of its model name. Defined-result buckets may enter LOW only when
the current track has landed in a concrete result bucket. Dynamic-result
buckets keep running on new input while bounded by global budget and detector
heartbeat mode.
"""

MIN_HEARTBEAT_MS = 5.0
DEFAULT_COARSE_MAIN_HEARTBEAT_LIMIT = 20


class ResultSemantics(str, Enum):
    DEFINED_STATE = "defined_state"
    DYNAMIC_STATE = "dynamic_state"
    CHAIN_ARTIFACT = "chain_artifact"


class RuntimeFrequency(str, Enum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    STOP = "stop"


class HeartbeatMode(str, Enum):
    HEARTBEAT_OFFSET = "heartbeat_offset"
    NEW_RESULT_DRIVEN = "new_result_driven"


class WarningLevel(str, Enum):
    OK = "ok"
    WATCH = "watch"
    DEGRADED = "degraded"
    CRITICAL = "critical"


@dataclass(frozen=True)
class HeartbeatProfile:
    main_latency_ms: float
    min_heartbeat_ms: float
    main_heartbeats: int
    coarse_limit: int
    mode: HeartbeatMode


@dataclass(frozen=True)
class ChainLatencyProfile:
    p50_ms: float
    p99_ms: float
    p50_heartbeats: int
    p99_heartbeats: int
    warning: WarningLevel
    names: tuple[str, ...]


@dataclass(frozen=True)
class ScheduleStateDecision:
    semantics: ResultSemantics
    frequency: RuntimeFrequency
    heartbeat_mode: HeartbeatMode
    concrete_result: bool
    reason: str


@dataclass(frozen=True)
class RetryDelayDecision:
    delay_ms: float
    heartbeat_ms: float
    multiplier: int
    reason: str


DEFINED_RESULT_BUCKETS = {"identity", "age"}
DYNAMIC_RESULT_BUCKETS = {"pose", "yolo_pose", "expression"}
CHAIN_ARTIFACT_BUCKETS = {"face_roi"}
RESULT_SEMANTICS_BY_BUCKET: dict[str, ResultSemantics] = {
    **{name: ResultSemantics.DEFINED_STATE for name in DEFINED_RESULT_BUCKETS},
    **{name: ResultSemantics.DYNAMIC_STATE for name in DYNAMIC_RESULT_BUCKETS},
    **{name: ResultSemantics.CHAIN_ARTIFACT for name in CHAIN_ARTIFACT_BUCKETS},
}


def bucket_result_semantics(bucket_name: str) -> ResultSemantics:
    name = normalize_bucket_name(bucket_name)
    return RESULT_SEMANTICS_BY_BUCKET.get(name, ResultSemantics.DYNAMIC_STATE)


def heartbeat_profile(
    main_detector_latency_ms: float,
    *,
    coarse_main_heartbeat_limit: int = DEFAULT_COARSE_MAIN_HEARTBEAT_LIMIT,
    min_heartbeat_ms: float = MIN_HEARTBEAT_MS,
) -> HeartbeatProfile:
    min_hb = max(1.0, float(min_heartbeat_ms or MIN_HEARTBEAT_MS))
    latency = max(0.0, float(main_detector_latency_ms or 0.0))
    heartbeats = max(1, int(ceil(latency / min_hb))) if latency > 0 else 1
    limit = max(1, int(coarse_main_heartbeat_limit or DEFAULT_COARSE_MAIN_HEARTBEAT_LIMIT))
    mode = HeartbeatMode.NEW_RESULT_DRIVEN if heartbeats > limit else HeartbeatMode.HEARTBEAT_OFFSET
    return HeartbeatProfile(
        main_latency_ms=latency,
        min_heartbeat_ms=min_hb,
        main_heartbeats=heartbeats,
        coarse_limit=limit,
        mode=mode,
    )


def chain_latency_profile(
    metrics,
    names: Iterable[str],
    *,
    min_heartbeat_ms: float = MIN_HEARTBEAT_MS,
    watch_ratio: float = 1.8,
    degraded_ratio: float = 2.6,
    critical_ratio: float = 3.5,
) -> ChainLatencyProfile:
    metric_names = tuple(str(name) for name in names)
    p50 = sum(metric_percentile(metrics, name, "p50") for name in metric_names)
    p99 = sum(metric_percentile(metrics, name, "p99") for name in metric_names)
    min_hb = max(1.0, float(min_heartbeat_ms or MIN_HEARTBEAT_MS))
    p50_hb = max(1, int(ceil(max(1.0, p50) / min_hb)))
    p99_hb = max(1, int(ceil(max(1.0, p99) / min_hb)))
    ratio = p99 / max(1.0, p50)
    if ratio >= critical_ratio:
        warning = WarningLevel.CRITICAL
    elif ratio >= degraded_ratio:
        warning = WarningLevel.DEGRADED
    elif ratio >= watch_ratio:
        warning = WarningLevel.WATCH
    else:
        warning = WarningLevel.OK
    return ChainLatencyProfile(
        p50_ms=float(p50),
        p99_ms=float(p99),
        p50_heartbeats=p50_hb,
        p99_heartbeats=p99_hb,
        warning=warning,
        names=metric_names,
    )


def resolve_schedule_state(
    *,
    bucket_name: str,
    runtime_state: dict[str, Any] | None,
    heartbeat: HeartbeatProfile,
    retry_limit: int | None = None,
    semantics: ResultSemantics | str | None = None,
    concrete_result: bool | None = None,
    defined_final_stops: bool | None = None,
) -> ScheduleStateDecision:
    semantics = ResultSemantics(str(semantics)) if semantics is not None else bucket_result_semantics(bucket_name)
    state = runtime_state or {}
    concrete = bool(concrete_result) if concrete_result is not None else has_concrete_result(
        bucket_name,
        state,
        retry_limit=retry_limit,
    )
    if semantics == ResultSemantics.CHAIN_ARTIFACT:
        return resolve_chain_artifact_state(semantics, heartbeat, concrete)
    if semantics == ResultSemantics.DYNAMIC_STATE:
        return resolve_dynamic_state(semantics, heartbeat)
    return resolve_defined_state(
        bucket_name=bucket_name,
        semantics=semantics,
        heartbeat=heartbeat,
        state=state,
        concrete=concrete,
        defined_final_stops=defined_final_stops,
    )


def resolve_chain_artifact_state(
    semantics: ResultSemantics,
    heartbeat: HeartbeatProfile,
    concrete: bool,
) -> ScheduleStateDecision:
    return ScheduleStateDecision(
        semantics=semantics,
        frequency=RuntimeFrequency.HIGH,
        heartbeat_mode=heartbeat.mode,
        concrete_result=concrete,
        reason="chain_artifact_protected",
    )


def resolve_dynamic_state(semantics: ResultSemantics, heartbeat: HeartbeatProfile) -> ScheduleStateDecision:
    return ScheduleStateDecision(
        semantics=semantics,
        frequency=RuntimeFrequency.HIGH if heartbeat.mode == HeartbeatMode.HEARTBEAT_OFFSET else RuntimeFrequency.NORMAL,
        heartbeat_mode=heartbeat.mode,
        concrete_result=False,
        reason="dynamic_state_new_input" if heartbeat.mode == HeartbeatMode.NEW_RESULT_DRIVEN else "dynamic_state_high",
    )


def resolve_defined_state(
    *,
    bucket_name: str,
    semantics: ResultSemantics,
    heartbeat: HeartbeatProfile,
    state: dict[str, Any],
    concrete: bool,
    defined_final_stops: bool | None = None,
) -> ScheduleStateDecision:
    if concrete:
        final_stops = normalize_bucket_name(bucket_name) != "identity" if defined_final_stops is None else bool(
            defined_final_stops
        )
        if bool(state.get("final")) and final_stops:
            frequency = RuntimeFrequency.STOP
            reason = "defined_final_stop"
        else:
            frequency = RuntimeFrequency.LOW
            reason = "defined_result_low"
        return ScheduleStateDecision(
            semantics=semantics,
            frequency=frequency,
            heartbeat_mode=heartbeat.mode,
            concrete_result=True,
            reason=reason,
        )
    return ScheduleStateDecision(
        semantics=semantics,
        frequency=RuntimeFrequency.NORMAL,
        heartbeat_mode=heartbeat.mode,
        concrete_result=False,
        reason="defined_state_not_concrete",
    )


def has_concrete_result(bucket_name: str, state: dict[str, Any], *, retry_limit: int | None = None) -> bool:
    name = normalize_bucket_name(bucket_name)
    if name == "identity":
        if state.get("nickname"):
            return True
        if state.get("min_seen"):
            return True
        return str(state.get("state", "")) in {"min", "pass", "nickname"} and bool(state.get("label") or state.get("nickname"))
    if name == "age":
        attempts = int(state.get("attempts", 0) or 0)
        if retry_limit is not None and attempts < int(retry_limit):
            return False
        return str(state.get("state", "")) in {"pass", "min"} and bool(state.get("label"))
    return bool(state.get("label") or state.get("nickname"))


def identity_stride_intervals(config: Any, state: dict[str, Any]) -> int:
    if state.get("confirmed_label"):
        if int(state.get("same_confirmations", 0) or 0) >= int(getattr(config, "required_same_confirmations", 1) or 1):
            return max(1, int(getattr(config, "stable_stride_intervals", 4) or 4))
        return max(1, int(getattr(config, "verify_stride_intervals", 2) or 2))
    attempts = int(state.get("attempts", 0) or 0)
    fast_attempts = int(getattr(config, "fast_attempts", 2) or 2)
    medium_attempts = int(getattr(config, "medium_attempts", 2) or 2)
    if attempts < fast_attempts:
        return max(1, int(getattr(config, "fast_stride_intervals", 1) or 1))
    if attempts < fast_attempts + medium_attempts:
        return max(1, int(getattr(config, "medium_stride_intervals", 2) or 2))
    return max(1, int(getattr(config, "slow_stride_intervals", 4) or 4))


def retry_delay_ms(
    *,
    state_name: str,
    base_delay_ms: float,
    heartbeat_ms: float,
    identity_bucket: bool = False,
    open_unknown_retry: bool = False,
    cooldown_heartbeats: int = 1,
    differencer: Any | None = None,
) -> RetryDelayDecision:
    base = max(1.0, float(base_delay_ms or 1.0))
    heartbeat = max(1.0, float(heartbeat_ms or base))
    multiplier = 1
    reason = "base_retry"
    cooldown = max(1, int(cooldown_heartbeats or 1))
    if state_name == "unknown_cooldown" and open_unknown_retry:
        multiplier = effective_retry_multiplier(heartbeat, cooldown, differencer)
        reason = "unknown_cooldown"
    elif state_name == "identity_min_cooldown" and identity_bucket:
        multiplier = effective_retry_multiplier(heartbeat, cooldown, differencer)
        reason = "identity_min_cooldown"
    elif state_name == "fixed_sample_retry":
        multiplier = effective_retry_multiplier(heartbeat, cooldown, differencer)
        reason = "fixed_sample_retry"
    delay = max(base, heartbeat * multiplier)
    return RetryDelayDecision(delay_ms=float(delay), heartbeat_ms=float(heartbeat), multiplier=int(multiplier), reason=reason)


def effective_retry_multiplier(heartbeat_ms: float, cooldown_heartbeats: int, differencer: Any | None = None) -> int:
    if differencer is not None:
        try:
            return max(1, int(differencer.effective_multiplier(heartbeat_ms, cooldown_heartbeats)))
        except Exception:
            pass
    return max(1, int(cooldown_heartbeats or 1))


def metric_percentile(metrics, name: str, percentile_name: str) -> float:
    if metrics is None:
        return 0.0
    fn = getattr(metrics, percentile_name, None)
    if fn is None:
        return 0.0
    try:
        return max(0.0, float(fn(name) or 0.0))
    except Exception:
        return 0.0


def normalize_bucket_name(name: str) -> str:
    return str(name or "").strip().lower()
