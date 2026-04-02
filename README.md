# ecom-image-agent

## 1. 项目简介
`ecom-image-agent` 是一个电商图片生成工作台项目，当前采用前后端分离：
- 后端提供任务提交、任务查询、模板与静态资源访问 API。
- 前端提供主图生成工作台、任务查看、详情页生成等页面。

当前仓库目标是保证：**本地可运行、任务链路可观测、文档与实现一致**，不宣称生产可用。

## 2. 当前技术架构
- 后端：Python 3.11 + FastAPI。
- 前端：React + TypeScript + Vite。
- 主图引擎：`backend/engine/`（LangGraph 工作流与 provider 路由）。
- 存储：本地文件存储（`storage/` + `outputs/tasks/`）。

## 3. 目录结构
```text
backend/
  api/               # FastAPI 路由层
  services/          # 后端业务服务层
  schemas/           # API schema
  repositories/      # 任务索引读写
  engine/            # 主图工作流与模型调用核心能力
  templates/         # 模板文件
frontend/
  src/pages/         # 页面层（主图、详情、模板、预览、数据、设置、资源库、登录）
  src/components/    # 复用组件（含统一 AppTopBar/PageShell）
  src/mocks/         # 前端 mock 数据集中目录
  src/services/      # API 调用封装（统一通过 http.ts）
  src/types/         # 前端类型与协议定义
docs/                # 中文文档（架构、API、流程、规范）
storage/tasks/       # 任务索引（index.json）
outputs/tasks/       # 任务产物目录（按 task_id）
AGENTS.md            # 仓库开发规则手册（Codex/人工共同遵循）
```

## 4. 后端启动方式
```bash
pip install -e .
uvicorn backend.main:app --reload --port 8000
```

默认后端地址：`http://127.0.0.1:8000`，API 前缀默认 `/api`。

## 5. 前端启动方式
```bash
cd frontend
npm install
npm run dev
```

默认前端地址：`http://127.0.0.1:5173`。

## 6. 环境变量说明
后端使用 `ECOM_` 前缀环境变量（定义在 `backend/core/config.py`）：
- `ECOM_APP_NAME`：应用名称（默认 `ecom-image-agent-api`）
- `ECOM_DEBUG`：是否开启 debug（默认 `false`）
- `ECOM_API_PREFIX`：API 前缀（默认 `/api`）
- `ECOM_CORS_ORIGINS`：CORS 白名单（默认 `[*]`）
- `ECOM_STORAGE_ROOT`：索引/资产目录（默认 `storage`）
- `ECOM_OUTPUTS_ROOT`：任务产物目录（默认 `outputs/tasks`）
- `ECOM_TEMPLATE_ROOT`：模板目录（默认 `backend/templates`）

前端常用变量：
- `VITE_API_BASE_URL`：后端 API 基址（默认 `http://127.0.0.1:8000/api`）。

## 7. 当前核心 API 能力概览
- 健康检查：`GET /api/health`
- 主图任务提交：`POST /api/image/generate-main`
- 详情页生成：`POST /api/detail/generate`
- 任务列表：`GET /api/tasks`
- 任务详情：`GET /api/tasks/{task_id}`
- 主图运行时：`GET /api/tasks/{task_id}/runtime`
- 任务文件访问：`GET /api/tasks/{task_id}/files/{file_name}`
- 模板列表与预览：
  - `GET /api/templates/main-images`
  - `GET /api/templates/detail-pages`
  - `POST /api/templates/detail-pages/preview`
- 静态资产访问：`GET /api/assets/{file_name}`

详细字段与示例见 `docs/api.md`。

## 8. 当前前端页面路由
- `/login` 登录页
- `/main-images` 主图生成工作台
- `/detail-pages` 详情长图编辑页（mock 三栏联动）
- `/templates` 模板中心（mock 筛选）
- `/preview` 预览中心（mock 任务切换）
- `/tasks` 历史任务
- `/dashboard` 数据中心
- `/settings` 系统设置
- `/assets-library` 资源库

## 9. 当前主工作台页面说明
- 核心页面：`frontend/src/pages/MainImagePage.tsx`。
- 核心能力：
  - 上传白底图、参考图、背景参考图；
  - 提交主图任务；
  - 轮询 runtime 展示进度、队列位置、QC 摘要、结果卡片；
  - 结果图预览与下载；
  - 通过 localStorage 恢复最近任务。

详情见 `docs/frontend-workbench.md` 与 `docs/workflow.md`。

## 10. 文档索引
- `docs/architecture.md`：整体架构与数据流。
- `docs/api.md`：后端 API 清单、请求/响应与示例。
- `docs/frontend-workbench.md`：主图工作台页面与前端数据流。
- `docs/storage.md`：存储组织、路径规则、URL 策略。
- `docs/workflow.md`：主图任务从提交到结果展示全链路。
- `docs/development-rules.md`：开发协作与提交前检查。
- `docs/codebase-file-map.md`：代码地图与关键文件说明。

## 11. AGENTS.md 说明入口
根目录 `AGENTS.md` 是仓库级执行规范手册。后续无论是 Codex 还是人工开发，都必须遵循其中的：
- 分层职责；
- 禁止事项；
- 文档同步规则；
- 提交前检查清单。
