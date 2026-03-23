# Workflow 节点输入输出总表

本文只描述当前仓库中的真实实现，不把理想方案写成已实现方案。节点顺序以 `src/workflows/graph.py` 为准。

## 1. 节点总览表

| 节点名 | 主要职责 | 输入 state 字段 | 输出 state 字段 | 依赖的 provider / service | 落盘文件 | 当前实现形态 |
| --- | --- | --- | --- | --- | --- | --- |
| `ingest_assets` | 补齐素材宽高，整理资产列表 | `task`, `assets`, `logs` | `assets`, `logs` | PIL `Image` | 节点本身不新增落盘；`inputs/` 和 `task.json` 在 UI 层 `_run_task()` 已写入 | `mixed` |
| `analyze_product` | 产出商品分析 `ProductAnalysis` | `task`, `assets`, `logs` | `product_analysis`, `logs` | `build_mock_product_analysis()` / `NVIDIAVisionProductAnalysisProvider` / `storage` | `product_analysis.json` | `mixed` |
| `plan_shots` | 产出图组规划 `ShotPlan` | `task`, `product_analysis`, `logs` | `shot_plan`, `logs` | `build_mock_shot_plan()` / `planning_provider` / `storage` | `shot_plan.json` | `mixed` |
| `generate_copy` | 产出结构化中文文案 `CopyPlan` | `task`, `product_analysis`, `shot_plan`, `logs` | `copy_plan`, `logs` | `build_mock_copy_plan()` / `planning_provider` / `storage` | `copy_plan.json` | `mixed` |
| `generate_layout` | 产出文字布局 `LayoutPlan` | `task`, `shot_plan`, `logs` | `layout_plan`, `logs` | `build_mock_layout_plan()` / `storage` | `layout_plan.json` | `mixed` |
| `build_prompts` | 产出图片提示词 `ImagePromptPlan` 并补充 per-shot 调试产物 | `task`, `product_analysis`, `shot_plan`, `copy_plan`, `layout_plan`, `logs` | `image_prompt_plan`, `logs` | `planning_provider` / `storage` | `image_prompt_plan.json`，`artifacts/shots/{shot_id}/shot.json`，`copy.json`，`layout.json`，`prompt.json` | `mixed` |
| `render_images` | 生成基础图片 | `task`, `assets`, `image_prompt_plan`, `logs` | `generation_result`, `logs` | `image_provider` | `generated/*.png` | `mixed` |
| `overlay_text` | Pillow 中文后贴字并生成预览图 | `task`, `generation_result`, `copy_plan`, `layout_plan`, `logs` | `generation_result`, `logs` | `text_renderer`, `save_preview()` | `final/*.png`, `previews/*.png` | `mixed` |
| `run_qc` | 基础质检并汇总 `QCReport` | `task`, `generation_result`, `copy_plan`, `logs` | `qc_report`, `logs` | `build_dimension_check()` / `build_ocr_check()` / `ocr_service` / `storage` | `qc_report.json` | `mixed` |
| `finalize` | 更新任务状态并导出 ZIP | `task`, `qc_report`, `logs` | `task`, `export_zip_path`, `logs` | `save_task_manifest()` / `export_task_zip()` | 回写 `task.json`，生成 `exports/{task_id}_images.zip` | `mixed` |

说明：

- 这里的 `mixed` 指当前节点要么在 mock / real 间切换，要么虽然不切换 provider，但无论 mock / real 模式都会执行同一套本地逻辑。
- workflow 之外还有一个前置步骤：`src/ui/pages/home.py::_run_task()` 会先创建任务目录、写入 `task.json`、保存上传图片，再调用 LangGraph。

## 2. 节点详细说明

### 2.1 `ingest_assets`

职责：

- 读取 `state["assets"]`
- 尝试打开本地图片，补齐 `width` 和 `height`
- 返回更新后的 `assets`

当前实现方案：

- 纯本地逻辑
- 使用 PIL `Image.open()` 读取图片尺寸
- 不调用 provider，也不调用注入的 `deps`

mock / real 切换点：

- 无
- 无论 provider mode 如何，执行同一套本地逻辑

输入依赖：

- `task`
- `assets`
- `logs`

输出结果：

- `assets`
- `logs`

落盘文件：

- 节点本身不新增落盘
- 真实落盘已在 `_run_task()` 完成：
  - `inputs/*`
  - `task.json`

当前风险或限制：

- 节点不会识别素材类型
- 如果图片打不开，会直接保留原始 `Asset`，尺寸可能仍为 `None`

后续最合理演进方向：

- 继续保持节点轻量，只补素材元信息
- 若以后增加素材分类，也应保持在结构化 schema 和 service 层完成，不应把 provider 细节散到节点里

### 2.2 `analyze_product`

职责：

- 产出 `ProductAnalysis`
- 为后续图组规划、文案、提示词提供商品分析输入

当前实现方案：

- mock 模式调用 `src/services/analysis/product_analyzer.py::build_mock_product_analysis()`
- real 分支会组装 `task + assets` 的结构化 prompt，并调用 `deps.vision_provider.generate_structured_from_assets(...)`
- 当前真实 provider 文件是 `src/providers/vision/nvidia_product_analysis.py`
- 结果通过 `storage.save_json_artifact()` 落盘为 `product_analysis.json`

mock / real 切换点：

- `deps.vision_provider_mode == "real"` 时走 real 分支
- 否则走本地 mock 分析

输入依赖：

- `task`
- `assets`
- `logs`

输出结果：

- `product_analysis`
- `logs`

落盘文件：

- `product_analysis.json`

当前风险或限制：

- real 分支依赖 NVIDIA 视觉接口和有效 API Key；当前实现不做 silent fallback
- 如果上传图片不存在、不可读或接口返回非 JSON，会直接报错
- mock 分析不会真的从图片中识别包装结构、标签位置或材质，只输出占位型结构化结果

后续最合理演进方向：

- 继续把视觉分析能力收敛在 provider 层，不要把多模态请求细节散到 workflow 节点
- 继续保持输出严格校验为 `ProductAnalysis`，不要退化成自由文本
- 保持它作为当前唯一看图分析节点，不把图片理解重新分散到后续文本节点

### 2.3 `plan_shots`

职责：

- 根据 `ProductAnalysis` 生成图组规划 `ShotPlan`
- 固定 `shot_id`、张数和图组结构

当前实现方案：

- mock 模式下，`build_dependencies()` 注入的是 `GeminiTextProvider`
- mock 逻辑本体仍由 `build_mock_shot_plan()` 生成
- real 模式下，`build_dependencies()` 先通过能力路由层选出 `planning_provider`，默认是 `NVIDIATextProvider + Qwen3.5`
- 如需回切，可通过配置把 `planning_provider` 仍路由到 `NVIDIATextProvider + GLM-5`
- real prompt 会带上 `task` 与 `product_analysis`
- prompt 会先注入类目族群、整组风格锚点摘要、核心图型与扩展图型约束
- 结果落盘到 `shot_plan.json`

mock / real 切换点：

- `deps.text_provider_mode == "real"` 时调用真实文本 provider
- 否则走本地 mock 规划

输入依赖：

- `task`
- `product_analysis`
- `logs`

输出结果：

- `shot_plan`
- `logs`

落盘文件：

- `shot_plan.json`

当前风险或限制：

- real 分支依赖当前 `planning_provider` 返回严格 JSON；当前实现没有 silent fallback
- mock 分支不会根据商品视觉差异产生真正细分的图组策略

后续最合理演进方向：

- 继续让 `ShotPlan` 保持结构化约束
- 需要更复杂图组策略时，也应收敛在文本 provider 和 schema，而不是 UI 层
- 继续优先约束类目边界与整组风格一致性，避免茶叶等类目失控发散

### 2.4 `generate_copy`

职责：

- 生成最终后贴字使用的结构化中文文案 `CopyPlan`

当前实现方案：

- mock 模式下，`build_dependencies()` 注入的是 `GeminiTextProvider`
- mock 逻辑本体由 `build_mock_copy_plan()` 生成
- real 模式下，`build_dependencies()` 先通过能力路由层选出 `planning_provider`，默认是 `NVIDIATextProvider + Qwen3.5`
- real prompt 会带上 `task`、`product_analysis` 与 `shot_plan`
- 节点输出是标题、副标题、卖点、CTA 的结构化组合
- 结果落盘到 `copy_plan.json`

mock / real 切换点：

- `deps.text_provider_mode == "real"` 时调用真实文本 provider
- 否则走本地 mock 文案

输入依赖：

- `task`
- `shot_plan`
- `logs`

输出结果：

- `copy_plan`
- `logs`

落盘文件：

- `copy_plan.json`

当前风险或限制：

- 图片模型不负责正式中文落图，因此这里的结构化文案是后续 `overlay_text` 的硬依赖
- 如果 real provider 返回的 JSON 不符合 schema，会直接报错，不会自动兜底

后续最合理演进方向：

- 继续把中文文案控制权保留在 `CopyPlan`
- 如要扩展文案风格，也应先扩 schema，再调 provider prompt

### 2.5 `generate_layout`

职责：

- 产出文字布局 `LayoutPlan`
- 为 Pillow 后贴字提供标题、副标题、卖点、CTA 的坐标和字号

当前实现方案：

- 固定调用 `build_mock_layout_plan()`
- 根据 `output_size` 拆出宽高，再生成规则布局块
- 结果落盘到 `layout_plan.json`

mock / real 切换点：

- 无
- 当前阶段不接布局模型，不区分 mock / real

输入依赖：

- `task`
- `shot_plan`
- `logs`

输出结果：

- `layout_plan`
- `logs`

落盘文件：

- `layout_plan.json`

当前风险或限制：

- 布局完全是规则型，不理解真实商品主体占位
- 只针对当前两种输出尺寸和现有版式做固定布局

后续最合理演进方向：

- 若后续引入更智能布局，也应继续输出 `LayoutPlan`
- 节点契约和落盘文件名不应变化

### 2.6 `build_prompts`

职责：

- 产出图片生成阶段使用的 `ImagePromptPlan`

当前实现方案：

- mock 模式按逐张 shot 生成本地占位 prompt，并同步写入单张调试 JSON
- real 模式下，`build_dependencies()` 先通过能力路由层选出 `planning_provider`，节点会按 `shot_plan` 循环，逐张调用 `deps.planning_provider.generate_structured(...)`
- 默认情况下，每次 real 调用都会把当前 `task`、`product_analysis`、当前 `shot`、对应 `copy`、对应 `layout` 送给 `Qwen3.5`
- 当前会显式标记 `build_prompts` 为“纯结构化推理模式”，不向文本模型发送图片输入
- 如需回切，可通过配置让同一条节点调用链改用 `GLM-5`
- real 结果会做一次归一化：
  - 缺省 `output_size` 时回填 `task.output_size`
  - 缺省 `negative_prompt` 时回填默认值
  - 缺省 `preserve_rules`、`text_space_hint`、`composition_notes`、`style_notes` 时按当前分析结果与布局补齐
- 节点在保留 aggregate `image_prompt_plan.json` 的同时，还会写入 `artifacts/shots/{shot_id}/shot.json`、`copy.json`、`layout.json`、`prompt.json`

mock / real 切换点：

- `deps.text_provider_mode == "real"` 时调用真实文本 provider
- 否则走本地拼接

输入依赖：

- `task`
- `product_analysis`
- `shot_plan`
- `copy_plan`
- `layout_plan`
- `logs`

输出结果：

- `image_prompt_plan`
- `logs`

落盘文件：

- `image_prompt_plan.json`
- `artifacts/shots/{shot_id}/shot.json`
- `artifacts/shots/{shot_id}/copy.json`
- `artifacts/shots/{shot_id}/layout.json`
- `artifacts/shots/{shot_id}/prompt.json`

当前风险或限制：

- 当前 prompt 明确要求图片模型不要直接输出正式中文，因此最终文案仍依赖后贴字
- 当前结构化规划模型生成的是“单张图的结构化生图提示词”，不是图片理解；其质量仍依赖前序 `product_analysis`、`shot_plan`、`copy_plan`、`layout_plan`
- 当前文本模型调用没有多模型 fallback；某一张 shot 失败会直接中断当前任务

后续最合理演进方向：

- 继续让图片提示词保持结构化，而不是回退为不可控长文本
- 如果补充更多视觉约束，优先扩 `ImagePromptPlan`

### 2.7 `render_images`

职责：

- 根据 `ImagePromptPlan` 生成基础图片
- 产出 `GenerationResult`

当前实现方案：

- 统一调用 `deps.image_provider.generate_images(...)`
- 输出目录固定为 `generated/`
- real provider 会额外使用 `reference_assets`
- mock provider 会忽略 `reference_assets`

mock / real 切换点：

- `build_dependencies()` 中：
  - `mock -> GeminiImageProvider`
  - `real -> RunApiGeminiImageProvider`

输入依赖：

- `task`
- `assets`
- `image_prompt_plan`
- `logs`

输出结果：

- `generation_result`
- `logs`

落盘文件：

- `generated/*.png`

当前风险或限制：

- real 图片 provider 要求至少一张上传参考图，否则直接报错
- 当前实现不做 silent fallback
- mock provider 只是本地占位底图，不代表真实商品一致性

后续最合理演进方向：

- 继续把真实图片请求封装在 provider 层
- 维持 `GenerationResult` 契约不变

### 2.8 `overlay_text`

职责：

- 把 `CopyPlan` 和 `LayoutPlan` 应用到基础图上
- 生成最终图和预览图

当前实现方案：

- 构造 `copy_map` 和 `layout_map`
- 对每张 `generated` 图片调用 `deps.text_renderer.render_copy(...)`
- 用 `save_preview()` 额外写缩略预览图
- 把 `GenerationResult.images[*].image_path` 改写为 `final/*.png`
- `status` 改为 `finalized`
<<<<<<< HEAD
=======
- 同时把字体来源、fallback 状态、`requested_font_size / used_font_size / min_font_size_hit / overflow_detected` 写回 `text_render_reports`
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c

mock / real 切换点：

- 无
- 当前始终通过 Pillow 后贴字，不依赖图片模型直接落正式中文

输入依赖：

- `task`
- `generation_result`
- `copy_plan`
- `layout_plan`
- `logs`

输出结果：

- 更新后的 `generation_result`
- `logs`

落盘文件：

- `final/*.png`
- `previews/*.png`

当前风险或限制：

- `copy_map` 或 `layout_map` 只要缺少对应 `shot_id`，节点会直接失败
- 当前 UI 虽然生成了 `previews/`，但结果页实际展示的是改写后的 `final/*.png`

后续最合理演进方向：

- 继续把中文渲染控制在本地 Pillow 流程
- 如需增强排版效果，应优先改进 `TextRenderer` 或 `LayoutPlan`

### 2.9 `run_qc`

职责：

- 生成基础质检报告 `QCReport`

当前实现方案：

- 对每张最终图做两类检查：
  - `dimension`
  - `ocr_similarity`
- `dimension` 通过 `build_dimension_check()` 校验实际图片尺寸
- `ocr_similarity` 通过 `build_ocr_check()` 调用 `PaddleOCRService.read_text()`
- 报告落盘到 `qc_report.json`

mock / real 切换点：

- 无独立 provider mode 分支
- 但 OCR service 是否真正启用受 `enable_ocr_qc` 控制

输入依赖：

- `task`
- `generation_result`
- `copy_plan`
- `logs`

输出结果：

- `qc_report`
- `logs`

落盘文件：

- `qc_report.json`

当前风险或限制：

- 默认 `enable_ocr_qc=False` 时，`PaddleOCRService.read_text()` 返回空列表
- 当前 `build_ocr_check()` 在 OCR 没结果时会直接返回 `passed=True`
- 因此当前 QC 更接近“链路完整性检查”，不是生产级视觉质检

后续最合理演进方向：

- 接入真实 OCR 后继续保留 `QCReport` 契约
- 更复杂质检逻辑应下沉到 `src/services/qc/`

### 2.10 `finalize`

职责：

- 基于 `qc_report` 更新任务状态
- 回写任务清单
- 生成下载用 ZIP

当前实现方案：

- `qc_report.passed=True` 时任务状态写为 `completed`
- 否则写为 `review_required`
- 调用 `save_task_manifest()` 回写 `task.json`
- 调用 `export_task_zip()` 生成 `exports/{task_id}_images.zip`

mock / real 切换点：

- 无
- 无论前面走 mock 还是 real，这里都执行同一套收尾逻辑

输入依赖：

- `task`
- `qc_report`
- `logs`

输出结果：

- 更新后的 `task`
- `export_zip_path`
- `logs`

落盘文件：

- 回写 `task.json`
- `exports/{task_id}_images.zip`

当前风险或限制：

- ZIP 只打包 `final/` 目录，不包含中间 JSON、`generated/` 或 `inputs/`
- 当前没有失败重试或补偿逻辑

后续最合理演进方向：

- 保持 `finalize` 只负责收尾与导出
- 如果未来增加更多导出形式，也应继续复用现有任务目录结构

## 3. 补充说明

### 3.1 workflow 之外的前置落盘

以下动作不属于 10 个节点，但对调试非常关键：

- `_run_task()` 创建 `task_id`
- `_run_task()` 写入 `task.json`
- `_run_task()` 保存上传文件到 `inputs/`

因此排查任务失败时，先看：

- `task.json`
- `inputs/`
- 结果页日志中的 `streamlit_entry` 和 `langgraph_invoke`

### 3.2 workflow 之后的额外测试产物

workflow 成功返回后，`_run_task()` 还会额外生成：

- `previews/text_render_base.png`
- `previews/text_render_test.png`
<<<<<<< HEAD

这两个文件不属于 10 个节点的标准产物，而是首页为调试后贴字链路额外补的一组样图。
=======
- `previews/text_render_test.meta.json`

这些文件不属于 10 个节点的标准产物，而是首页为调试后贴字链路额外补的一组样图与 metadata。
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
