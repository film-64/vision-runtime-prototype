# Runtime architecture

## Purpose

This document describes the stable runtime boundary represented by the `yoloe26-smoke` baseline and the limited public Observation slice extracted from later work. It does not document the complete Observation / Attention research path and it does not claim that this showcase contains the complete original application.

## Original runtime shape

The development system connected perception work to a managed execution runtime rather than treating every model as an unconditional per-frame call.

```text
Frame source
    |
    v
Main perception
  detector / pose / tracking
    |
    v
Capability and artifact work
    |
    v
Runtime control
  admission
  schedule state
  detector-time deadlines
  queue / latency metrics
    |
    v
Specialist execution
    |
    v
Result merge + persistent state
    |
    +----> metrics / health feedback ----+
                                         |
                                         +--> next scheduling decision
```

The source runtime used a single scheduling authority for work admission/submission. Control policies could change effective runtime frequency or priority, but were not intended to create a second hidden execution path.

## Observation boundary

The later Observation work asks what is already known, why it is currently believed, whether that evidence is still usable, and whether stronger observation is justified.

Its public placement is deliberately upstream of the existing runtime authority:

```text
perception / existing information
        |
        v
Observation
  evidence provenance
  freshness / uncertainty
  carried information
  spatial-support proposal
        |
        v
capability request / task shaping
        |
        v
existing admission + scheduler
        |
        v
specialist execution
        |
        v
new evidence / updated information
```

Observation may construct evidence or propose what is worth observing. It does not directly submit semantic tasks, create a second queue, or take ownership of admission and scheduling.

The public `vision_runtime.observation` package keeps only evidence and information-state contracts. The larger source system contains additional experimental mechanisms that are intentionally not reproduced here.

## Detector boundary

Pose and YOLOE should be understood as separate detector capabilities. They had different input/use-case paths and could coexist in the runtime. A particular route could prefer Pose for full-frame person/keypoint work while YOLOE remained available for full-frame or task/object-region work.

Therefore this architecture should not be summarized as "Pose replaced YOLOE."

## What this showcase extracts

The public package keeps four small, model-free runtime-control parts plus a small Observation contract slice.

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

`vision_runtime.runtime_health.RuntimeHealthMonitor` derives `ok`, `watch`, `degraded`, or `critical` state from latency tails, queue pressure, stale work and scene volatility. Hysteresis prevents immediate recovery from a short clear period.

### Observation evidence

`vision_runtime.observation.EvidenceStore` keeps append-only evidence versions scoped by source and generation. Material updates advance versions; historical queries do not expose versions produced by later frames; freshness and invalidation remain explicit.

### Observation information state

`vision_runtime.observation.InformationState` keeps carried information linked to the exact evidence refs declared to support it. It reports whether those refs remain fresh at a requested frame but does not decide which model should run next.

## Public verification boundary

The tests in this repository use synthetic values only. They demonstrate the behavior of the extracted control and Observation contracts without requiring model weights, videos, OCR assets, Redis, Qt, GPU support, or the original application configuration.

Historical model execution and later bounded Observation experiments are documented separately under `docs/evidence/`. Those reports are evidence that the larger development system was exercised and measured; they are not bundled as a public reproduction environment.
