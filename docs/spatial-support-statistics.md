# Spatial support statistics

This page describes a small engineering concept used in the source project: measuring the spatial distribution of detector/probe outputs without treating those outputs as complete objects or semantic truth.

The current work should be read as **spatial support statistics**, not as academic Information Geometry, not as human-perceived object geometry, and not as a persistent world model.

## What is being measured

A visual capability may return regions, boxes, points, or other bounded observations. Each observation is tied to a source/frame context and provenance.

The source project can derive measurements such as:

```text
position / size / area
pairwise gap / overlap / containment
coverage and local density
scatter / covariance / principal direction
support relations and ambiguity
```

These are machine-side measurements of returned spatial evidence. They are useful for describing where current evidence is concentrated and how observations relate to one another.

They do not by themselves establish:

```text
a semantic object identity
a human-visible object boundary
a persistent physical shape
hidden content
world geometry
```

## Practical role in Observation

The engineering flow is:

```text
visual capability / detector / probe
        |
        v
bounded observations
        |
        v
spatial measurements and support statistics
        |
        v
current support state / uncertainty
        |
        v
Observation maintenance
        |
        +--> reuse current information
        +--> validate it
        +--> request stronger observation when needed
```

The measurements help Observation reason about the current spatial support of information. They do not execute models or own scheduling.

## Current public boundary

The public repository does not publish the full private implementation of these statistics or the source project's detailed grouping/acceptance logic. The public code only exposes the narrower Evidence and Information-state contracts used to demonstrate provenance, freshness, historical visibility, and explicit evidence linkage.

Existing private implementation names may still contain `InformationGeometry` or similar historical terminology. Those names should be read as legacy implementation names, not as a claim that the project implements the academic field of Information Geometry.

The current source work described here stops at spatial measurements, support relations, and derived support-state summaries. This showcase does not claim a separate higher-order geometry subsystem.
