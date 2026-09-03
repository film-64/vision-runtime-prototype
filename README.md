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

The original runtime was broader. At a high level it connected frame input, detector/pose/tracking perception, capability/artifact DAG work, scheduling/admission, specialist execution, and result/state feedback. The public Observation slice sits beside that runtime rather than replacing its scheduling authority.

```text
Frame source
    -> perception / existing information
    -> Observation evidence + information state
    -> capability / artifact work
    -> admission + scheduling + time semantics
    -> specialist execution
    -> result merge / persistent state
    -> runtime metrics + health feedback
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
docs/evidence/               historical summaries + current synthetic verification
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

That path uses deterministic synthetic input, the extracted runtime projection, bounded asynchronous metadata commit, package/index/archive creation, the existing package verifier, and `ReplayRuntime`. GitHub Actions reruns the same path and uploads an artifact named with the commit SHA.

## Historical execution evidence

The source repository archived dated experiments with explicit environment and timing boundaries. This showcase carries sanitized summaries rather than raw media, model artifacts, machine-local paths, or historical experiment directories.

| Evidence | What it demonstrates |
| --- | --- |
| [YOLO26 Pose sparse / ONNX](docs/evidence/yolo26-pose-sparse-onnx.md) | measured sparse-target path, PT/ONNX parity, native ONNX Runtime execution |
| [OCR region-shape performance](docs/evidence/ocr-region-performance.md) | measured cost/candidate trade-offs for coarse ROI materialization |
| [YOLOE26 fused/local path](docs/evidence/yoloe26-fused-local.md) | measured fused-vs-dynamic and dense-vs-coordinate-local execution |
| [Motion-selected region person detection](docs/evidence/motion-selected-region-person.md) | cheap CV evidence selecting a smaller region before person-detector computation |
| [Temporal spatial reuse](docs/evidence/temporal-spatial-reuse.md) | sparse validation and event-driven rebuild versus eager per-frame spatial processing |
| [Current synthetic metadata E2E](docs/evidence/current-synthetic-metadata-e2e/README.md) | current model-free projection/commit/package/verify/replay chain; not a model benchmark |

Historical benchmark summaries are validation snapshots, not current performance guarantees. The synthetic E2E package is current verification of the extracted metadata path and is explicitly not a real-model result.

## Provenance

The runtime-control slice was curated from `film-64/Vision-product`, branch `yoloe26-smoke`, source snapshot:

`701333cbf1d019a662c18846f8a812ccf763a5e1`

The selected Observation contracts and later validation summaries were curated from subsequent `gate-tool-2` work. The private source repository contains substantially more application code, local assets, experiments, research notes and unfinished development than this showcase.

Development was agent-assisted and implementation-led. A common loop was rough capability hypothesis -> agent-assisted runnable implementation -> run/test/profile -> mismatch or new boundary -> requirement or ownership refinement -> repeat. The earlier runtime accumulated migration and exploration residue through that process. Later Observation work added more explicit separation between current design, historical exploration, validation evidence, and still-open concepts. The public repository presents converged slices and bounded evidence rather than reproducing every exploratory implementation or implying unaided authorship of every implementation detail.

## What is intentionally not included

- model weights or generated model checkpoints;
- private/original media and decoded frame caches;
- face databases or identity material;
- machine-local configuration and absolute paths;
- the complete source application's scheduler/task/model/UI implementation;
- the complete Observation / Attention research path, literature map and internal handoff documents;
- unpublished OCR evidence-construction and activation strategy;
- future Observation research roadmap;
- original Git history;
- a claim that the complete historical system is clone-and-run reproducible.

## License

The extracted source code follows the license of the source repository: GNU Affero General Public License v3.0. Third-party model/runtime artifacts are not redistributed here. See `THIRD_PARTY_NOTICES.md` for scope notes.
