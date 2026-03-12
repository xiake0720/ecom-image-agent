# 系统架构说明

## 1. 项目总体定位

本项目当前是一个面向茶叶电商图片生产场景的本地 Streamlit 单体应用，目标不是上线生产，而是把“上传素材 -> 工作流执行 -> 结构化 JSON 落盘 -> 图片生成 -> 中文后贴字 -> 预览与下载”这条链路跑通，并保持中间产物可检查、可回放。

当前仓库仍处于第二阶段“真实 provider 接线阶段”，但代码现状不是“全链路都已真实化”：

- 入口仍然只有 `streamlit_app.py`
- 工作流仍然是 `LangGraph + Pydantic schema + 本地目录落盘`
- 中文文案仍然统一通过 Pillow 后贴字
- 文本侧真实 provider 已有实现文件：`NVIDIATextProvider`
- 图片侧真实 provider 已有实现文件：`RunApiGeminiImageProvider`
- `generate_layout`、OCR、rembg 仍然是规则或占位实现
- 视觉分析真实 provider 已有实现文件：`src/providers/vision/nvidia_product_analysis.py`
- 默认主链路模型已切到 Qwen3.5，GLM-5 仍保留为可切换文本模型
- 模型调用选择已集中到 `src/providers/router.py`
- `build_prompts` 在 real 模式下继续逐张 shot 调用当前结构化规划模型，并补充 per-shot JSON 调试产物

本文以当前仓库中的真实代码为准。如果旧文档表述与代码不一致，以代码现状为准。

## 2. 系统整体架构图

```mermaid
flowchart TD
    U[用户] --> S[Streamlit UI\nstreamlit_app.py]
    S --> H[src/ui/pages/home.py\nrender_home_page / _run_task]

    H --> LS[LocalStorageService\n创建 task_id / 保存 task.json / 保存 uploads]
    LS --> TASKDIR[outputs/tasks/{task_id}/\ninputs/\ntask.json]

    H --> G[src/workflows/graph.py\nbuild_workflow()]
    G --> LG[LangGraph StateGraph\n10 个固定节点]

    subgraph WF[Workflow Nodes]
        N1[ingest_assets]
        N2[analyze_product]
        N3[plan_shots]
        N4[generate_copy]
        N5[generate_layout]
        N6[build_prompts]
        N7[render_images]
        N8[overlay_text]
        N9[run_qc]
        N10[finalize]
        N1 --> N2 --> N3 --> N4 --> N5 --> N6 --> N7 --> N8 --> N9 --> N10
    end

    LG --> WF

    N2 --> VP[Vision Provider\nmock 规则 / NVIDIAVisionProductAnalysisProvider(real)]
    N3 --> TP[Planning Provider\nGeminiTextProvider(mock)\nNVIDIATextProvider(real)]
    N4 --> TP
    N6 --> TP
    N7 --> IP[Image Provider\nGeminiImageProvider(mock)\nRunApiGeminiImageProvider(real)]
    N8 --> TR[TextRenderer + Pillow]
    N9 --> QC[image_qc + ocr_qc\nPaddleOCRService 占位]
    N10 --> ZIP[zip_export]

    N2 --> PA[product_analysis.json]
    N3 --> SP[shot_plan.json]
    N4 --> CP[copy_plan.json]
    N5 --> LP[layout_plan.json]
    N6 --> PP[image_prompt_plan.json\nartifacts/shots/{shot_id}/prompt.json]
    N7 --> GD[generated/*.png]
    N8 --> FD[final/*.png\npreviews/*.png]
    N9 --> QR[qc_report.json]
    N10 --> EX[exports/{task_id}_images.zip\n回写 task.json]

    LG --> STATE[WorkflowState]
    STATE --> H
    H --> RV[src/ui/pages/result_view.py\n日志 / 调试信息 / 预览 / 下载]
```

## 3. 调用链说明

### 3.1 用户在 Streamlit 页面做什么

用户通过 `python -m streamlit run streamlit_app.py` 启动应用后，首页由 `src/ui/pages/home.py` 渲染。页面左侧完成两类输入：

- `render_upload_panel()` 上传商品素材图
- `render_task_form()` 填写品牌名、产品名、平台、尺寸、张数、文案风格

点击“开始生成”后，页面层调用 `_run_task(form_data, uploads)`。

### 3.2 UI 如何触发 workflow

`_run_task()` 在进入 LangGraph 之前，先做三件事：

1. 用 `LocalStorageService.create_task_id()` 创建任务 ID
2. 用 `save_task_manifest()` 先写入 `outputs/tasks/{task_id}/task.json`
3. 用 `save_uploads()` 把上传文件写入 `outputs/tasks/{task_id}/inputs/`

然后构造初始状态：

- `task`
- `assets`
- `logs`

最后执行：

```python
workflow = build_workflow()
state = workflow.invoke(initial_state)
```

也就是说，真正的工作流入口不在 UI 组件里，而是在 `_run_task()` 里调用 `build_workflow().invoke(...)`。

### 3.3 LangGraph 在哪里接入

LangGraph 的真实接入点在：

- `src/workflows/graph.py`

这里做了几件关键事情：

- 用 `StateGraph(WorkflowState)` 定义图
- 通过 `build_dependencies()` 统一注入 storage / provider / renderer / OCR service
- 通过 `src/providers/router.py` 先解析“结构化规划 / 视觉分析 / 图片生成”三类能力，再注入到 workflow
- 按固定顺序注册 10 个节点
- 用 `_wrap_node()` 给每个节点统一增加开始、结束、异常、耗时日志
- `graph.compile()` 后返回可直接 `invoke()` 的图对象

需要注意的实现细节：

- `build_workflow()` 被 `@lru_cache(maxsize=1)` 缓存
- `get_settings()` 也被缓存

因此 provider mode 的实际依赖构建发生在当前 Streamlit 进程第一次构建 workflow 时。修改环境变量后，如果不重启进程，不应假设 provider 已经随之切换。

### 3.4 workflow 如何调用 provider / service

当前 10 个节点按固定顺序执行：

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

其中：

- `analyze_product` 在 `vision_provider_mode=mock` 时走 `build_mock_product_analysis()`；real 分支调用 `deps.vision_provider.generate_structured_from_assets(...)`
- `plan_shots`、`generate_copy`、`build_prompts` 在 `text_provider_mode=real` 时调用 `deps.planning_provider.generate_structured(...)`
- `render_images` 统一调用 `deps.image_provider.generate_images(...)`
- `overlay_text` 调用 `deps.text_renderer.render_copy(...)`，并生成 `final/` 与 `previews/`
- `run_qc` 调用 `build_dimension_check()` 与 `build_ocr_check()`
- `finalize` 更新任务状态并打包 ZIP

运行时使用的 prompt 文件来自 `src/prompts/*.md`，不是 `docs/` 目录。

### 3.5 结果如何回到 UI 展示与下载

workflow 返回后，`_run_task()` 会做两类收尾：

- 把 `task`、`generation_result`、`qc_report` 转成适合 `st.session_state` 存储的字典
- 额外生成 `previews/text_render_test.png` 和 `previews/text_render_base.png` 作为后贴字链路测试样图

随后 `render_result_view()` 展示：

- `logs`
- `debug_info`
- 结果图片
- 单图下载按钮
- ZIP 下载按钮

当前 UI 有一个实际行为需要特别说明：

- `overlay_text` 虽然会写 `preview_path`
- 但结果页真正展示和下载的是 `generation_result.images[*].image_path`
- 在 `overlay_text` 执行完成后，这个字段已经被改写为 `final/*.png`

因此当前页面展示的其实是最终图，而不是 `previews/` 缩略图。

## 4. 分层职责说明

### 4.1 UI 层

位置：

- `streamlit_app.py`
- `src/ui/`

职责：

- 收集上传素材和表单参数
- 触发 `_run_task()`
- 展示日志、调试信息、结果预览和下载按钮

边界：

- 不直接写 provider HTTP 请求
- 不直接拼装 LangGraph 节点逻辑

### 4.2 Workflow 层

位置：

- `src/workflows/`

职责：

- 定义 `WorkflowState`
- 定义 `WorkflowDependencies`
- 组装 LangGraph 图
- 串联 10 个节点
- 统一日志与异常包装

边界：

- 节点消费 provider/service，但不处理底层 HTTP 细节

### 4.3 Domain 层

位置：

- `src/domain/`

职责：

- 统一定义任务对象、资产对象、商品分析、图组规划、文案、布局、图片生成结果、QC 报告等 schema
- 作为节点间传递和落盘 JSON 的主契约

当前核心 schema：

- `Task`
- `Asset`
- `ProductAnalysis`
- `ShotPlan`
- `CopyPlan`
- `LayoutPlan`
- `ImagePromptPlan`
- `GenerationResult`
- `QCReport`

### 4.4 Provider 层

位置：

- `src/providers/`

职责：

- 统一封装文本模型和图片模型调用
- 提供 mock / real 两类实现
- 把外部响应校验为 Pydantic 结构化对象

当前真实存在的实现文件：

- 文本 mock：`src/providers/llm/gemini_text.py`
- 文本 real：`src/providers/llm/nvidia_text.py`
- 视觉 real：`src/providers/vision/nvidia_product_analysis.py`
- 图片 mock：`src/providers/image/gemini_image.py`
- 图片 real：`src/providers/image/runapi_gemini_image.py`
- 能力路由：`src/providers/router.py`

### 4.5 Service 层

位置：

- `src/services/`

职责：

- 本地存储与 ZIP 导出
- mock 规划逻辑
- Pillow 中文后贴字
- 图片预览图生成
- 基础 QC
- OCR / rembg 占位服务

### 4.6 Local Storage 层

当前位置实际由两部分组成：

- 路径约定：`src/core/paths.py`
- 读写实现：`src/services/storage/local_storage.py`

真实职责：

- 统一创建 `outputs/tasks/{task_id}/`
- 统一写 `task.json`、中间 JSON、上传素材、最终图、ZIP

需要注意：

- `ingest_assets` 节点本身不负责把上传文件写入磁盘
- 上传文件和 `task.json` 的真实落盘发生在 UI 层 `_run_task()` 中

## 5. 当前 provider 分工

### 5.1 文本 provider

负责节点：

- `plan_shots`
- `generate_copy`
- `build_prompts`

实现分工：

- `GeminiTextProvider`：当前代码中的 mock 文本 provider，本地直接返回伪造结构化 payload，不调用真实 Gemini API
- `NVIDIATextProvider`：当前真实结构化规划 provider，调用 NVIDIA NIM 的 OpenAI-compatible chat completions，并强制 JSON-only 输出
- 默认模型是 `Qwen3.5`
- 如需切换，可通过配置改为 `GLM-5`

### 5.2 视觉分析 provider

代码现状：

- `analyze_product` 节点中存在 `vision_provider_mode` 分支
- real 分支调用 `deps.vision_provider.generate_structured_from_assets(...)`
- `graph.py` 和 `tests/unit/test_provider_modes.py` 都引用了 `NVIDIAVisionProductAnalysisProvider`

当前实现分工：

- `NVIDIAVisionProductAnalysisProvider`：在 `vision_provider_mode=real` 时接收上传商品图，走 NVIDIA 多模态接口，输出受 `ProductAnalysis` 约束的 SKU 级视觉分析
- `analyze_product` 不做 silent fallback；缺 key、缺图片或响应不合法时会显式报错

### 5.3 图片 provider

负责节点：

- `render_images`

实现分工：

- `GeminiImageProvider`：当前 mock 图片 provider，本地用 Pillow 画占位底图
- `RunApiGeminiImageProvider`：当前真实图片 provider，调用 RunAPI 的 Gemini Image Gen，要求至少有一张上传参考图，不做 silent fallback

### 5.4 mock / real 模式怎么切换

配置入口在 `src/core/config.py`，读取以下环境变量：

- `ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE`
- `ECOM_IMAGE_AGENT_VISION_PROVIDER_MODE`
- `ECOM_IMAGE_AGENT_IMAGE_PROVIDER_MODE`

依赖注入发生在 `src/workflows/graph.py -> build_dependencies()`，其中模型选择由 `src/providers/router.py` 集中处理：

- planning：`real -> NVIDIATextProvider`，否则 `GeminiTextProvider`
- image：`real -> RunApiGeminiImageProvider`，否则 `GeminiImageProvider`
- vision：`real -> NVIDIAVisionProductAnalysisProvider(...)`，否则 `None`

## 6. 当前限制

### 6.1 当前已实现

- Streamlit 单体入口与页面交互
- LangGraph 10 节点工作流
- 本地任务目录创建与 JSON 落盘
- mock / real 文本 provider 切换
- mock / real 图片 provider 切换
- Pillow 中文后贴字
- 单图下载与 ZIP 下载

### 6.2 当前未实现或仍是占位

- 真实 OCR 运行时
- 真实 rembg 运行时
- 多模型 fallback
- 数据库、鉴权、消息队列、云部署
- 真实布局模型

### 6.3 当前实现上的重要限制

- `generate_layout` 固定走规则布局，不区分 mock / real
- `run_qc` 的 OCR 检查依赖 `PaddleOCRService`；默认 `enable_ocr_qc=False` 时 `read_text()` 返回空列表，因此 OCR 检查会直接通过
- `save_uploads()` 目前只按顺序把第一张图标为 `product`、其余标为 `detail`，没有真实素材分类
- `finalize` 导出的 ZIP 只打包 `final/` 目录，不包含整套 task 目录和中间 JSON
- prompt 文本实际读取自 `src/prompts/`，`docs/prompts.md` 只是说明文档
- `build_prompts` 虽然已改为逐张 shot 生成，但 `generate_layout` 仍是规则布局，因此文案留白提示仍依赖现有布局规则

## 7. 当前代码与旧文档的冲突点

以下冲突点已按代码现状处理：

1. `ingest_assets` 在旧描述中容易被理解为“负责素材落盘”，但当前真实代码里，`inputs/` 和 `task.json` 的写入发生在 UI 层 `_run_task()`，节点本身只补齐资产宽高。
2. 旧文档曾把 `build_prompts` 写成一次性生成整组 prompt，但当前代码已经改成逐张 shot 调用当前结构化规划模型，并额外落盘 `artifacts/shots/{shot_id}/`。
3. 结果页虽然生成了 `previews/`，但当前 UI 实际展示与下载的是 `final/*.png`。
