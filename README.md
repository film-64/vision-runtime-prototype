# vision-runtime-prototype

[中文说明](README.zh-CN.md) | English

A curated public extraction from a larger private visual-perception project.

This repository is a **job-application showcase**. It presents selected runtime-control code, a small Observation contract slice, synthetic verification, and bounded historical experiment summaries. It is not the full application and does not claim to reproduce the complete private system.

## What this repository demonstrates

The public code and evidence are intended to show a few concrete engineering behaviors:

- latency, queue and runtime metrics;
- detector-index time semantics and stale-work rejection;
- scheduling state and runtime-frequency decisions;
- runtime-health classification with hysteresis and pressure-aware actions;
- versioned evidence with source/generation provenance, freshness and history;
- carried information that explicitly cites its supporting evidence;
- a deterministic synthetic metadata path through projection, async commit, package, verify and replay;
- bounded historical measurements for sparse/local perception paths.

## Engineering problem

The source project explores continuous visual processing under limited compute.

A simple per-frame pipeline can repeatedly run expensive capabilities even when previously acquired information is still usable. The project therefore experiments with separating three questions:

```text
what information is already available?
what evidence currently supports it?
what work is actually needed now?
```

The practical goals are reuse, bounded recomputation, stale-work rejection, and keeping model execution under one scheduling authority.

## System context

The larger private project connects multiple visual capabilities to a managed runtime:

```text
Frame / previous results
        |
        v
Observation state
  information + evidence
  freshness / validity
        |
        v
reuse / validate / request work
        |
        v
Runtime control
  admission / schedule state
  deadlines / queue / latency
        |
        v
Global TaskScheduler
        |
        v
visual capabilities
  Pose / YOLOE / OCR recognition / other specialists
        |
        v
results / persistent state / metadata
        |
        +--------------------> Observation update
```

Observation does not replace the scheduler and does not execute specialist models directly. It keeps explicit state about what information is available and what evidence supports that information.

The public repository implements only a narrow part of this larger flow.

## Observation

`Observation` is the project name for the shared state/contract layer around already-acquired visual information.

The public package currently exposes two small mechanisms:

- `EvidenceStore`: append-only evidence versions scoped by source/generation, with freshness, invalidation and historical visibility;
- `InformationState`: carried information linked to exact evidence refs.

This is enough to demonstrate the ownership boundary, but not the complete private maintenance logic or model-selection policy.

See [docs/observation.md](docs/observation.md).

## Spatial support statistics

Some private source work measures the spatial distribution of detector/probe outputs using gaps, overlap, containment, coverage, scatter, density and related support descriptors.

In this showcase that work is described as **spatial support statistics**. It is not presented as academic Information Geometry, human-perceived object geometry, or a completed world model.

See [docs/spatial-support-statistics.md](docs/spatial-support-statistics.md).

## Runtime-control extraction

The public runtime-control core keeps four model-free behaviors from the earlier runtime baseline:

- metrics and jitter filtering;
- detector-time deadlines and stale rejection;
- scheduling state/frequency decisions;
- runtime-health state with hysteresis.

Pose and YOLOE were separate detector capabilities in the source system. A route could prefer one capability for a task without replacing the other architecturally.

See [docs/runtime-architecture.md](docs/runtime-architecture.md).

## Repository contents

```text
vision_runtime/
  metrics.py                 latency, counters, gauges, jitter filtering
  time_semantics.py          detector clock, watermark and deadline decisions
  schedule_core.py           runtime-frequency / heartbeat state decisions
  runtime_health.py          pressure, tail-latency and hysteresis decisions
  observation/
    evidence.py              evidence provenance, versioning, freshness, history
    information_state.py     carried information linked to explicit evidence

dynamic_pipeline/core/      narrow metadata contracts used by the synthetic E2E path
roi_app/                     extracted async commit/package/replay support
scripts/generate_public_evidence.py
                             deterministic synthetic E2E evidence harness

tests/                       synthetic, model-free contract tests
config/                      sanitized runtime-policy excerpt
docs/runtime-architecture.md
docs/observation.md
docs/spatial-support-statistics.md
docs/publication-boundary.md
docs/evidence/               historical summaries + frozen synthetic snapshot
examples/                    small model-free demonstrations
```

`dynamic_pipeline/` and `roi_app/` contain only the support required for the public synthetic path. They are not a release of the complete application.

## Lightweight verification

The extracted runtime-control and Observation contracts can be exercised without model weights or private media:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
python examples/runtime_control_demo.py
python examples/observation_contract_demo.py
```

Passing these commands verifies the curated public slice and its current test oracle. It does not demonstrate comprehensive quality of the full private system.

The synthetic metadata chain can also be regenerated:

```bash
python scripts/generate_public_evidence.py --output-dir /tmp/public-metadata-evidence
```

That path uses deterministic synthetic input, the extracted runtime projection, bounded asynchronous metadata commit, package/index/archive creation, the existing verifier, and `ReplayRuntime`. GitHub Actions reruns the same path and uploads a commit-scoped artifact.

## Historical execution evidence

The private source archived several dated experiments. This showcase carries sanitized summaries with explicit claim boundaries.

| Evidence | What it demonstrates |
| --- | --- |
| [YOLO26 Pose sparse / ONNX](docs/evidence/yolo26-pose-sparse-onnx.md) | measured sparse-target path, PT/ONNX parity, native ONNX Runtime execution |
| [OCR region-shape performance](docs/evidence/ocr-region-performance.md) | measured cost/candidate trade-offs for coarse ROI materialization |
| [YOLOE26 fused/local path](docs/evidence/yoloe26-fused-local.md) | measured fused-vs-dynamic and dense-vs-coordinate-local execution |
| [Motion-selected region person detection](docs/evidence/motion-selected-region-person.md) | cheap CV evidence selecting a smaller region before person-detector computation |
| [Temporal spatial reuse](docs/evidence/temporal-spatial-reuse.md) | sparse validation and event-driven rebuild versus eager per-frame spatial processing |
| [Synthetic metadata E2E snapshot](docs/evidence/current-synthetic-metadata-e2e/README.md) | current public projection/commit/package/verify/replay path |

Historical benchmark summaries are validation snapshots, not current performance guarantees. The synthetic E2E result is model-free verification of the extracted path, not a real-model performance result.

## Development approach and authorship

The source project is heavily AI-agent-assisted. Coding agents produce much of the implementation and many tests/documents.

My role is primarily to define requirements and behavioral constraints, ask different agents to implement/review/check work, inspect outputs and measured results, and revise the requirements or component boundaries when the result does not match the intended behavior.

This repository therefore does not imply unaided authorship of every implementation detail. It also does not treat green tests as proof that the entire private system is comprehensively validated.

## Publication boundary

The repository intentionally excludes private media, model weights, identity material, the complete application/model-integration stack, unpublished experimental mechanisms, detailed private policies/heuristics, and the full internal development history.

See [docs/publication-boundary.md](docs/publication-boundary.md).

## License

The extracted source code follows GNU Affero General Public License v3.0. Third-party model/runtime artifacts are not redistributed here. See `THIRD_PARTY_NOTICES.md` for scope notes.
