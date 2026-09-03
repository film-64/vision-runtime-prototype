# Observation

This repository exposes a small, testable slice of the later Observation work from the source system. It publishes the resulting runtime ideas and selected validation evidence, not the research path that produced them.

The operational question is simple:

> Given what the system already knows, is the current evidence still sufficient, or is stronger observation worth paying for?

Two practical forms of that question are used in this showcase:

```text
Where is additional visual computation worth spending?
When is previously acquired information no longer safe to reuse?
```

## Runtime position

Observation is not a second scheduler and does not own model execution.

```text
Perception / existing information
        |
        v
Observation state
  information + evidence
  freshness / uncertainty
  spatial support
        |
        v
capability request / task shaping
        |
        v
existing runtime control
  admission + scheduling + deadlines
        |
        v
specialist execution
        |
        v
new evidence / updated information
```

The public Observation package therefore owns only evidence and carried-information contracts. Existing runtime-control code continues to own admission, scheduling and execution decisions.

## Evidence before stronger inference

The runtime does not need every available capability to run at full spatial scope on every frame. A cheaper measurement can first establish whether stronger work is justified.

One historical feasibility test used short frame history plus camera-motion-compensated residual-flow evidence to select a continuous region before running the person branch of a local Pose model. Across the bounded 14 measured frames, the regional path retained all 48 full-frame reference person boxes while purchasing 61.93% of the active area on average. Complete-path p50 fell from 217.1164 ms to 131.8110 ms, a 39.3% reduction in that window.

The keypoint head was disabled in this benchmark. The result supports selective detector computation; it is not a posture-accuracy result. See [motion-selected region person detection](evidence/motion-selected-region-person.md).

## Maintaining information over time

The second case asks whether already acquired spatial information must be rebuilt on every source frame.

A separate 96-frame replay compared eager per-frame spatial processing with an event-driven path that reused state between sparse validation opportunities and escalated only when cheaper evidence failed. Measured compute fell from 1961.27 ms to 304.95 ms in that replay, with mean source-frame compute falling from 20.43 ms to 3.18 ms. The recorded compute reduction was 84.45%.

This result supports lazy temporal maintenance on that sample. It does not prove that every selected region is semantically valuable, and it excludes decode, scheduler contention, memory pressure and target-device transforms. See [temporal spatial reuse](evidence/temporal-spatial-reuse.md).

## Public evidence ladder

The public material uses the following explanatory ladder:

```text
known information
      |
      v
reuse while current evidence remains sufficient
      |
      v
cheap structural / temporal validation
      |
      v
stronger spatial recovery when needed
      |
      v
regional detector or specialist work when justified
      |
      v
new evidence updates carried information
```

This is an explanation of staged evidence acquisition, not a claim that the repository contains a universal cost optimizer.

## Information-Support Geometry

Observation also needs a way to carry spatial evidence without treating every model output as permanent scene truth. The public ISG description therefore stays at the evidence level: observed regions, evidence-backed supports, spatial relations and coverage, provenance, freshness, uncertainty, and evidence maturity.

The internal mathematical construction and detailed acceptance logic are intentionally outside the public repository. See [information-support geometry](information-support-geometry.md) for the limited public abstraction.

## Why text becomes a harder example

Text is spatially explicit and can carry dense semantic information. Once text has been acquired, however, repeating recognition on every frame is not automatically justified.

That raises a harder Observation question: what evidence is sufficient to keep previously acquired text information usable, and when should stronger text observation be purchased again?

Detailed text-evidence construction, OCR activation policy, hypothesis evolution and the associated research path are intentionally outside this public repository. See [research boundary](research-boundary.md).
