# Information-Support Geometry

This page exposes a limited engineering boundary from the later Observation work. It does not publish the research path, literature mapping, threshold-search process or future acquisition policy.

The problem starts with a common mistake: treating detector rectangles as if they were already a stable description of the world.

The public model keeps four things separate:

```text
support topology
    !=
geometry dimension
    !=
spatial-partition occupancy
    !=
evidence maturity
```

## What that separation prevents

A few counterexamples are enough to show why the separation matters:

- one large rectangle can span several viewport partitions while remaining one support;
- several rectangles inside one partition can still represent multiple independent supports;
- dense detector output does not by itself prove stable two-dimensional structure;
- three supports do not automatically form a well-conditioned triangle;
- a change from provisional detector candidates to recognition-confirmed candidates is evidence maturation, not automatically physical scene motion.

The intended construction is therefore closer to:

```text
real observed rectangles
        |
        v
typed spatial measurements
        |
        v
support hypotheses + weak relations + ambiguity
        |
        v
local geometry descriptors
        |
        v
spatial-view / global-geometry candidates
```

A support hypothesis is not semantic truth. A geometry candidate is not automatically accepted stable geometry.

## Measurements before conclusions

The source implementation records measurements such as rectangle size and area, center displacement, exact boundary gap, overlap, containment, size ratios, local scatter and support extent before stronger interpretation is attempted.

Two rules are intentionally preserved in the public description:

1. Center distance alone is not a sufficient proximity fact; rectangle boundaries and footprint matter.
2. Partition occupancy is descriptive. It must not manufacture additional independent supports or fake geometry vertices.

Synthetic cases are useful for rejecting broken rules, but they do not establish production thresholds for real OCR or detector distributions.

## Evidence boundary

The same geometric constructor can be applied to different evidence stages. For example, provisional perception rectangles and later confirmed rectangles may produce different geometry because the evidence matured.

That geometry change must not be confused with camera motion or scene evolution. Temporal spatial maintenance requires real image measurements or explicit transforms; derived box centers or partition labels are not substitutes for pixel correspondences.

## Public scope

This repository publishes the invariants above because they explain why Observation cannot treat model output as world truth. It intentionally omits:

- production acceptance thresholds;
- full topology and geometry-construction implementation;
- OCR-specific evidence acquisition strategy;
- research notes, cross-domain references and hypothesis history;
- future Observation roadmap.
