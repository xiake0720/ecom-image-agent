# 最小 A/B 评测方案

本文档定义当前项目的最小工程化评测框架，用于比较：

- 不同 `provider` 组合
- 不同 `budget mode`
- 不同 `prompt build mode`

当前阶段只做工程指标汇总，不引入自动打分模型，也不改变现有 workflow 节点逻辑。

## 1. 评测目标

评测框架只回答两个问题：

1. 某组配置能否稳定跑通现有链路
2. 不同配置之间的时延、产物数量和 QC 状态差异如何

当前不做：

- 自动美学评分
- 人工偏好建模
- 多模型裁判
- 图像复评模型

## 2. 评测输入

评测脚本入口：

- `scripts/run_benchmark.py`

默认 case 根目录：

- `tests/fixtures/ecom_cases/`

每个 case 目录建议包含：

- `inputs/`
- `expected/`
- `case.json`

其中 `case.json` 是 benchmark 读取的机器可读配置，至少包含：

```json
{
  "case_name": "tea_single_can",
  "category": "tea",
  "task": {
    "brand_name": "Baseline Tea",
    "product_name": "高山乌龙单罐",
    "platform": "taobao",
    "output_size": "1440x1440",
    "shot_count": 4,
    "copy_tone": "专业自然"
  },
  "input_count": 1,
  "placeholder_inputs": [
    {
      "filename": "product_main.png",
      "size": "1600x1600",
      "color": [214, 192, 154]
    }
  ]
}
```

说明：

- `inputs/` 下有真实素材时，脚本优先使用真实素材
- `inputs/` 不足时，脚本按 `placeholder_inputs` 自动补最小占位图，便于本地 smoke benchmark
- 占位图只用于工程链路验证，不用于真实视觉质量判断

## 3. 可比较维度

脚本支持以下维度：

- `case` 列表
- `budget mode`
- `provider combo`
- `prompt build mode`
- `render mode`

其中 `provider combo` 建议写成：

```text
mock_all:text=mock,vision=mock,image=mock
nvidia_main:text=nvidia,vision=nvidia,image=runapi
cheap_mix:text=ollama,vision=mock,image=mock
```

说明：

- 同一次 benchmark 运行可以指定多个 `provider combo`
- 同一次 benchmark 运行可以指定多个 `prompt build mode`
- 最终按笛卡尔积展开为多次 task 执行

## 4. 输出位置

benchmark 继续复用现有：

- `outputs/tasks/{task_id}/`

同时新增一份总报告：

- `outputs/benchmarks/{run_id}/benchmark_report.json`

这样不会破坏当前 task 目录结构，也方便回放单个任务。

## 5. 报告字段

`benchmark_report.json` 顶层包含：

- `run_id`
- `generated_at`
- `case_root`
- `budget_mode`
- `render_mode`
- `prompt_build_modes`
- `provider_combos`
- `runs`

`runs[*]` 至少包含：

- `task_id`
- `case_name`
- `provider_combo`
- `render_mode`
- `prompt_build_mode`
- `total_latency_ms`
- `total_tokens`
- `generated_image_count`
- `qc_status`

当前 `total_tokens` 的口径说明：

- 仓库当前没有统一的 provider token usage 汇总接口
- 因此本字段先保留并默认回填 `0`
- 后续如果 provider 层补了 usage 统计，可继续兼容写入，不影响现有报告结构

## 6. 最小使用方式

只跑一个 mock smoke case：

```bash
python scripts/run_benchmark.py ^
  --cases tea_single_can ^
  --budget-mode production ^
  --provider-combo mock_all:text=mock,vision=mock,image=mock ^
  --prompt-build-mode batch ^
  --render-mode full_auto
```

对比两个 prompt build mode：

```bash
python scripts/run_benchmark.py ^
  --cases tea_single_can tea_gift_box ^
  --budget-mode production ^
  --provider-combo mock_all:text=mock,vision=mock,image=mock ^
  --prompt-build-mode batch ^
  --prompt-build-mode per_shot
```

对比两组 provider：

```bash
python scripts/run_benchmark.py ^
  --cases tea_single_can ^
  --budget-mode balanced ^
  --provider-combo mock_all:text=mock,vision=mock,image=mock ^
  --provider-combo main_chain:text=nvidia,vision=nvidia,image=runapi ^
  --prompt-build-mode per_shot
```

## 7. 当前建议

当前阶段先把 benchmark 当成工程回归和配置对比工具来用：

- 先验证能否跑通
- 再看 latency / image count / QC status
- 最后人工抽查对应 task 目录中的 JSON 和最终图

不要把当前报告直接当成图像质量结论。
