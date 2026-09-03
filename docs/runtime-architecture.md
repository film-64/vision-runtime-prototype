# Runtime architecture

## Purpose

This document describes the stable runtime boundary represented by the `yoloe26-smoke` baseline. It does not document later Observation / Attention research and it does not claim that this showcase contains the complete original application.

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

## Detector boundary

Pose and YOLOE should be understood as separate detector capabilities. They had different input/use-case paths and could coexist in the runtime. A particular route could prefer Pose for full-frame person/keypoint work while YOLOE remained available for full-frame or task/object-region work.

Therefore this architecture should not be summarized as "Pose replaced YOLOE."

## What this showcase extracts

The public package keeps four small, model-free parts of the runtime control layer:

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

## Public verification boundary

The tests in this repository use synthetic values only. They demonstrate the behavior of the extracted control contracts without requiring model weights, videos, OCR assets, Redis, Qt, GPU support, or the original application configuration.

Historical model execution is documented separately under `docs/evidence/`. Those reports are evidence that the larger 26 baseline was exercised and measured; they are not bundled as a public reproduction environment.
