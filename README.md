# vision-runtime-prototype

A curated, evidence-backed extraction of runtime-control and selected Observation mechanisms from a larger private visual-perception development repository.

This repository is a job-application showcase. It is intentionally narrower than the original system: it demonstrates runtime control behavior, architecture boundaries, selected Observation contracts, tests, and bounded execution evidence without redistributing private media, model weights, face data, or the complete research history.

## Scope

The extracted control core keeps four behaviors from the `yoloe26-smoke` runtime baseline:

- latency/queue/runtime metrics;
- detector-index time semantics and stale-work rejection;
- scheduling state and runtime-frequency decisions;
- runtime-health classification with hysteresis and pressure-aware actions.

A later public Observation slice adds two small contracts:

- versioned evidence with source/generation provenance, freshness and historical visibility;
- carried information state that explicitly points back to the evidence supporting it.

The original runtime was much broader. It connected frame input, detector/pose/tracking perception, capability/artifact DAG work, scheduling/admission, specialist execution, persistent state, metadata, replay, and higher-level control. The public extraction is a runnable projection of selected mechanisms, not a miniature copy of the complete private application.

## Long-term motivation

The project is not centered on a single detector or a single product form. Its long-term motivation is a persistent visual companion: a system that can remain present over time, selectively observe its surroundings, maintain useful state, acquire stronger evidence when necessary, and reuse what it already knows instead of recomputing the world from scratch.

That substrate could support very different product forms — wearable assistance, local security, visual search and recognition, or personal daily records — without treating each one as a completely separate perception stack.

The source project therefore accumulated many experimental requirements and capabilities. They were not all intended to survive unchanged. A common development pattern was:

```text
temporarily stable runtime substrate
        -> new capability / requirement
        -> runnable implementation
        -> run / profile / inspect
        -> exposed boundary or collision
        -> narrow / rename / re-own / remove
        -> deeper recombination
        -> next temporarily stable substrate
```

This repository does not present that history as a clean top-down product architecture. The implementation grew through exploration, and later work increasingly consolidated the shared problems behind that growth.

## System context

The larger private project explores runtime infrastructure around continuous visual inference rather than a conventional model wrapper. Its architecture combines higher-level goals, static graph-defined perception requirements, a protected Observation substrate, runtime specialization, admission and scheduling, heterogeneous perception capabilities, learned execution feedback, and persistent state.

Architecture maturity is intentionally uneven. The following diagram is system context, not a claim that every control loop is complete or equally mature:

```text
                 Agent / goal control
                         |
                 Static DAG authoring
                         |
                observation requirements
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
          | cost / utility estimates         |
          | guarded learning                 |
          | spatial / semantic reuse         |
          | admission                        |
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

In the current private runtime, scheduling is more than FIFO dispatch. Existing runtime state and load control constrain candidate capacity; admission can rank legal candidates using utility/cost information and consume an estimated execution-cost budget; selected online-learning domains can make guarded changes inside existing safety and legality boundaries. The execution authority remains the scheduler.

This should **not** be read as a completed global learned orchestrator. Broader cross-DAG optimization, semantic scheduling policy, total task staggering, and the full interaction between offline/online learning and higher-level agent control remain outside the claims made by this public extraction. Observation can progressively change what becomes scheduler-visible work without bypassing scheduler ownership.

A simplified current execution chain is therefore closer to:

```text
existing legal runtime space
        -> load / capacity constraints
        -> candidate set
        -> limited guarded adaptation
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

The architectural analogy is closer to a resource-constrained visual cortex than to a conventional inference API: maintain enough observation to keep the system situated, then pay for stronger semantic acquisition only when current information is insufficient. This is an architectural analogy, not a claim of biological modeling.

See [docs/observation.md](docs/observation.md) for the public mechanism, [docs/information-support-geometry.md](docs/information-support-geometry.md) for the public spatial-evidence abstraction, and [docs/research-boundary.md](docs/research-boundary.md) for what is intentionally not published.

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

`dynamic_pipeline/` and `roi_app/` are not a publication of the full source application. They contain only the real metadata projection/commit/package/archive/replay support required for the public synthetic E2E path. Scheduler/task internals, model-specific Pose/OCR helpers, UI replay behavior, migration adapters, and unrelated source-application utilities are intentionally excluded.

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

## Provenance

The runtime-control slice was curated from `film-64/Vision-product`, branch `yoloe26-smoke`, source snapshot:

`701333cbf1d019a662c18846f8a812ccf763a5e1`

The selected Observation contracts and later validation summaries were curated from subsequent `gate-tool-2` work. The private source repository contains substantially more application code, local assets, experiments, research notes and unfinished development than this showcase.

Development was agent-assisted and implementation-led. A common loop was rough capability hypothesis -> high-bandwidth agent-assisted runnable implementation -> run/test/profile -> mismatch or new boundary -> requirement or ownership refinement -> repeat. New ideas were usually placed on a temporarily stable runtime substrate first; later development could narrow them, remove them, rename their ownership, or combine them more deeply once their shared requirements became visible.

Agent assistance was not treated as a substitute for domain learning. In several phases, implementation breadth could grow faster than the developer's theoretical understanding of the system. Runnable artifacts then exposed concrete gaps — unfamiliar model behavior, scheduling constraints, evidence-lifetime problems, performance bottlenecks, or conflicting abstractions — that forced deeper study. That new knowledge changed the interpretation of the artifact and often changed the architecture itself.

The development loop was therefore reciprocal rather than one-way automation:

```text
partial understanding
        -> agent-assisted implementation probe
        -> runnable system behavior
        -> exposed knowledge boundary
        -> deeper study / measurement
        -> stronger system model
        -> redefinition / consolidation
        -> next implementation probe
```

The earlier runtime therefore accumulated real scope growth, migration residue and partially competing abstractions. Later Observation work did not erase that history; it became the current convergence point for questions that had repeatedly appeared across scheduling, spatial reuse, evidence lifetime, model specialization and persistent state. It also introduced more explicit separation between current design, historical exploration, validation evidence, and still-open concepts.

The public repository presents converged slices and bounded evidence rather than reproducing every exploratory implementation or implying unaided authorship of every implementation detail.

## What is intentionally not included

- model weights or generated model checkpoints;
- private/original media and decoded frame caches;
- face databases or identity material;
- machine-local configuration and absolute paths;
- the complete source application's scheduler/task/model/UI implementation;
- the private static DAG editor and higher-level agent implementation;
- the complete online/offline learning implementation and internal control policies;
- the complete Observation / Attention research path, literature map and internal handoff documents;
- unpublished OCR evidence-construction and activation strategy;
- private model-specialization implementation details;
- future Observation research roadmap;
- original Git history;
- a claim that the complete historical system is clone-and-run reproducible.

## License

The extracted source code follows the license of the source repository: GNU Affero General Public License v3.0. Third-party model/runtime artifacts are not redistributed here. See `THIRD_PARTY_NOTICES.md` for scope notes.
