# ecom-image-agent

这是一个面向茶叶品类的本地 Streamlit 电商图片生成工具。

当前仓库处于第二阶段“真实 provider 接线阶段”，但仍然以本地可运行、结构化 JSON 落盘、链路清晰、便于检查与回放为优先目标，不应描述为生产可用系统。

当前以真实代码为准可以确认的状态是：

- 入口仍然只有 `streamlit_app.py`
- 工作流仍然是 `Streamlit + LangGraph + 本地文件存储`
- 文本 real provider 已有实现文件：`NVIDIATextProvider`
- 图片 real provider 已有实现文件：`RunApiGeminiImageProvider`
- 中文正式文案仍然统一通过 Pillow 后贴字
- `generate_layout`、OCR、rembg 仍是规则或占位实现
- 视觉分析 real provider 已有实现文件：`NVIDIAVisionProductAnalysisProvider`
- 当前默认主链路模型已切到 Qwen3.5，GLM-5 仍保留为可配置开关
- 模型选择已集中到 provider 路由层，`build_prompts` 在 real 模式下继续保持逐张 shot 精细生成
- `analyze_product` 是当前唯一看图节点，`build_prompts` 当前不再向文本模型发送图片输入
- `plan_shots` 已增加类目边界、核心图型 / 扩展图型和整组风格锚点控制

第一阶段 Mock MVP 归档文档见：

- `docs/milestones/phase-1-mock-mvp.md`

## 当前仓库状态

- 当前包版本：`0.2.0`
- 当前入口：`streamlit_app.py`
- 当前核心形态：Python 3.11、Streamlit 单体应用、LangGraph workflow、本地任务目录落盘

## 程序运行链路简介

程序通过下面的命令启动：

```bash
python -m streamlit run streamlit_app.py
```

启动后，`streamlit_app.py` 会进入 `src/ui/pages/home.py::render_home_page()`。页面负责收集上传图片和任务参数，点击“开始生成”后执行 `_run_task()`。

`_run_task()` 会先创建 `task_id`，把上传素材写入 `outputs/tasks/{task_id}/inputs/`，并先落一版 `task.json`，然后调用 `src/workflows/graph.py::build_workflow().invoke(initial_state)` 执行 LangGraph。

之所以使用 Streamlit，是因为当前阶段只需要一个本地单体 UI 来完成上传、表单输入、预览和下载，不需要拆分前后端。LangGraph 的作用是把 10 个固定节点按稳定顺序串起来，并统一状态传递、日志和异常边界。最终结果会写入 `outputs/tasks/{task_id}/`，页面再从该任务目录对应的返回状态中展示结果和下载按钮。

## 当前已具备能力

- 本地上传商品素材图
- 本地创建任务目录
- LangGraph 10 节点工作流
- mock / real 视觉分析 provider 切换
- mock / real 文本 provider 切换
- mock / real 图片 provider 切换
- Pillow 中文后贴字
- 结果预览
- 单图下载
- ZIP 下载

## 当前系统模块说明

- `src/ui`
  - Streamlit 页面、上传组件、结果展示、下载按钮、页面状态管理
- `src/workflows`
  - `WorkflowState`、依赖注入、LangGraph 图构建、10 个节点实现
- `src/providers`
  - 文本 provider、图片 provider 及 mock / real 实现
- `src/services`
  - 本地存储、ZIP 导出、mock 规划逻辑、Pillow 渲染、QC、OCR/rembg 占位服务
- `outputs/tasks`
  - 每个任务的输入图片、中间 JSON、生成图片、最终图片、预览图和 ZIP 导出

## 当前工作流节点

固定顺序如下：

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

## 当前 provider 说明

文本侧：

- `GeminiTextProvider`：当前代码里的 mock 文本 provider，本地返回伪造结构化数据
- `NVIDIATextProvider`：当前真实结构化规划 provider，通过 NVIDIA NIM 返回结构化 JSON
- 默认模型是 `qwen/qwen3.5-122b-a10b`
- 如需回切，可通过开关改为 `z-ai/glm5`

图片侧：

- `GeminiImageProvider`：当前代码里的 mock 图片 provider，本地生成占位图
- `RunApiGeminiImageProvider`：当前真实图片 provider，通过 RunAPI 调用 Gemini Image Gen

视觉分析侧：

- `NVIDIAVisionProductAnalysisProvider`：当前真实视觉分析 provider，使用支持图片输入的 NVIDIA 多模态接口做 SKU 级商品分析
- `analyze_product` 在 `vision_provider_mode=real` 时会直接把上传商品图传给该 provider，不做 silent fallback

## 当前任务目录结构

每个任务落盘到：

```text
outputs/tasks/{task_id}/
```

至少会包含：

- `inputs/`
- `task.json`
- `product_analysis.json`
- `shot_plan.json`
- `copy_plan.json`
- `layout_plan.json`
- `image_prompt_plan.json`
- `artifacts/shots/{shot_id}/shot.json`
- `artifacts/shots/{shot_id}/copy.json`
- `artifacts/shots/{shot_id}/layout.json`
- `artifacts/shots/{shot_id}/prompt.json`
- `qc_report.json`
- `generated/`
- `final/`
- `previews/`
- `exports/`

其中要注意两点：

- `inputs/` 和第一次写入的 `task.json` 是在 UI 层 `_run_task()` 里完成的，不是 `ingest_assets` 节点完成的
- `exports/{task_id}_images.zip` 当前只打包 `final/` 目录，不包含整套任务目录

## 当前目录说明

- `streamlit_app.py`：唯一 UI 入口
- `src/core/`：配置、常量、路径工具
- `src/domain/`：Pydantic schema
- `src/providers/`：provider 接口与 mock / real 实现
- `src/services/`：本地存储、规划、渲染、QC 与占位服务
- `src/workflows/`：状态定义、LangGraph 图与节点
- `src/ui/`：上传表单、结果页、下载组件
- `src/prompts/`：运行时真正读取的 prompt 文件
- `docs/`：架构、工作流、提示词、QA 规则与里程碑文档
- `tests/`：schema、渲染与 provider mode 等测试

## 当前运行方式

安装：

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
python -m pip install -e .[dev]
```

启动：

```bash
python -m streamlit run streamlit_app.py
```

## 环境变量

基础配置：

```env
ECOM_IMAGE_AGENT_VISION_PROVIDER_MODE=mock
ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE=mock
ECOM_IMAGE_AGENT_IMAGE_PROVIDER_MODE=mock
ECOM_IMAGE_AGENT_TEXT_MODEL_PROVIDER=qwen
ECOM_IMAGE_AGENT_VISION_MODEL_PROVIDER=qwen
ECOM_IMAGE_AGENT_DEFAULT_FONT_PATH=assets/fonts/NotoSansSC-Regular.otf
ECOM_IMAGE_AGENT_PROVIDER_TIMEOUT_SECONDS=120
```

文本 / 视觉模型选择：

```env
ECOM_IMAGE_AGENT_TEXT_MODEL_PROVIDER=qwen
ECOM_IMAGE_AGENT_VISION_MODEL_PROVIDER=qwen
ECOM_IMAGE_AGENT_QWEN_MODEL_ID=qwen/qwen3.5-122b-a10b
ECOM_IMAGE_AGENT_GLM5_MODEL_ID=z-ai/glm5
ECOM_IMAGE_AGENT_TEXT_MODEL_ID=
ECOM_IMAGE_AGENT_VISION_MODEL_ID=
```

文本 real provider：

```env
ECOM_IMAGE_AGENT_NVIDIA_API_KEY=
ECOM_IMAGE_AGENT_NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
ECOM_IMAGE_AGENT_NVIDIA_TEXT_MODEL=
```

图片 real provider：

```env
ECOM_IMAGE_AGENT_RUNAPI_API_KEY=
ECOM_IMAGE_AGENT_RUNAPI_IMAGE_BASE_URL=https://runapi.co
ECOM_IMAGE_AGENT_RUNAPI_IMAGE_MODEL=gemini-2.5-flash-image
```

视觉分析相关配置位当前代码仍保留：

```env
ECOM_IMAGE_AGENT_NVIDIA_VISION_API_KEY=
ECOM_IMAGE_AGENT_NVIDIA_VISION_BASE_URL=https://integrate.api.nvidia.com/v1
ECOM_IMAGE_AGENT_NVIDIA_VISION_MODEL=qwen/qwen3.5-122b-a10b
```

说明：

- provider mode 的依赖注入发生在 `src/workflows/graph.py::build_dependencies()`
- 模型能力路由集中在 `src/providers/router.py`
- `plan_shots`、`generate_copy`、`build_prompts` 都通过“结构化规划能力”取 provider，不在节点里写死模型名
- `analyze_product` 通过“视觉分析能力”取 provider，不在节点里写死 Qwen 类名
- `build_workflow()` 和 `get_settings()` 都有缓存；修改环境变量后，建议重启 Streamlit 进程再验证 provider 切换
- 当前实现不做 silent fallback，缺 key 或接口失败时会显式报错
- `build_prompts` 在 real 模式下会逐张 shot 调用当前结构化规划模型，并把单张调试产物写入 `artifacts/shots/{shot_id}/`
- `build_prompts` 当前只基于结构化结果生成 per-shot prompt；真正的参考商品图会在 `render_images` 节点再传给图片模型
- 如当前环境仍设置了旧的 `ECOM_IMAGE_AGENT_NVIDIA_TEXT_MODEL` 或 `ECOM_IMAGE_AGENT_NVIDIA_VISION_MODEL`，调试面板会显示其为 legacy 来源

## 调试与排查建议

日志主要看两处：

- 结果页“任务日志”面板
- `task_state["logs"]` 中的 `streamlit_entry`、`langgraph_invoke` 和各节点日志

排查任务时，优先看这些文件：

- `task.json`
- `product_analysis.json`
- `shot_plan.json`
- `copy_plan.json`
- `layout_plan.json`
- `image_prompt_plan.json`
- `artifacts/shots/{shot_id}/shot.json`
- `artifacts/shots/{shot_id}/copy.json`
- `artifacts/shots/{shot_id}/layout.json`
- `artifacts/shots/{shot_id}/prompt.json`
- `qc_report.json`

如果问题出现在具体阶段，建议按下面顺序看：

1. 看 `task.json` 和 `inputs/`，确认任务和素材是否先落盘成功。
2. 看 `product_analysis.json`、`shot_plan.json`、`copy_plan.json`、`layout_plan.json`、`image_prompt_plan.json`，确认 aggregate 中间结构化输出是否缺失或异常。
3. 如果问题集中在单张图，继续看 `artifacts/shots/{shot_id}/shot.json`、`copy.json`、`layout.json`、`prompt.json`，确认 `build_prompts` 是否已经按逐张 shot 生成高质量提示词。
4. 看 `generated/`、`final/`、`previews/`，确认图片生成、后贴字和预览是否完成。
5. 看 `qc_report.json`，确认失败点在尺寸检查还是 OCR 占位检查。
6. 看 `exports/`，确认 ZIP 是否生成。

额外说明：

- `_run_task()` 成功后还会额外在 `previews/` 下写 `text_render_base.png` 与 `text_render_test.png`，用于快速验证 Pillow 后贴字链路
- 当前结果页实际展示的是 `final/*.png`，不是 `previews/*.png`

## 当前限制

- 当前不是生产可用系统
- `generate_layout` 仍是规则布局
- OCR 仍是占位实现，默认情况下 OCR 检查会直接通过
- rembg 仍未接入真实运行时
- 当前没有多模型 fallback
- 当前没有数据库、鉴权、消息队列、云部署和前后端分离
