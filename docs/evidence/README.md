# Historical execution evidence

These pages are sanitized summaries of dated validation archives from the source repository. They preserve the engineering claim and measurement boundary without redistributing original media, model weights, generated checkpoints, raw machine paths, or the private research history.

## Runtime-control baseline evidence

- [YOLO26 Pose sparse / ONNX](yolo26-pose-sparse-onnx.md)
- [OCR region-shape performance](ocr-region-performance.md)
- [YOLOE26 fused/local execution](yoloe26-fused-local.md)

These were curated from the earlier `yoloe26-smoke` runtime baseline.

## Observation-related evidence

- [Motion-selected region for person detection](motion-selected-region-person.md)
- [Temporal spatial reuse validation](temporal-spatial-reuse.md)

These later bounded validations were recorded on `gate-tool-2`. They are included because they demonstrate two narrow Observation questions with measured evidence: where stronger computation can be focused, and when previously acquired spatial state can be reused instead of rebuilt.

## Interpretation rule

Each result is a historical snapshot tied to its recorded model, input, hardware/runtime and timing boundary. The numbers are not current product guarantees and should not be generalized beyond the stated experiment.

The public repository intentionally does not promise full reproduction of these runs. The source archives recorded their own inputs, hashes, raw results and tools; this showcase carries only the parts needed to demonstrate that the runtime and Observation ideas were actually exercised, measured and bounded during development.
