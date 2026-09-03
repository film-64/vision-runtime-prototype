# Information-Support Geometry

This page exposes only the current public abstraction of Information-Support Geometry (ISG). It does not publish the mathematical construction, rule derivation, counterexample set, threshold-selection process, or research path that produced the model.

## Public role

ISG is an intermediate spatial-evidence representation used by Observation.

Its job is not to identify the world by itself. It gives the runtime a structured way to carry spatial evidence forward so that later Observation decisions can ask:

```text
what spatial information is currently supported?
where does that support apply?
which evidence produced it?
is that evidence still valid enough to reuse?
is stronger observation needed?
```

## Public evidence abstraction

The public description keeps only a few concepts.

### Observed regions

A region is a spatial observation tied to a source/frame context and explicit provenance. It may originate from a detector, a perception stage, or another visual measurement.

A region is evidence about an area of the current view. It is not automatically a semantic object or permanent scene entity.

### Information supports

ISG can carry spatial supports that let Observation refer to evidence-backed parts of the view as maintainable information units.

A support records that some spatial information has enough evidence to be represented and revisited. The public repository does not expose the mathematical rules used to construct or accept those supports.

### Relations and coverage

Supports may carry explicit spatial relations and coverage information so that Observation can reason about where evidence exists in the current view and how supported regions relate to one another.

These descriptors are evidence state, not semantic truth.

### Evidence maturity and validity

Spatial information may be provisional, strengthened by later evidence, reused while still valid, or invalidated when its supporting evidence is no longer sufficient.

A change in evidence maturity is not automatically a physical change in the scene. Provenance, freshness and uncertainty remain part of the state.

## Runtime position

The public relationship is:

```text
visual measurements / model outputs
        |
        v
spatial evidence
        |
        v
ISG support + relation + validity state
        |
        v
carried Information
        |
        v
reuse / validate / request stronger observation
        |
        v
existing runtime admission + scheduler
```

ISG does not execute models and does not create a second scheduling authority.

## Public scope

This repository intentionally does not publish:

- the mathematical construction of ISG;
- topology or geometry acceptance rules;
- the counterexample and rejection set used during model formation;
- production thresholds or calibration procedure;
- OCR-specific evidence-construction and activation strategy;
- literature mapping, hypothesis evolution, or other research-path material;
- future Observation research directions.

The public goal is only to show the role ISG plays inside Observation and the kinds of spatial evidence it is designed to carry.
