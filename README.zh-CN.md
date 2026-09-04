# vision-runtime-prototype

[English](README.md) | 中文

这是一个从更大的私有视觉感知项目中整理出来的公开展示仓库。

它不是完整应用，也不是完整历史代码的镜像。这里公开的是一部分可以独立运行、检查和验证的机制：运行时控制、部分 Observation 合约、测试、合成验证链，以及经过整理的历史实验结果。

这个仓库主要用于展示我当前项目的前进方向、系统边界和可验证结果，同时保留私有媒体、模型权重、身份数据、完整应用栈和未公开内部机制。

## 这个项目在解决什么

长期目标不是做一个单独的检测器，也不是把多个视觉模型简单串起来。

我更关心的是一个持续存在的视觉系统：它不能每一帧都重新理解整个世界，而需要知道自己已经知道什么、哪些信息还能继续使用、哪些信息已经过期或不足，以及下一次额外计算是否值得发生。

它最终希望支持一种长期存在的视觉伴随系统，例如可穿戴、本地观察、视觉搜索、识别和长期上下文，而不是为每个产品形态重新搭一套互不相干的视觉流水线。

> **你需要一个 Observation 中心，而不是让一切都变成 Attention。注意力是有限的。**

系统不应该尝试一直完整感知所有东西。它应该维护一个持续的信息状态，再把有限的感知与计算资源花在真正值得追加观测的位置。

## 当前公开范围

公开的 runtime control 部分保留了早期运行时中的几类机制：

- 延迟、队列和运行时指标；
- detector-index 时间语义和过期任务拒绝；
- 调度状态与运行频率决策；
- 带 hysteresis 的运行时健康状态和压力响应。

后来加入的公开 Observation 部分目前只展示两个较窄的合约：

- 带来源、generation、freshness 和历史可见性的版本化 evidence；
- 明确指回其支撑 evidence 的 information state。

原始私有系统范围更大，包含帧输入、多种感知能力、图定义需求、调度/准入、执行、持久状态、metadata、replay 和更高层控制。这里公开的是其中选出的可运行投影，不是完整系统的缩小复制品。

## 系统上下文

当前更大的系统关系可以简化为：

```text
                 更高层控制
                     |
                 图定义需求
                     |
                     v
Frame ----------> OBSERVATION <---------- semantic feedback
                  受保护的信息基座
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

系统不只是决定“运行哪个模型”。过去很多实验都在问同一个更一般的问题：一个通用视觉能力能不能根据当前上下文，在空间、语义、时间或计算形式上被缩窄，只做当前真正需要的部分。

OCR 区域实验、稀疏 Pose、时间复用和 YOLOE 的动态/局部执行都属于这个方向的有限验证，不代表已经完成了一个通用优化层。

当前私有运行时中的调度也不只是 FIFO。运行状态和负载会影响候选容量；合法候选可以结合 cost / utility 信息，在有界执行预算内被排序和准入；部分自适应路径可以在既有安全边界内做有限调整。最终执行权仍然属于 Global TaskScheduler。

公开仓库只展示其中有限的调度和自适应行为，不声称已经完成端到端全局学习型编排。

## Observation

公开部分最核心的问题是：

> **在系统已经知道一些东西的前提下，当前 evidence 是否仍然足够，还是值得为更强的 observation 再支付一次计算成本？**

可以进一步拆成：

```text
哪里值得追加视觉计算？
什么时候以前获得的信息已经不能安全复用？
```

Observation 比 Attention 更宽。

Attention 解决的是有限感知与计算机会应该投向哪里；Observation 维护的是整个系统共享的信息状态，让其他部分能够区分：当前已知什么、未知什么、哪些东西已经过期、哪些证据支撑不足、哪些信息值得重新获取。

因此架构并不要求所有能力都变成“Attention”。Attention 和其他策略都应该围绕一个共同的 Observation 中心工作。

在更大的系统中，Observation 不是普通的后处理模块，也不是 OCR / Pose / YOLOE 这样的并列 specialist。它位于普通语义任务之前，作为受保护的前置 substrate，维护可复用信息、evidence、维护规则和内部 observation compute。

当注册需求无法继续被当前状态满足时，Observation 可以构造 scheduler-visible work；语义结果执行完成后又可以反馈回 Observation，成为新的 evidence。

Observation 不直接执行 specialist model，也不替代 Global TaskScheduler。

## 开发方式

这个项目的实现高度由 AI 助手和 Coding Agent 驱动。

我主要控制项目的前进方向，而不是具体实现过程。

一个典型循环是：

```text
方向 / 判断
    ↓
与 AI 助手讨论、拆解和澄清
    ↓
Coding Agent 物化为可运行实现
    ↓
观察实际行为、结果和测量
    ↓
判断与验证
    ↓
符合预期 → 保留并继续推进

不符合预期
    ↓
重新评估问题
    ↓
结合新的结果与约束更新系统模型
    ↓
重新定义结构、边界或优先级
    ↓
进入下一轮实现
```

很多实现细节、维护工作、测试和文档由 Agent 完成，其中也存在一些并非由我预先提出、而是在实现过程中自然产生的结构。

我不会因为一个结果来自 Agent 就否定它。只要实际行为合理，并且能够通过运行、测试或测量得到支持，它就可以进入下一轮系统。

我主要持续判断：

- 当前结果是不是我要的；
- 系统行为是否与当前理解一致；
- 哪些结果值得保留；
- 哪些地方出现了无法解释的偏差；
- 当前结构和约束是否还足以继续推进；
- 项目下一步应该往哪个方向前进。

因此，这个项目并不是先完成一套完整理论，再按照设计图实现。

它更接近：

```text
方向
→ AI / Agent 物化
→ 实际结果
→ 判断与验证
→ 更新系统模型
→ 调整结构与边界
→ 下一轮
```

随着结果持续返回，最初模糊的想法会被保留、删除、重新定义或重新组合，系统结构也因此逐渐收敛。

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
dynamic_pipeline/core/      公开 synthetic E2E 所需的窄 metadata contracts
roi_app/                     公开 evidence 所需的 async commit/package/replay 路径
scripts/generate_public_evidence.py
                             deterministic synthetic E2E evidence harness

tests/                       synthetic、model-free contract tests
config/                      经过整理的 runtime policy 示例
docs/runtime-architecture.md
docs/observation.md
docs/information-support-geometry.md
docs/research-boundary.md
docs/evidence/               历史结果摘要 + frozen synthetic snapshot
examples/                    小型 model-free demo
```

`dynamic_pipeline/` 和 `roi_app/` 并不是完整应用源码，只保留公开 synthetic E2E 所需要的支持代码。

## 轻量验证

公开 runtime control 和 Observation contracts 可以在不依赖完整视觉模型环境的情况下运行：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
python examples/runtime_control_demo.py
python examples/observation_contract_demo.py
```

这些命令验证的是当前公开切片，不代表完整历史视觉系统已经被公开复现。

合成 metadata E2E 也可以重新生成：

```bash
python scripts/generate_public_evidence.py --output-dir /tmp/public-metadata-evidence
```

GitHub Actions 会重新运行同一条 model-free 验证链，并生成与 commit 对应的 artifact。仓库里检查进去的 evidence 目录只是方便浏览的 frozen snapshot；每个 commit 对应的 Actions artifact 才是当前执行记录。

## 历史执行证据

| Evidence | 说明 |
| --- | --- |
| [YOLO26 Pose sparse / ONNX](docs/evidence/yolo26-pose-sparse-onnx.md) | 稀疏目标路径、PT/ONNX parity、原生 ONNX Runtime 执行 |
| [OCR region-shape performance](docs/evidence/ocr-region-performance.md) | ROI 形状与候选质量/执行成本之间的实际取舍 |
| [YOLOE26 fused/local path](docs/evidence/yoloe26-fused-local.md) | dynamic vs fused、dense vs coordinate-local 的实测差异 |
| [Motion-selected region person detection](docs/evidence/motion-selected-region-person.md) | 先用廉价 CV evidence 选择区域，再投入 person detector 计算 |
| [Temporal spatial reuse](docs/evidence/temporal-spatial-reuse.md) | sparse validation / event-driven rebuild 与 eager per-frame processing 的比较 |
| [Synthetic metadata E2E snapshot](docs/evidence/current-synthetic-metadata-e2e/README.md) | 当前公开 metadata projection / commit / package / verify / replay 链 |

这些 benchmark 是历史验证快照，不是当前设备上的性能承诺。Synthetic E2E 是当前公开切片的 model-free 验证，也不是实际模型性能结果。

## 公开边界

本仓库刻意不公开：

- 私有媒体、模型权重、身份材料和机器本地资产；
- 完整应用与模型集成栈；
- 超出公开切片的内部控制、自适应和编排机制；
- 未公开的 Observation 机制和模型特化细节；
- 完整内部开发历史和私有实验材料；
- “完整历史系统可以直接 clone-and-run”的声明。

## License

公开源码沿用源仓库的 GNU Affero General Public License v3.0。第三方模型和 runtime artifact 不在这里重新分发，范围说明见 `THIRD_PARTY_NOTICES.md`。
