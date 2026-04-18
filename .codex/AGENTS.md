# AGENTS.md

## 1. 项目定位

### 1.1 项目是什么
- 本项目是一个“电商图片生产工作台”仓库，当前采用 **FastAPI 后端 + React 前端** 的前后端分离架构。
- 当前目标是：本地可运行、主链路可观测、任务可追溯、文档与实现一致。
- 当前阶段不宣称生产可用，不允许在文档中做超实现承诺。

### 1.2 当前正式技术架构
- 后端入口：`backend/main.py`（FastAPI）。
- 前端入口：`frontend/src/main.tsx`（React + TypeScript + Vite）。
- 主图生成引擎：`backend/engine/`（LangGraph 工作流 + provider 路由 + 渲染与落盘）。
- 任务索引：`storage/tasks/index.json`。
- 任务产物目录：`outputs/tasks/{task_id}/`。

### 1.3 当前主页面/主流程
- 当前核心页面：`frontend/src/pages/MainImagePage.tsx`。
- 当前核心流程：
  1. 前端提交 `POST /api/image/generate-main`；
  2. 后端创建任务并入进程内队列；
  3. worker 串行执行主图 workflow；
  4. 前端轮询 `GET /api/tasks/{task_id}/runtime` 展示进度与结果；
  5. 前端通过 `GET /api/tasks/{task_id}/files/{file_name}` 预览/下载产物。

### 1.4 前后端目录职责
- `backend/api/`：仅路由层（参数接入、调用 service、返回统一响应）。
- `backend/services/`：后端业务编排层（任务准备、详情页组装、runtime 聚合等）。
- `backend/schemas/`：HTTP 入参与出参 schema。
- `backend/repositories/`：任务索引读写。
- `backend/storage/`：存储抽象与实现。
- `backend/engine/`：主图工作流、节点、domain contract、provider 与渲染能力。
- `frontend/src/pages/`：页面级容器与页面状态。
- `frontend/src/components/`：可复用 UI 组件。
- `frontend/src/services/`：统一 API 调用层。
- `frontend/src/types/`：前端 contract 类型。
- `docs/`：项目事实文档与规范文档。

---

## 2. 开发原则
- **最小改动优先**：优先在现有结构上补齐，不做无关重构。
- **复用优先**：已有 service / schema / 组件可复用时，禁止重复造轮子。
- **不推翻既有模块**：除非有明确任务要求，不得擅自替换主链路。
- **接口、页面、文档同步**：代码改动必须同步更新对应文档。
- **代码与文档一致**：若代码与文档冲突，以代码真实实现为准修正文档。

---

## 3. Python / FastAPI 规范

### 3.1 route 层职责（`backend/api/`）
- 只处理：请求接入、参数校验、调用单一 service、返回统一 envelope。
- 禁止在 route 层实现复杂业务逻辑、文件系统编排或 provider 调用。

### 3.2 service 层职责（`backend/services/`）
- 负责业务流程编排与跨模块组合。
- 调用 repository / storage / engine 能力。
- 新增业务逻辑优先沉淀在 service 层，不下沉到 route。

### 3.3 schema 层职责（`backend/schemas/`）
- 一切 API 入参和出参结构先定义 schema，再在 route/service 使用。
- 禁止用裸 `dict` 在多层间传递关键业务字段。

### 3.4 storage / repository 职责
- `backend/repositories/` 负责索引读写（如 `storage/tasks/index.json`）。
- `backend/storage/` 与 `backend/engine/services/storage/` 负责文件落盘与路径管理。
- 禁止在 route 层直接拼路径并落盘。

### 3.5 类型标注要求
- 新增/修改 Python 函数必须补充类型标注。
- 公共函数返回值必须显式标注，避免 `Any` 污染。

### 3.6 中文注释要求
- 核心模块、核心类、核心函数必须有中文 docstring。
- 复杂逻辑必须解释“为什么这样做”，禁止低价值注释。

### 3.7 错误处理要求
- 业务错误使用 `AppException`，由全局异常处理统一出参。
- 禁止直接把 Python 原始异常信息返回给前端。

### 3.8 配置与环境变量要求
- 所有运行参数统一进入 `backend/core/config.py`（`ECOM_` 前缀）。
- 禁止新增“仅写在代码里”的隐式配置。
- 新增配置项必须同步更新 README 与 `docs/development-rules.md`。

---

## 4. React / 前端规范

### 4.1 分层职责
- 页面层（`pages/`）：页面布局、状态组合、交互编排。
- 组件层（`components/`）：可复用视图单元。
- 服务层（`services/`）：API 调用与请求封装。
- 样式层（`*.css`）：页面或组件样式，不在业务代码中堆积内联样式。

### 4.2 数据与 API 约束
- 禁止在页面中长期保留假数据；临时 mock 必须带明确清理计划。
- 所有 API 调用统一走 `frontend/src/services/`，禁止页面直连 axios/fetch。
- 统一使用 `frontend/src/services/http.ts` 作为 HTTP 基座。

### 4.3 组件复用原则
- 上传、进度、结果卡片、预览弹层等交互，优先复用既有组件/样式约定。
- 同类功能不得出现多套交互语义冲突的实现。

### 4.4 中文注释与 UI 一致性
- 复杂页面状态与交互分支需有中文注释。
- 新 UI 必须遵循现有工作台风格，不允许局部“另起一套设计语言”。

---

## 5. 文档同步规则（强制）

### 5.1 改接口时必须同步
- `docs/api.md`
- 涉及流程变更时同步 `docs/workflow.md`
- 涉及 schema 变更时同步 `docs/contracts/*`（如适用）

### 5.2 改页面时必须同步
- `docs/frontend-workbench.md`（主图工作台）或对应页面文档
- `docs/workflow.md`（若影响任务状态、轮询、预览/下载行为）

### 5.3 改目录职责时必须同步
- `docs/architecture.md`
- `docs/codebase-file-map.md`
- `README.md` 的目录结构章节

### 5.4 改存储方案时必须同步
- `docs/storage.md`
- `docs/architecture.md`（数据流与存储位置）
- `docs/api.md`（若影响 URL/返回字段）

### 5.5 改开发规范时必须同步
- `docs/development-rules.md`
- 本文件 `AGENTS.md`

---

## 6. 禁止事项
- 禁止文档长期过期、与实现不一致。
- 禁止硬编码假数据长期留在正式页面。
- 禁止实验代码混入正式目录且无说明。
- 禁止前后端协议变更但不更新文档与类型。
- 禁止新增配置项但不说明用途、默认值与生效方式。
- 禁止随意破坏统一 UI 风格。

---

## 7. 提交前检查清单（必须执行）
- 是否变更了 API、schema、状态字段、任务落盘结构？
- 是否变更了页面行为、轮询逻辑、预览/下载行为？
- 是否变更了目录职责、配置项、环境变量？
- 是否同步更新 `README.md`、`docs/codebase-file-map.md` 和受影响文档？
- 若判断“无需更新文档”，必须在总结中明确说明原因。
