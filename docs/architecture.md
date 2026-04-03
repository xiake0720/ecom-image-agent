# 架构说明

## 1. 整体架构
当前仓库为前后端分离架构：
- `frontend/`：React 工作台，负责用户交互与结果展示。
- `backend/`：FastAPI API 服务，负责任务接入、任务查询、模板与资产访问。
- `backend/engine/`：主图生成核心引擎（workflow、provider、渲染、落盘）。

## 2. frontend / backend 角色

### 2.1 前端（React）
- 页面入口：`frontend/src/main.tsx`。
- 核心页面：`frontend/src/pages/MainImagePage.tsx`。
- 职责：上传文件、提交任务、轮询任务 runtime、展示进度与结果、触发预览下载。

### 2.2 后端（FastAPI）
- 服务入口：`backend/main.py`。
- 路由层：`backend/api/`。
- 服务层：`backend/services/`。
- 职责：
  - 接收任务请求并落盘；
  - 调用引擎执行主图 workflow；
  - 提供任务列表、任务 runtime、任务文件访问；
  - 提供详情页模板化生成功能。

## 3. 核心数据流

### 3.1 主图任务数据流
1. 前端发起 `POST /api/image/generate-main`（multipart）。
2. `MainImageService.prepare_generation` 创建 `task_id`，落盘上传素材与 `task.json`。
3. 任务写入 `storage/tasks/index.json`，并进入进程内队列。
4. 队列 worker 调用 `run_workflow` 执行主图链路。
5. 执行中持续回写任务状态，前端通过 runtime API 轮询查看。
6. 前端通过任务文件 API 获取图片与 ZIP。

### 3.2 详情页数据流
1. 前端发起 `POST /api/detail/generate` 或 `POST /api/templates/detail-pages/preview`。
2. `DetailPageService` 按平台+风格选择模板并组装模块。
3. 落盘 `detail_page_modules.json`，并写入任务摘要。
4. 接口返回 `modules`、`preview_data`、导出素材信息。

## 4. 主图生成流程（后端）
固定主链路（由 `backend.engine.workflows.graph.run_workflow` 执行）：
1. `ingest_assets`
2. `director_v2`
3. `prompt_refine_v2`
4. `render_images`
5. `run_qc`
6. `finalize`

## 5. 详情页生成流程（后端）
- 按模板定义模块骨架；
- 根据请求内容填充文案与素材引用；
- 输出结构化 JSON（`detail_page_modules.json`）与预览数据。

## 6. 存储层位置
- 任务索引：`storage/tasks/index.json`
- 任务产物：`outputs/tasks/{task_id}/`
  - 常见子目录：`inputs/`、`generated/`、`final/`、`exports/`
- 模板文件：`backend/templates/detail_pages/*.json`


## 新增：detail_page_v2 独立任务流
- 入口：`/api/detail/jobs` 与 `/api/detail/jobs/plan`。
- 与主图关系：仅可引用主图结果文件作为素材，不耦合 workflow，不共享 runtime 字段。
- 任务目录：`outputs/tasks/{task_id}/inputs|plan|generated|qc|exports`。
- 产物：规划 JSON、文案 JSON、prompt JSON、QC JSON、详情图 PNG 与 ZIP。
