# vision-runtime-prototype

A curated, evidence-backed extraction of runtime-control and selected Observation mechanisms from a larger private visual-perception development repository.

This repository is a job-application showcase. It is intentionally narrower than the original system: it demonstrates runtime control behavior, architecture boundaries, selected Observation contracts, tests, and bounded execution evidence without redistributing private media, model weights, identity data, or the complete research history.

## Scope

The extracted control core keeps four behaviors from the 26-era runtime baseline:

- latency/queue/runtime metrics;
- detector-index time semantics and stale-work rejection;
- scheduling state and runtime-frequency decisions;
- runtime-health classification with hysteresis and pressure-aware actions.

A later public Observation slice adds two small contracts:

- versioned evidence with source/generation provenance, freshness and historical visibility;
- carried information state that explicitly points back to the evidence supporting it.

The original runtime was much broader. It connected frame input, multiple perception capabilities, graph-defined work, scheduling/admission, execution, persistent state, metadata, replay, and higher-level control. The public extraction is a runnable projection of selected mechanisms, not a miniature copy of the complete private application.

## Long-term motivation

The project is not centered on a single detector or a single product form. Its long-term motivation is a persistent visual companion: a system that can remain present over time, selectively observe its surroundings, maintain useful state, acquire stronger evidence when necessary, and reuse what it already knows instead of recomputing the world from scratch.

The same substrate could support multiple product forms, from wearable or local-monitoring use to visual search, recognition, and longer-lived personal context, without treating each use case as a completely separate perception stack.

The source project accumulated many experimental requirements and capabilities while keeping a temporarily stable runtime underneath them. New work was implemented, measured, narrowed, consolidated, or recombined as the shared constraints became clearer. The current architecture is therefore the result of iterative convergence rather than a single top-down design.

## System context

The larger private project explores runtime infrastructure around continuous visual inference rather than a conventional model wrapper. At a high level it combines higher-level control, graph-defined perception requirements, a protected Observation substrate, runtime specialization, admission and scheduling, heterogeneous perception capabilities, adaptive execution feedback, and persistent state.

The diagram below shows system context. The public repository implements only selected slices of it:

```text
                 Higher-level control
                         |
                graph-defined requirements
                         |
                         v
Frame ------------> OBSERVATION <------------- semantic feedback
                    protected substrate
                    information / evidence
                    maintenance / compute
                         |
                scheduler-visible need
                         |
                         v
          Runtime specialization + scheduling
          +----------------------------------+
          | capacity / load                  |
          | cadence / stale-work rejection   |
          | cost-aware admission             |
          | guarded adaptation               |
          | contextual reuse                 |
          +----------------+-----------------+
                           |
                           v
                   Global TaskScheduler
                           |
          +----------------+----------------+
          |                |                |
         OCR              Pose             YOLOE
       Identity        Appearance           ...
          +----------------+----------------+
                           |
                     semantic results
                           |
              +------------+------------+
              |                         |
       Observation evidence       persistent state /
                                  metadata / memory
```

The important distinction is that the system is not only deciding *which model to run*. Much of the 26-era exploration asked whether a general perception capability could be narrowed according to current runtime context: spatially, semantically, temporally, or computationally. Historical OCR, sparse Pose, temporal-reuse and YOLOE experiments in this repository are bounded examples of that direction rather than claims of a finished universal optimization layer.

In the current private runtime, scheduling is more than FIFO dispatch. Runtime state and load constraints shape candidate capacity; legal candidates can be ranked with cost/utility information and admitted under bounded execution budgets; selected adaptive paths can make guarded adjustments inside existing safety and legality boundaries. Execution authority remains with the scheduler.

The public extraction demonstrates bounded scheduling and adaptation behavior. It does not claim end-to-end global orchestration, nor does it publish the broader internal coordination and policy mechanisms used by the private system. Observation can progressively change what becomes scheduler-visible work without bypassing scheduler ownership.

A simplified current execution chain is therefore closer to:

```text
existing legal runtime space
        -> load / capacity constraints
        -> candidate set
        -> bounded adaptation
        -> cost-sensitive admission
        -> TaskScheduler
        -> perception execution
        -> result / persistent-state feedback
```

Pose and YOLOE were separate detector capabilities in the development system. A routing policy could prefer one path for a task; that should not be read as one detector replacing the other architecturally.

## Observation

The public Observation question is:

> Given what the system already knows, is the current evidence still sufficient, or is stronger observation worth paying for?

This repository demonstrates two narrow forms of that question:

```text
Where is additional visual computation worth spending?
When is previously acquired information no longer safe to reuse?
```

In the larger architecture, Observation is the current convergence point of the earlier runtime exploration. It is not intended as another post-processing specialist. It is a protected pre-semantic substrate for maintaining reusable visual information, supporting evidence, maintenance rules, and internal observation compute before ordinary semantic model work is admitted.

Observation can construct scheduler-visible work when registered requirements can no longer be satisfied by current state, and semantic results can feed back into Observation as new evidence. It does not directly execute specialist models or replace the Global Scheduler.

The public material intentionally exposes this ownership boundary more clearly than the private mechanisms behind it.

See [docs/observation.md](docs/observation.md) for the public mechanism, [docs/information-support-geometry.md](docs/information-support-geometry.md) for the public spatial-evidence abstraction, and [docs/research-boundary.md](docs/research-boundary.md) for the publication boundary.

## Repository contents

```text
vision_runtime/
  metrics.py                 latency, counters, gauges, jitter filtering
  time_semantics.py          detector clock, watermark and deadline decisions
  schedule_core.py           runtime frequency / heartbeat state decisions
  runtime_health.py          pressure, tail-latency and hysteresis decisions
  observation/
    evidence.py              evidence provenance, versioning, freshness, history
    information_state.py     carried information linked to explicit evidence
dynamic_pipeline/core/      narrow metadata evidence contracts and storage helpers
roi_app/                     extracted async commit/package/replay path used by evidence
scripts/generate_public_evidence.py
                             deterministic synthetic E2E evidence harness

tests/                       synthetic, model-free contract tests
config/                      representative sanitized runtime policy excerpt
docs/runtime-architecture.md
docs/observation.md
docs/information-support-geometry.md
docs/research-boundary.md
docs/evidence/               historical summaries + a frozen synthetic package snapshot
examples/                    small model-free demonstrations
```

`dynamic_pipeline/` and `roi_app/` are not a publication of the full source application. They contain only the support required for the public synthetic E2E path. Unrelated application, model-integration, internal-control, UI, migration, and private research code is intentionally excluded.

## Lightweight verification

The full historical vision stack is not reproduced here. The extracted control and Observation contracts are deliberately model-free and can be exercised independently:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
python examples/runtime_control_demo.py
python examples/observation_contract_demo.py
```

Passing these commands verifies the curated public slice, not the original detector/OCR/model environment.

The current synthetic metadata chain can also be regenerated without private media or model weights:

```bash
python scripts/generate_public_evidence.py --output-dir /tmp/public-metadata-evidence
```

That path uses deterministic synthetic input, the extracted runtime projection, bounded asynchronous metadata commit, package/index/archive creation, the existing package verifier, and `ReplayRuntime`. GitHub Actions reruns the same path and uploads an artifact named with the commit SHA. The checked-in evidence directory is a frozen browsable snapshot; the commit-scoped Actions artifact is the authoritative current execution record.

## Historical execution evidence

The source repository archived dated experiments with explicit environment and timing boundaries. This showcase carries sanitized summaries rather than raw media, model artifacts, machine-local paths, or historical experiment directories.

| Evidence | What it demonstrates |
| --- | --- |
| [YOLO26 Pose sparse / ONNX](docs/evidence/yolo26-pose-sparse-onnx.md) | measured sparse-target path, PT/ONNX parity, native ONNX Runtime execution |
| [OCR region-shape performance](docs/evidence/ocr-region-performance.md) | measured cost/candidate trade-offs for coarse ROI materialization |
| [YOLOE26 fused/local path](docs/evidence/yoloe26-fused-local.md) | measured fused-vs-dynamic and dense-vs-coordinate-local execution |
| [Motion-selected region person detection](docs/evidence/motion-selected-region-person.md) | cheap CV evidence selecting a smaller region before person-detector computation |
| [Temporal spatial reuse](docs/evidence/temporal-spatial-reuse.md) | sparse validation and event-driven rebuild versus eager per-frame spatial processing |
| [Synthetic metadata E2E snapshot](docs/evidence/current-synthetic-metadata-e2e/README.md) | browsable package shape; current per-commit projection/commit/package/verify/replay result is produced by Actions |

These benchmarks should be read together as examples of runtime specialization rather than unrelated model tuning: reducing spatial search, reusing temporal state, or changing the execution form of a general perception capability when the current task permits it.

Historical benchmark summaries are validation snapshots, not current performance guarantees. The synthetic E2E run is current model-free verification of the extracted metadata path and is explicitly not a real-model result; current provenance is carried by the commit-scoped Actions artifact.

## Development approach and provenance

This public repository was curated from multiple stages of a larger private development history. It preserves selected runtime-control mechanisms, later Observation contracts, and sanitized validation summaries while keeping the complete application and research path private.

Development was agent-assisted and implementation-led. Agent tools accelerated the conversion of rough capability hypotheses into runnable probes; measurement, code inspection, and domain study were then used to decide what to keep, redefine, consolidate, or remove. New understanding repeatedly fed back into architecture and ownership decisions.

A representative loop was:

```text
capability hypothesis
        -> agent-assisted runnable probe
        -> measurement / inspection
        -> focused domain study
        -> architecture refinement
        -> consolidation
        -> next probe
```

The public repository presents the converged, interview-relevant slices and bounded evidence from that process rather than the complete internal development graph.

## What is intentionally not included

- private media, model weights, identity material, or machine-local assets;
- the complete application and model-integration stack;
- internal control, adaptation, and orchestration mechanisms beyond the published slices;
- unpublished Observation/research mechanisms and model-specific optimization details;
- internal development history, handoff material, and private experimental artifacts;
- a claim that the complete historical system is clone-and-run reproducible.

## License

The extracted source code follows the license of the source repository: GNU Affero General Public License v3.0. Third-party model/runtime artifacts are not redistributed here. See `THIRD_PARTY_NOTICES.md` for scope notes.
