# Publication boundary

This repository is a job-application showcase, not a complete release of the source project.

## Included here

The public repository includes:

- selected runtime-control code;
- a small Observation contract slice for evidence provenance, versioning, freshness, history, and carried information;
- synthetic, model-free tests and an end-to-end metadata/package/replay verification path;
- sanitized summaries of several historical model/runtime experiments;
- explicit limitations for each published result.

## Not included here

The public repository intentionally excludes:

- private media, model weights, identity material, and machine-local assets;
- the complete application and model-integration stack;
- private scheduling, admission, adaptation, and model-specific policy details beyond the published slices;
- unpublished experimental branches and unfinished mechanisms;
- detailed internal heuristics, calibration values, and implementation notes that are not needed to understand the public artifact;
- the complete private Git history and internal development material.

The goal is to make the published engineering artifact inspectable without implying that the complete private system is reproduced here.

## Development provenance

Development of the source project is heavily AI-agent-assisted. Coding agents produce much of the implementation and many tests/documents. Requirements, behavioral constraints, reviews, cross-agent checks, and follow-up changes are driven through iterative interaction with those agents.

The public repository therefore presents code, tests, execution evidence, and their boundaries rather than implying unaided authorship or comprehensive validation of the full private system.
