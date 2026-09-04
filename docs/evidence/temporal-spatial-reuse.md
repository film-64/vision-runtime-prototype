# Temporal spatial reuse validation

This historical validation asked whether a weight-free Observation path could build spatial state from preselected candidate regions, reuse that state across a continuous shot, and rebuild after a scene transition at materially lower cost than eager per-frame processing.

## Recorded scope

- Source branch: `gate-tool-2`
- 96 decoded source frames; decode time excluded
- local CPU replay: Darwin x86_64, Python 3.11.13, OpenCV 4.10.0
- eager baseline: candidate Gate plus residual-flow/perspective processing on every source frame
- event-driven path: sparse validation opportunities, coarse structural watchdog, sparse anchor tracking, structural recovery only after cheaper evidence failed, and full candidate-region rebuild only when spatial evidence failed
- no OCR recognition
- no external model weights
- no runtime task entry or metadata write

The original media and raw replay environment are not redistributed here.

## Evidence depth used by the replay

```text
D0  cached state / freshness between validation opportunities
D1  coarse histogram + edge-density structural check
D2  sparse local feature tracking
D3  stronger structural re-anchor after D2 failure
D4  rebuild candidate regions and spatial state after evidence failure
```

The ordering was lazy: a stronger depth was not executed merely because it existed.

## Recorded result

| Measurement | Eager every frame | Event-driven |
| --- | ---: | ---: |
| Total measured compute, 96 frames | 1961.27 ms | 304.95 ms |
| Mean compute per source frame | 20.43 ms | 3.18 ms |
| p95 compute per source frame | 24.00 ms | 10.53 ms |
| Maximum observed frame compute | 50.72 ms | 12.29 ms |
| Compute reduction | - | 84.45% |

Additional recorded observations:

- 66 continuous-shot frames produced zero full candidate-region rebuilds;
- a strong view-disturbance window used nine anchor-reuse validations and zero structure/full rebuilds;
- continuous-window compute reduction ranged from 83.92% to 84.84%;
- a controlled hard transition produced exactly one full rebuild;
- under the deliberately worst interval-3 phase, transition detection occurred two source frames after the cut, about 66.7 ms at 29.97 FPS;
- the measured rebuild-frame cost was 12.14 ms.

## Interpretation boundary

The timing evidence is stronger than the semantic-value evidence. The source validation explicitly recorded that selected value-region quality was not yet proven against semantic ground truth.

In this replay, sparse validation plus event-driven rebuild reduced measured spatial-state maintenance cost relative to eager processing on the recorded sample. It does **not** establish deployment performance, universal region quality, or production thresholds. Decode, scheduler contention, memory pressure and target-device transforms were outside the timing boundary.

The replay did not change runtime ownership: Observation-side work produced maintenance evidence and candidate work descriptions, while the existing runtime remained responsible for task creation, admission, scheduling and merge.
