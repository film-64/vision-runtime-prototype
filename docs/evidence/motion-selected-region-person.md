# Motion-selected region for person detection

Historical source archive date: 2026-09-02.

This bounded offline feasibility test asked whether short frame history and low-cost motion evidence could choose one continuous region for person detection, preserve the full-frame reference detections from the same model, and reduce complete-path cost.

## Recorded scope

- Source branch: `gate-tool-2`
- 15 decoded in-memory frames; the first seeded history and 14 were measured
- source sampled every third frame in the recorded window
- 1280x720 source represented as 640x360 active content inside a 640x640 observation plane
- camera-motion-compensated residual-flow analysis over a short history window
- continuous candidate regions selected from fixed spatial boundaries
- selected region had to cover at least 98.5% of the dilated motion support or fall back to the full active region
- local YOLO26 Pose model
- only backbone/neck plus one-class person classification and box branches executed
- **keypoint branch not executed**
- CPU, FP32, one Torch thread
- confidence 0.25, NMS IoU 0.6
- full-frame boxes from the same model were the reference; they were not human-labeled ground truth

The source video, decoded frames and model weights are not redistributed here.

## Recorded result

| Measurement | Full person-only | Motion-selected region |
| --- | ---: | ---: |
| Reference person boxes retained | 48 | 48/48 |
| Mean / minimum mapped IoU | - | 0.9488 / 0.8669 |
| Mean purchased active area | 100% | 61.93% |
| Full-region fallback | - | 2/14 frames |
| Detector p50 | 217.1164 ms | 99.7230 ms |
| Region-selection p50 | - | 26.8007 ms |
| Complete-path p50 | 217.1164 ms | 131.8110 ms |

The complete regional path reduced p50 by 39.3% in this bounded window while retaining every full-frame reference box.

The regional path emitted 64 person boxes versus 48 from the full input. Cropping can change candidate survival, so the result demonstrates preservation against the same model-derived full-frame reference. It does not establish human-labeled precision.

## Observation interpretation

This experiment is useful as a concrete example of staged visual work:

```text
short frame history
      |
      v
cheap motion / CV evidence
      |
      v
continuous region selection
      |
      v
purchase person-detector computation only on that region
```

It supports the direction "cheap evidence before stronger inference" on the recorded window. It does not define a production selection policy, and it does not demonstrate posture semantics because the keypoint branch was disabled.
