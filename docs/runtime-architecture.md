# Runtime architecture

## Purpose

This document describes the runtime boundary represented by the `yoloe26-smoke` baseline plus the small public Observation contract slice. It is a showcase of selected engineering mechanisms, not a complete copy of the private application.

## Original runtime shape

The development system connected perception work to a managed execution runtime instead of treating every model as an unconditional per-frame call.

```text
Frame source
    |
    v
Perception capabilities
  detector / pose / tracking / specialists
    |
    v
Task and artifact requirements
    |
    v
Runtime control
  admission
  schedule state
  detector-time deadlines
  queue / latency metrics
    |
    v
TaskScheduler
    |
    v
Capability execution
    |
    v
Result merge + persistent state
    |
    +----> metrics / health feedback ----+
                                         |
                                         +--> next scheduling decision
```

The source runtime used one scheduling authority for work admission/submission. Control policies could change effective frequency or priority, but did not create a second hidden execution path.

## Observation boundary

The later Observation work adds explicit state around already-acquired information and its supporting evidence.

```text
perception result / existing information
        |
        v
Observation
  evidence provenance
  freshness / validity
  carried information
  spatial support state
        |
        v
reuse / validate / request more work
        |
        v
existing admission + scheduler
        |
        v
capability execution
        |
        v
new evidence / updated information
```

Observation does not execute specialist models and does not own scheduler admission. It maintains state that can affect what work becomes necessary.

The public `vision_runtime.observation` package currently exposes only evidence and information-state contracts. The larger private source contains additional experimental maintenance and task-construction logic that is not reproduced here.

## Detector boundary

Pose and YOLOE are separate detector capabilities. They have different input/use-case paths and can coexist in the runtime. A route may prefer Pose for one task and YOLOE for another; that should not be summarized as one detector replacing the other architecturally.

OCR recognition and other specialist capabilities remain separate from detector/probe-side region acquisition.

## What this showcase extracts

The public package keeps four small model-free runtime-control parts plus a small Observation contract slice.

### Metrics

`vision_runtime.metrics.RuntimeMetrics` records latency distributions, counters, gauges and labels. A jitter filter can exclude warmup and bounded one-off spikes from effective scheduling metrics while retaining raw observations.

### Detector-time semantics

`vision_runtime.time_semantics` models a detector-index clock, a watermark and task deadlines. Work can be rejected before execution or at merge time when its deadline falls behind the allowed watermark.

### Schedule state

`vision_runtime.schedule_core` separates result semantics from model names:

- dynamic-result work can stay input-driven;
- defined-result work can move to lower frequency after a concrete result;
- completed fixed-result work can stop;
- protected chain artifacts remain high-frequency;
- coarse detector cadence can switch scheduling from heartbeat-offset behavior to new-result-driven behavior.

### Runtime health

`vision_runtime.runtime_health.RuntimeHealthMonitor` derives `ok`, `watch`, `degraded`, or `critical` state from latency tails, queue pressure, stale work and scene volatility. Hysteresis prevents immediate recovery after a short clear period.

### Observation evidence

`vision_runtime.observation.EvidenceStore` keeps append-only evidence versions scoped by source and generation. Material updates advance versions; historical queries do not expose versions produced by later frames; freshness and invalidation remain explicit.

### Observation information state

`vision_runtime.observation.InformationState` keeps carried information linked to the exact evidence refs declared to support it. It reports whether those refs remain fresh at a requested frame but does not decide which model should run next.

## Spatial support terminology

Some private source work measures detector/probe outputs using spatial statistics such as gaps, overlap, coverage, scatter, density and support relations. In this showcase that work is described as **spatial support statistics**.

It should not be read as academic Information Geometry or as a claim that the system has reconstructed human-perceived object geometry. See [spatial support statistics](spatial-support-statistics.md).

## Public verification boundary

The tests in this repository use synthetic values only. They demonstrate the behavior of the extracted control and Observation contracts without requiring model weights, videos, OCR assets, Redis, Qt, GPU support, or the original application configuration.

Historical model execution and bounded source-project experiments are documented separately under `docs/evidence/`. Those reports show that specific paths were exercised and measured under stated conditions; they are not a public reproduction environment for the full private system.
