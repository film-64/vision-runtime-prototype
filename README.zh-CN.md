# vision-runtime-prototype

[English](README.md) | 中文

这是一个从更大的私有视觉感知项目中整理出来的公开展示仓库。

这个仓库主要用于求职展示。它公开的是一部分可以独立检查和验证的工程机制：运行时控制、少量 Observation 合约、合成验证链，以及经过整理的历史实验结果。它不是完整应用，也不代表完整私有系统已经公开复现。

## 这个仓库能展示什么

当前公开内容主要能直接展示这些工程行为：

- 延迟、队列和运行时指标；
- detector-index 时间语义与过期任务拒绝；
- 调度状态与运行频率决策；
- 带 hysteresis 的运行时健康状态和压力响应；
- 带 source / generation / freshness / history 的版本化 evidence；
- 明确引用支撑 evidence 的 information state；
- 可重复生成的 synthetic metadata projection / async commit / package / verify / replay 路径；
- 若干带明确边界的历史视觉运行实验。

## 这个项目在解决什么

私有项目长期处理的是一个很实际的工程问题：

> 连续视觉处理中，不应该默认每一帧都把所有昂贵能力重新跑一遍。

因此系统会尝试把三个问题分开：

```text
当前已经有什么信息？
这些信息现在由什么 evidence 支撑？
此刻到底还需要追加什么计算？
```

目标是减少不必要的重复计算、明确旧结果什么时候不能继续使用，并让真正的模型执行继续经过统一的 scheduler。

## 系统上下文

私有项目的大致关系可以简化为：

```text
Frame / 已有结果
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
视觉能力
  Pose / YOLOE / OCR recognition / 其他 specialist
        |
        v
results / persistent state / metadata
        |
        +--------------------> Observation update
```

Observation 不替代 scheduler，也不直接执行 specialist model。它主要维护“现在有什么信息、这些信息由什么 evidence 支撑、是否还能继续使用”这类状态。

公开仓库只实现了这条完整链路中的一小部分。

## Observation

`Observation` 是项目内部对共享视觉信息状态/合约层的命名。

当前公开代码只保留两个较窄的机制：

- `EvidenceStore`：按 source / generation 保存 append-only evidence 版本，并显式处理 freshness、invalidation 和历史可见性；
- `InformationState`：保存 carried information，并明确引用支撑它的 evidence refs。

这些内容能够展示职责边界，但不等于私有项目中的完整 maintenance、task construction 或模型选择逻辑已经公开。

详见 [docs/observation.md](docs/observation.md)。

## 空间支撑统计

私有项目里有一部分工作会统计 detector / probe 返回区域的空间分布，例如 gap、overlap、containment、coverage、scatter、density 等。

在这个展示仓库里，这部分统一描述为 **Spatial Support Statistics / 空间支撑统计**。

它不是学术上的 Information Geometry，也不代表系统已经恢复了人眼感知意义上的物体几何或完整 world model。

详见 [docs/spatial-support-statistics.md](docs/spatial-support-statistics.md)。

## Runtime control

公开的 runtime-control 部分主要保留了早期运行时中的几类 model-free 机制：

- metrics 与 jitter filtering；
- detector-time deadline 与 stale rejection；
- scheduling state / runtime frequency 决策；
- 带 hysteresis 的 runtime-health 状态。

Pose 和 YOLOE 在原系统中是不同的 detector capability。某条 route 偏好某个 capability，不代表另一个 detector 在架构上被替代。

详见 [docs/runtime-architecture.md](docs/runtime-architecture.md)。

## 仓库内容

```text
vision_runtime/
  metrics.py                 延迟、计数器、gauge、jitter filtering
  time_semantics.py          detector clock、watermark、deadline decision
  schedule_core.py           runtime frequency / heartbeat state decision
  runtime_health.py          pressure、tail latency、hysteresis decision
  observation/
    evidence.py              evidence 来源、版本、freshness、history
    information_state.py     与明确 evidence 关联的 carried information

dynamic_pipeline/core/      synthetic E2E 所需的窄 metadata contracts
roi_app/                     async commit/package/replay 支持代码
scripts/generate_public_evidence.py
                             deterministic synthetic E2E evidence harness

tests/                       synthetic、model-free contract tests
config/                      经过整理的 runtime policy 示例
docs/runtime-architecture.md
docs/observation.md
docs/spatial-support-statistics.md
docs/publication-boundary.md
docs/evidence/               历史结果摘要 + frozen synthetic snapshot
examples/                    小型 model-free demo
```

`dynamic_pipeline/` 和 `roi_app/` 只保留公开 synthetic path 所需的支持代码，不是完整应用源码。

## 轻量验证

公开 runtime control 和 Observation contracts 可以在没有私有媒体和模型权重的情况下运行：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
python examples/runtime_control_demo.py
python examples/observation_contract_demo.py
```

这些命令验证的是当前公开切片以及当前 test oracle，并不能证明完整私有系统已经经过全面验证。

合成 metadata E2E 也可以重新生成：

```bash
python scripts/generate_public_evidence.py --output-dir /tmp/public-metadata-evidence
```

这条路径使用 deterministic synthetic input，经过 runtime projection、bounded async metadata commit、package/index/archive、现有 verifier 和 `ReplayRuntime`。GitHub Actions 会重新运行同一路径，并上传与 commit 对应的 artifact。

## 历史执行证据

| Evidence | 说明 |
| --- | --- |
| [YOLO26 Pose sparse / ONNX](docs/evidence/yolo26-pose-sparse-onnx.md) | 稀疏目标路径、PT/ONNX parity、原生 ONNX Runtime 执行 |
| [OCR region-shape performance](docs/evidence/ocr-region-performance.md) | ROI 形状与候选质量/执行成本之间的实际取舍 |
| [YOLOE26 fused/local path](docs/evidence/yoloe26-fused-local.md) | dynamic vs fused、dense vs coordinate-local 的实测差异 |
| [Motion-selected region person detection](docs/evidence/motion-selected-region-person.md) | 先用廉价 CV evidence 选择区域，再投入 person detector 计算 |
| [Temporal spatial reuse](docs/evidence/temporal-spatial-reuse.md) | sparse validation / event-driven rebuild 与 eager per-frame processing 的比较 |
| [Synthetic metadata E2E snapshot](docs/evidence/current-synthetic-metadata-e2e/README.md) | 当前公开 metadata projection / commit / package / verify / replay 链 |

这些 benchmark 是历史验证快照，不是当前设备上的性能承诺。Synthetic E2E 是公开切片的 model-free 验证，也不是实际模型性能结果。

## 开发方式与作者边界

私有项目的实现高度依赖 AI 助手和 Coding Agent。大量代码、测试和文档由 agents 生成。

我主要负责提出需求和行为约束，通过不同 agents 做实现、审查和交叉检查，再根据运行输出、测试结果和 benchmark 调整需求或组件边界。

因此这个公开仓库不暗示每个实现细节都是我独立手写，也不把 green tests 当成“完整私有系统已经充分测试”的证明。

## 公开边界

本仓库不公开私有媒体、模型权重、身份材料、完整应用/模型集成栈、未公开实验机制、详细私有策略与 heuristic，以及完整内部开发历史。

详见 [docs/publication-boundary.md](docs/publication-boundary.md)。

## License

公开源码沿用 GNU Affero General Public License v3.0。第三方模型和 runtime artifact 不在这里重新分发，范围说明见 `THIRD_PARTY_NOTICES.md`。
