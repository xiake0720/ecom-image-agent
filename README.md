# ecom-image-agent

## 1. 项目简介
`ecom-image-agent` 是一个电商图片生成工作台仓库，当前采用：
- 后端：FastAPI
- 前端：React + TypeScript + Vite
- 主图引擎：`backend/engine/`（LangGraph 工作流 + provider/router）

当前仓库目标是：**本地可运行、主链路可观测、任务可追溯、文档与实现一致**。当前阶段不宣称生产可用。

## 2. 当前正式架构
- 主图：独立 `main graph`，入口为 [`backend/engine/workflows/graph.py`](/D:/python/ecom-image-agent/backend/engine/workflows/graph.py)
- 详情图：独立 `detail graph`，入口为 [`backend/engine/workflows/detail_graph.py`](/D:/python/ecom-image-agent/backend/engine/workflows/detail_graph.py)
- 模型路由：统一走 [`backend/engine/providers/router.py`](/D:/python/ecom-image-agent/backend/engine/providers/router.py)
- 任务索引：`storage/tasks/index.json`
- 任务产物：`outputs/tasks/{task_id}/`

详情图已从旧的 service 串行实现升级为“**导演 Agent + 生产 Graph**”双层架构：
- Agent 负责：规划、文案、最终渲染 prompt
- Graph 负责：节点编排、状态持久化、模型调用、QC、导出、runtime

## 3. 目录结构
```text
backend/
  api/                     # FastAPI 路由层
  services/                # 业务编排层
  schemas/                 # API contract
  repositories/            # 任务索引读写
  engine/
    providers/             # 统一文本/图片 provider 与 router
    workflows/             # main graph 与 detail graph
    services/              # 存储、渲染等底层能力
  templates/               # detail 模板资源
frontend/
  src/pages/               # 页面容器
  src/components/          # 通用组件与 detail 工作台组件
  src/services/            # API 调用封装
  src/types/               # 前端 contract 类型
docs/                      # 中文事实文档
storage/tasks/             # 任务索引
outputs/tasks/             # 任务产物
```

## 4. 本地启动

### 4.1 后端
```bash
pip install -e .
uvicorn backend.main:app --reload --port 8000
```

### 4.2 前端
```bash
cd frontend
npm install
npm run dev
```

默认后端地址：`http://127.0.0.1:8000`  
默认前端地址：`http://127.0.0.1:5173`

## 5. 环境变量

### 5.1 FastAPI 应用层（`ECOM_`）
定义位置：[`backend/core/config.py`](/D:/python/ecom-image-agent/backend/core/config.py)
- `ECOM_APP_NAME`
- `ECOM_DEBUG`
- `ECOM_API_PREFIX`
- `ECOM_CORS_ORIGINS`
- `ECOM_STORAGE_ROOT`
- `ECOM_OUTPUTS_ROOT`
- `ECOM_TEMPLATE_ROOT`

### 5.2 引擎与 provider 层（`ECOM_IMAGE_AGENT_`）
定义位置：[`backend/engine/core/config.py`](/D:/python/ecom-image-agent/backend/engine/core/config.py)
- `ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE`：`mock` / `real`
- `ECOM_IMAGE_AGENT_IMAGE_PROVIDER_MODE`：`mock` / `real`
- `ECOM_IMAGE_AGENT_TEXT_PROVIDER`：当前支持 `runapi_openai`
- `ECOM_IMAGE_AGENT_IMAGE_PROVIDER`：当前默认 `banana2`
- `ECOM_IMAGE_AGENT_GOOGLE_API_KEY`：Google 官方 Gemini API Key
- `ECOM_IMAGE_AGENT_RUNAPI_API_KEY`：RunAPI 通道 Key
- `ECOM_IMAGE_AGENT_RUNAPI_TEXT_API_KEY`：文本专用 RunAPI Key
- `ECOM_IMAGE_AGENT_BANANA2_MODEL`：默认 `gemini-3.1-flash-image-preview`

### 5.3 mock / real 切换
- `mock`：`ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE=mock` 且 `ECOM_IMAGE_AGENT_IMAGE_PROVIDER_MODE=mock`
- `real`：`ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE=real` 且 `ECOM_IMAGE_AGENT_IMAGE_PROVIDER_MODE=real`

detail 不再单独维护一套 mock 开关，直接复用主图同一套 provider/router 与 mode 体系。

## 6. 当前核心 API
- `GET /api/health`
- `POST /api/image/generate-main`
- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `GET /api/tasks/{task_id}/runtime`
- `GET /api/tasks/{task_id}/files/{file_name}`
- `POST /api/detail/jobs`
- `POST /api/detail/jobs/plan`
- `GET /api/detail/jobs/{task_id}`
- `GET /api/detail/jobs/{task_id}/runtime`
- `GET /api/detail/jobs/{task_id}/files/{file_name}`
- `GET /api/templates/main-images`
- `GET /api/templates/detail-pages`
- `POST /api/templates/detail-pages/preview`

详细字段见 [`docs/api.md`](/D:/python/ecom-image-agent/docs/api.md)。

## 7. 当前页面路由
- `/main-images`：主图工作台
- `/detail-pages`：茶叶详情图工作台
- `/tasks`：历史任务
- `/templates`：模板中心
- `/preview`：预览中心
- `/dashboard`：数据中心
- `/settings`：系统设置
- `/assets-library`：资源库
- `/login`：登录页

## 8. 详情图系统 V1 已完成能力
- detail 已独立成 graph，不再混在 main graph 里
- detail 拥有独立 `task_id`、独立 runtime、独立产物目录、独立失败状态
- detail 输入统一落盘为：
  - `inputs/request_payload.json`
  - `inputs/asset_manifest.json`
- detail Agent 输出统一落盘为：
  - `plan/detail_plan.json`
  - `plan/detail_copy_plan.json`
  - `plan/detail_prompt_plan.json`
- detail 正式渲染统一通过 `banana2` 图片路由；当前优先使用 Google 官方 `google.genai` SDK，缺失 Google Key 时回退到 RunAPI，结果落盘到 `generated/*.png`
- detail QC 输出：
  - `qc/detail_qc_report.json`
- detail 最终导出：
  - `exports/detail_bundle.zip`
- detail mock mode 已改成 provider 级 mock，不再使用运行时 PIL 拼接详情图
- 前端 `/detail-pages` 已重构为三栏工作台，支持：
  - 主图结果导入
  - 规划/文案/prompt 预览
  - runtime 轮询
  - 结果预览
  - 单张下载
  - ZIP 下载
  - 真实错误透出

## 9. 主图未被破坏的边界
- main graph 仍使用 [`backend/engine/workflows/graph.py`](/D:/python/ecom-image-agent/backend/engine/workflows/graph.py)
- 主图 API 仍是 `POST /api/image/generate-main`
- 主图 runtime 仍是 `GET /api/tasks/{task_id}/runtime`
- main/detail 只共享 provider/router、storage、task repository 等底层能力
- detail 不回写 main task 状态

## 10. 文档索引
- [`docs/architecture.md`](/D:/python/ecom-image-agent/docs/architecture.md)
- [`docs/api.md`](/D:/python/ecom-image-agent/docs/api.md)
- [`docs/workflow.md`](/D:/python/ecom-image-agent/docs/workflow.md)
- [`docs/frontend-workbench.md`](/D:/python/ecom-image-agent/docs/frontend-workbench.md)
- [`docs/codebase-file-map.md`](/D:/python/ecom-image-agent/docs/codebase-file-map.md)
- [`docs/storage.md`](/D:/python/ecom-image-agent/docs/storage.md)
- [`docs/development-rules.md`](/D:/python/ecom-image-agent/docs/development-rules.md)

## 11. 协作规范
根目录 [`AGENTS.md`](/D:/python/ecom-image-agent/AGENTS.md) 为仓库级执行规范，代码修改需同步遵守其中的：
- 分层职责
- 文档同步规则
- 禁止事项
- 提交前检查清单

