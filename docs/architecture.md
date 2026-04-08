# 架构说明

## 1. 总体结构
当前仓库采用前后端分离：
- `frontend/`：React 工作台
- `backend/`：FastAPI API 服务
- `backend/engine/`：生成引擎、provider/router、workflow、存储与渲染底层能力

当前正式架构分为两条独立任务流：
- 主图任务流：`main graph`
- 详情图任务流：`detail graph`

两者共享：
- provider/router
- storage
- task repository
- 统一任务目录约定

两者隔离：
- task_id
- runtime
- 任务产物目录
- 错误状态
- graph 编排文件

## 2. 主图系统

### 2.1 编排入口
- [`backend/engine/workflows/graph.py`](/D:/python/ecom-image-agent/backend/engine/workflows/graph.py)

### 2.2 固定节点
1. `ingest_assets`
2. `director_v2`
3. `prompt_refine_v2`
4. `render_images`
5. `run_qc`
6. `finalize`

### 2.3 服务入口
- [`backend/services/main_image_service.py`](/D:/python/ecom-image-agent/backend/services/main_image_service.py)

## 3. 详情图系统

### 3.1 架构升级后的正式形态
详情图已从旧的 service 串行版升级为“**导演 Agent + 生产 Graph**”：

导演 Agent：
- 负责理解素材与输入参数
- 负责规划整套详情图叙事
- 负责生成结构化文案
- 负责生成最终 Banana2 render prompt

生产 Graph：
- 负责节点顺序
- 负责状态传递
- 负责中间结果落盘
- 负责 runtime 聚合所需 artifact
- 负责图片 provider 调用
- 负责 QC
- 负责 ZIP 导出

### 3.2 编排入口
- [`backend/engine/workflows/detail_graph.py`](/D:/python/ecom-image-agent/backend/engine/workflows/detail_graph.py)

### 3.3 状态定义
- [`backend/engine/workflows/detail_state.py`](/D:/python/ecom-image-agent/backend/engine/workflows/detail_state.py)

关键状态：
- `detail_payload`
- `detail_assets`
- `detail_plan`
- `detail_copy_blocks`
- `detail_prompt_plan`
- `detail_render_results`
- `detail_qc_summary`

### 3.4 节点链路
1. `detail_ingest_assets`
2. `detail_plan`
3. `detail_generate_copy`
4. `detail_generate_prompt`
5. `detail_render_pages`
6. `detail_run_qc`
7. `detail_finalize`

### 3.5 节点目录
- [`backend/engine/workflows/detail_nodes/`](/D:/python/ecom-image-agent/backend/engine/workflows/detail_nodes)

### 3.6 服务入口
- [`backend/services/detail_page_job_service.py`](/D:/python/ecom-image-agent/backend/services/detail_page_job_service.py)

### 3.7 导演层服务
- [`backend/services/detail_planner_service.py`](/D:/python/ecom-image-agent/backend/services/detail_planner_service.py)
- [`backend/services/detail_copy_service.py`](/D:/python/ecom-image-agent/backend/services/detail_copy_service.py)
- [`backend/services/detail_prompt_service.py`](/D:/python/ecom-image-agent/backend/services/detail_prompt_service.py)

### 3.8 渲染与 runtime
- [`backend/services/detail_render_service.py`](/D:/python/ecom-image-agent/backend/services/detail_render_service.py)
- [`backend/services/detail_runtime_service.py`](/D:/python/ecom-image-agent/backend/services/detail_runtime_service.py)

## 4. provider/router 体系

### 4.1 统一入口
- [`backend/engine/providers/router.py`](/D:/python/ecom-image-agent/backend/engine/providers/router.py)

### 4.2 文本能力
- 主图与详情图共用统一文本路由
- 当前 real 路由：`runapi_openai`
- 当前 mock 路由：本地 mock text provider

### 4.3 图片能力
- 主图与详情图共用统一图片路由
- 当前默认 real 路由：`banana2`
- 当前 mock 路由：provider 级 mock image provider

### 4.4 Banana2
- provider 文件：[`backend/engine/providers/image/banana2_image.py`](/D:/python/ecom-image-agent/backend/engine/providers/image/banana2_image.py)
- 真实模式优先使用 Google 官方 `google.genai` SDK
- 当前默认模型：`gemini-3.1-flash-image-preview`
- 若未配置 Google API Key，则回退到现有 RunAPI 通道

## 5. mock mode 设计
- mock mode 不再是本地拼图模式
- mock text provider 返回稳定结构化 plan/copy/prompt
- mock image provider 复制预置 mock 样张到 `generated/`
- detail graph 在 mock/real 两种模式下共用同一套节点、落盘、runtime 与下载流程

## 6. 存储结构
任务索引：
- `storage/tasks/index.json`

任务目录：
- `outputs/tasks/{task_id}/`

详情图任务常见产物：
- `inputs/request_payload.json`
- `inputs/asset_manifest.json`
- `plan/detail_plan.json`
- `plan/detail_copy_plan.json`
- `plan/detail_prompt_plan.json`
- `generated/*.png`
- `generated/detail_render_report.json`
- `qc/detail_qc_report.json`
- `detail_manifest.json`
- `exports/detail_bundle.zip`

## 7. 前端工作台
- 主图页：[`frontend/src/pages/MainImagePage.tsx`](/D:/python/ecom-image-agent/frontend/src/pages/MainImagePage.tsx)
- 详情图页：[`frontend/src/pages/DetailPageGeneratorPage.tsx`](/D:/python/ecom-image-agent/frontend/src/pages/DetailPageGeneratorPage.tsx)

详情图前端已重构为三栏工作台：
- 左栏：输入与素材控制
- 中栏：主图导入 + 规划 + 文案 + prompt + 结果图
- 右栏：状态、进度、QC、错误、ZIP

## 8. 与旧 detail 实现的区别
旧实现：
- `detail_page_job_service.py` 内串行执行 planner/copy/prompt/render
- 没有独立 detail graph
- runtime 主要按文件猜测状态

当前实现：
- detail 独立 graph
- detail 独立 state
- detail 渲染统一走 Banana2 provider
- detail runtime 读取 graph 真实产物
- detail mock mode 改为 provider 级 mock
