# YOLO26 Pose sparse-target / ONNX validation

Historical source archive date: 2026-08-24.

This evidence tested whether work could be reduced after a person target had been coordinate-locked, then checked parity and execution through exported ONNX graphs and ONNX Runtime.

## Recorded scope

- Source branch: `yoloe26-smoke`
- Experiment baseline: `35194e1c2dd4e2ff15aa00b8b7c3197b6529317a`
- 90 decoded 640x640 frames; 89 post-lock transitions
- Local YOLO26 Pose model, FP32, CPU, 8 threads
- PyTorch 2.2.2, Ultralytics 8.4.60, ONNX 1.21.0, ONNX Runtime 1.23.2
- Timing excluded file I/O and RGB-to-NCHW preprocessing

The original video/cache and source model are not redistributed by this showcase.

## Selected measurements

| Path | p50 ms | p95 ms | Observation |
| --- | ---: | ---: | --- |
| Full YOLO26 Pose, first run | 158.96 | 207.42 | baseline |
| Locked P4 local cls + top-1 box + pose | 125.55 | 170.71 | 90/90 tracked |
| Full YOLO26 Pose, paired floor run | 166.61 | 199.99 | paired reference |
| Locked P4 local path, paired floor run | 129.81 | 170.73 | target Recall@1 89/89 |
| ORT Python full pose | 59.49 | 64.74 | exported runtime path |
| ORT Python sparse | 42.41 | 49.27 | exported sparse path |
| ORT C++ full pose | 72.81 | 83.44 | native harness |
| ORT C++ sparse wall | 38.70 | 46.59 | included both sessions and patch/tensor handling |

A second strict-build C++ sparse run recorded 38.38 ms p50 / 48.33 ms p95.

## Parity checks

The archive recorded:

- relocation anchor match: 89/89;
- box IoU p05/p50: 0.9999976 / 0.9999984;
- keypoint XY maximum absolute error: 0.000305 px;
- standard `ai.onnx` operators only; no custom ONNX operator was required.

A no-classification shortcut was rejected: although its measured latency was slightly lower, the archived quality checks showed worse target/keypoint behavior. This is useful evidence of the development process because the fastest measured variant was not automatically accepted.

## What this demonstrates

The claim is bounded: on the recorded machine and input sequence, a coordinate-local sparse path retained the selected target behavior while reducing measured work, and the exported path was checked against the PyTorch reference.

It does **not** demonstrate identity preservation through severe crossings/occlusion, no-person specificity, cold-start behavior, end-to-end file/preprocessing latency, or general performance across hardware/models.
