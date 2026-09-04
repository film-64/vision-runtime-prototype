# Observation

`Observation` is the project name for a shared runtime state/contract layer around visual information. It is an engineering abstraction used to answer a practical question:

> Given what the system already has, can the current information still be reused, does it need validation, or should another visual capability run?

It is not a model, not a second scheduler, and not a claim of general scene understanding.

## Runtime position

A simplified flow is:

```text
perception result / existing information
        |
        v
Observation state
  information + evidence refs
  freshness / validity
  uncertainty / spatial support
        |
        v
reuse / validate / request more work
        |
        v
existing runtime control
  admission + scheduling + deadlines
        |
        v
specialist capability
        |
        v
new result / new evidence
```

The public `vision_runtime.observation` package is intentionally smaller than this full source-project flow. It currently exposes only two narrow contracts:

- versioned evidence with source/generation provenance, freshness, invalidation, and historical visibility;
- carried information that explicitly cites the evidence supporting it.

The public package does not implement the complete private maintenance logic or model-selection policy.

## Why this exists

Continuous visual processing can waste compute if every capability reruns at full scope on every frame. The source project therefore experiments with separating three questions:

```text
what information is already available?
what evidence currently supports it?
what additional computation is actually needed now?
```

The goal is operational reuse and bounded recomputation, not a universal optimizer.

## Example: selecting a smaller detector region

One historical feasibility test used short frame history plus camera-motion-compensated residual-flow evidence to select a continuous region before running the person branch of a local Pose model.

Across the bounded 14 measured frames, the regional path retained all 48 full-frame reference person boxes while processing 61.93% of the active area on average. Complete-path p50 fell from 217.1164 ms to 131.8110 ms, a 39.3% reduction in that window.

The keypoint head was disabled. This result supports selective person-detector computation on that sample; it is not a posture-accuracy result or a production threshold. See [motion-selected region person detection](evidence/motion-selected-region-person.md).

## Example: reusing spatial state between frames

A separate 96-frame replay compared eager per-frame spatial processing with an event-driven path that reused state between sparse validation opportunities and rebuilt only when cheaper evidence failed.

Measured compute fell from 1961.27 ms to 304.95 ms in that replay, with mean source-frame compute falling from 20.43 ms to 3.18 ms. The recorded compute reduction was 84.45%.

This supports lazy temporal maintenance on that sample. It does not prove semantic quality and excludes decode, scheduler contention, memory pressure, and target-device transforms. See [temporal spatial reuse](evidence/temporal-spatial-reuse.md).

## Spatial support statistics

Some source-project work measures the spatial distribution of detector/probe returns: gaps, overlap, containment, coverage, scatter, density, principal direction, and related support descriptors.

These measurements are engineering statistics over machine-observed regions. They are not academic Information Geometry and should not be read as human-perceived object geometry or a persistent world model.

See [spatial support statistics](spatial-support-statistics.md) for the public terminology and boundary.

## Text is only one capability example

OCR-related experiments are present because text provides a useful case where region discovery and semantic recognition can be separated.

A detector-side result can first provide candidate regions. Recognition is a later semantic operation. The candidate regions are observations, not proof that the system has identified a complete object or understood the scene.

The same Observation contracts are intended to remain usable with other capabilities such as Pose, YOLOE, temporal measurements, and future detector/probe paths.

## Public boundary

The public repository shows selected contracts, tests, synthetic execution, and bounded historical measurements. It does not reproduce the full private application or its unfinished/experimental policies.

See [publication boundary](publication-boundary.md) for the exact scope.
