# 工作流说明

## 一、当前工作流定位
当前工作流是在第一阶段 **Mock MVP** 骨架基础上继续演进的。  
第一阶段已经完成归档，当前仓库处于第二阶段**真实 provider 接线阶段**。

因此当前工作流的准确描述应为：
- 仍然保留 mock 路径，便于本地验证和回退
- 部分节点已经支持切换到真实文本 provider
- 图片生成节点已经支持切换到真实图片 provider
- OCR 与 rembg 仍保持占位，不属于当前已完成能力

当前工作流的重点仍然是：
- 节点顺序稳定
- 结构化数据契约稳定
- 本地落盘稳定
- 预览与下载链路稳定

---

## 二、节点顺序
当前工作流节点按以下顺序执行：

1. `ingest_assets`
2. `analyze_product`
3. `plan_shots`
4. `generate_copy`
5. `generate_layout`
6. `build_prompts`
7. `render_images`
8. `overlay_text`
9. `run_qc`
10. `finalize`

---

## 三、节点职责说明

### 1. ingest_assets
职责：
- 接收上传文件
- 补充素材尺寸信息
- 为后续节点准备结构化资产数据

当前状态：
- 保持本地文件处理逻辑
- 不调用真实 provider

主要落盘：
- `inputs/`
- `task.json`

### 2. analyze_product
职责：
- 分析商品基础信息
- 生成后续图组规划的基础输入

当前状态：
- `mock` 模式下使用本地规则输出
- `real` 模式下切换到 NVIDIA 多模态模型做 SKU 级视觉分析

主要落盘：
- `product_analysis.json`

### 3. plan_shots
职责：
- 规划本次任务要生成的图型集合
- 为每张图定义展示目标和卖点方向

当前状态：
- `mock` 模式下使用本地规则输出
- `real` 模式下切换到 NVIDIA GLM-5 结构化输出

主要落盘：
- `shot_plan.json`

### 4. generate_copy
职责：
- 生成标题、副标题、卖点条目等结构化中文文案

当前状态：
- `mock` 模式下使用本地规则输出
- `real` 模式下切换到 NVIDIA GLM-5 结构化输出

主要落盘：
- `copy_plan.json`

### 5. generate_layout
职责：
- 为每张图生成标题区、副标题区、卖点区的坐标与尺寸信息
- 为 Pillow 后贴字提供结构化布局数据

当前状态：
- 当前仍保持 mock / 规则型布局生成
- 本阶段没有接入真实布局模型

主要落盘：
- `layout_plan.json`

### 6. build_prompts
职责：
- 生成图片模型提示词所需的结构化内容
- 约束主体保持、风格一致和文案留白区域

当前状态：
- `mock` 模式下使用本地 prompt 构造
- `real` 模式下切换到 NVIDIA GLM-5 结构化输出

主要落盘：
- `image_prompt_plan.json`

### 7. render_images
职责：
- 生成基础图片

当前状态：
- `mock` 模式下输出本地占位图
- `real` 模式下切换到 RunAPI Gemini Image Gen

主要落盘：
- `generated/`

### 8. overlay_text
职责：
- 使用 Pillow 将中文文案渲染到图片上
- 生成最终可预览图片

当前状态：
- 始终保留为本地 Pillow 后贴字方案
- 不依赖图片模型直接输出正式中文

主要落盘：
- `final/`
- `previews/`

### 9. run_qc
职责：
- 对当前任务做基础检查
- 检查产物是否完整
- 记录 `review_required` 状态

当前状态：
- 以基础规则检查为主
- OCR 相关能力仍为占位

主要落盘：
- `qc_report.json`

### 10. finalize
职责：
- 汇总任务产物
- 生成导出文件
- 生成 ZIP 包
- 准备 UI 预览与下载结果

主要落盘：
- `exports/`

---

## 四、当前落盘产物
每次任务执行后，`outputs/tasks/{task_id}/` 目录下通常包含：
- `inputs/`
- `task.json`
- `product_analysis.json`
- `shot_plan.json`
- `copy_plan.json`
- `layout_plan.json`
- `image_prompt_plan.json`
- `qc_report.json`
- `generated/`
- `final/`
- `previews/`
- `exports/`

---

## 五、当前阶段说明
当前工作流已经不是“只支持 mock”的状态，但也不是“全部能力都已真实化”的状态。

更准确的阶段划分是：
- 真实视觉 provider 已接入：`analyze_product`
- 真实文本 provider 已接入：`plan_shots`、`generate_copy`、`build_prompts`
- 真实图片 provider 已接入：`render_images`
- 仍保持 mock / 占位：`generate_layout`、`run_qc` 中的 OCR 路径、OCR 服务、rembg 服务

必须继续保证：
- 结构化产物存在
- 预览可显示
- 下载可用
- 文本继续走后贴字

---

## 六、当前与后续边界
当前已完成的真实接线：
- 商品分析视觉能力：`NVIDIAVisionProductAnalysisProvider`
- 文本规划能力：`NVIDIATextProvider`
- 图片能力：`RunApiGeminiImageProvider`

当前尚未进入范围的能力：
- 真实 OCR 运行时
- 真实 rembg 运行时
- 多模型 fallback
- 更复杂的自动复核与失败重试策略

---

## 七、结论
当前工作流已经从第一阶段 Mock MVP 平滑进入第二阶段真实 provider 接线状态。  
后续应继续保持节点契约、目录结构和 Pillow 后贴字方案稳定，而不是重做整体 workflow。

