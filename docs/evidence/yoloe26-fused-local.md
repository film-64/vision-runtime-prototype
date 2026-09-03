# YOLOE26 fused / coordinate-local execution validation

Historical source archive date: 2026-08-25.

This summary keeps two measured parts of the original evidence: dynamic prompt embedding versus a fused one-class YOLOE head, and full fused YOLOE versus a coordinate-local classification/box path after target lock. Other exploratory material from the source archive is intentionally omitted from this showcase.

## Recorded scope

- Source branch: `yoloe26-smoke`
- Experiments 1-2 baseline: `aced678956c1ab539b0f9acdcec4765f71735e98`
- Local YOLOE26 segmentation model and text encoder
- 10 decoded 640x640 frames for these two experiments
- Python 3.11.13, PyTorch 2.2.2, Ultralytics 8.4.60
- CPU, FP32 live inference, 8 PyTorch threads

The original model, text encoder, decoded frame cache, generated prompt embedding and fused checkpoint are not redistributed here.

## Dynamic prompt path versus fused one-class head

Both paths used fresh model instances and the same saved `person` prompt embedding before the fused path applied the installed Ultralytics head fusion.

| 10-frame path | Wall p50 | Wall p95 | Inference p50 | Inference p95 |
| --- | ---: | ---: | ---: | ---: |
| Dynamic TPE contrastive head | 234.36 ms | 294.70 ms | 213.72 ms | 269.95 ms |
| Fused one-class head | 226.56 ms | 265.61 ms | 196.73 ms | 243.12 ms |

Recorded parity:

- detection count: 117 versus 117;
- matched boxes: 117/117;
- minimum matched IoU: 1.0;
- maximum bbox error: 0 px;
- maximum confidence error: `3.6657e-6`.

## Full fused path versus coordinate-local head

After one dense target lock, the experiment reused the previous anchor as the center of a local feature patch and measured only the relevant local cls/box work while retaining backbone+neck execution.

| 10-frame path | p50 | p95 | Total |
| --- | ---: | ---: | ---: |
| Full fused YOLOE Seg | 161.58 ms | 181.36 ms | 1638.54 ms |
| Backbone + neck | 115.36 ms | 125.35 ms | 1126.08 ms |
| Dense P3/P4/P5 cls + box | 17.78 ms | 23.79 ms | 182.05 ms |
| One-level local cls + box | 2.58 ms | 4.21 ms | 28.47 ms |
| Backbone + local total | 118.65 ms | 127.76 ms | 1154.95 ms |

The archive calculated full-versus-sparse savings of 26.57% at p50, 29.55% at p95, and 29.51% over the ten-frame total for this specific run. Dense-versus-local head work fell much more sharply, but the backbone/neck remained the dominant cost.

Recorded continuity/parity included:

- relocation anchor match: 10/10;
- maximum cls raw error: `1.8692e-4`;
- maximum box raw error: `9.5367e-6`;
- local versus corresponding dense bbox minimum IoU: `0.99999869`.

Dense/local switching patterns also retained the same ten-frame anchor sequence without model reload in the warmed resident model.

## What this demonstrates

The useful engineering result is not that a model head can simply be removed. The measurement showed where work remained: localizing the head reduced head cost heavily, while backbone/neck execution still dominated the full path. That evidence motivated later attention to input/ROI consumption and avoiding repeated full-frame work rather than making an unsupported claim about arbitrary model-internal rewrites.

## Interpretation limits

All selected anchors stayed on the same feature level in this run. Cross-level scale changes, severe occlusion, identity preservation through crossings, process/model cold start and broader input distributions were not validated by this ten-frame measurement. These values are historical measurements, not current performance guarantees.
