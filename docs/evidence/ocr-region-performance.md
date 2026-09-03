# OCR region-shape performance validation

Historical source archive date: 2026-08-25.

This experiment measured detector-only OCR cost and candidate survival for different coarse region materializations. It did not change the production scheduler or OCR runtime policy.

## Recorded scope

- Source branch: `yoloe26-smoke`
- Experiment baseline: `2055d822ddfdbf08a1cb52e228c879095267e6ee`
- One 640x640 decoded frame
- Local PP-OCRv5 mobile INT8 ONNX detector
- Python 3.10.5, OpenCV 4.10.0, NumPy 2.2.6, ONNX Runtime 1.23.2, x86_64
- 2 threads, 2 warmup passes, 12 measured passes
- Timing included crop/mask materialization plus synchronous detector-only perception
- OCR recognition, scheduler/admission, source decoding and model/session startup were excluded
- Full-frame detector output was used as the reference set; it was not human-labeled ground truth

The original frame and model artifacts are not redistributed here.

## Selected measurements

| Region recipe | p50 ms | p95 ms | Tensor ratio | Calls | Reference match |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full frame | 158.611 | 176.072 | 1.000 | 1 | 9/9 |
| Three rows sequential | 155.208 | 167.045 | 1.050 | 3 | 2/9 |
| Q2 | 37.685 | 43.748 | 0.250 | 1 | 3/5 |
| Q top half | 73.577 | 78.481 | 0.500 | 1 | 5/7 |
| Q1+Q2+Q4 L multi-crop | 111.278 | 129.352 | 0.750 | 2 | 6/9 |
| R1+R2+R6 bounding crop | 103.869 | 110.046 | 0.650 | 1 | 2/6 |
| R1+R2+R6 multi-crop | 54.883 | 59.578 | 0.350 | 2 | 2/6 |
| Largest exact focus box | 3.119 | 4.160 | 0.007 | 1 | 0/1 |

## Findings preserved from the archive

- Detector time broadly followed actual preprocessed tensor area rather than the logical selected area.
- Splitting the frame into three sequential row calls did not reduce total work; it mainly shaped peak single-call cost.
- Full-size bounding/mask materializations did not create a useful performance reduction.
- Extremely tight crops were fast but could fail to preserve detector candidates; context mattered.
- Non-contiguous materialization could reduce cost for some region shapes, but call count, split direction and candidate survival had to be evaluated together.

The archive therefore treated ROI selection as a cost/quality problem rather than assuming that smaller logical regions are automatically better.

## Interpretation limits

This was a one-frame detector-only experiment. It did not validate OCR recognition correctness, a production threshold, a scheduler policy, or representative multi-frame recall. Absolute timings are specific to the recorded machine/runtime/model.
