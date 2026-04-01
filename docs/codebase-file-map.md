# 代码地图（当前）

## 主要入口
- `backend/main.py`：FastAPI 主入口。
- `frontend/src/main.tsx`：React 主入口，`/` 默认重定向到 `/main-images`。
- `backend/legacy/streamlit_app.py`：历史 Streamlit 调试入口，当前不作为主 UI。

## 后端关键文件
- `backend/api/image.py`：主图提交接口，创建任务后立即返回 `task_id`，后台继续执行 workflow。
- `backend/api/tasks.py`：任务列表、任务摘要、工作台 runtime 查询与任务文件访问接口。
- `backend/engine/`：主图 LangGraph workflow、provider、渲染与存储能力。
- `backend/services/main_image_service.py`：主图任务准备与后台执行服务。
- `backend/services/task_queue_service.py`：进程内单 worker 主图队列，提供最小队列观测快照。
- `backend/services/task_runtime_service.py`：从 `task.json`、`prompt_plan_v2.json` 和任务输出目录组装工作台运行时数据。
- `backend/services/detail_page_service.py`：详情页结构化生成服务。
- `backend/repositories/task_repository.py`：任务索引 JSON 持久化与运行时状态同步。
- `backend/templates/detail_pages/*.json`：详情页模板资源。

## 前端关键文件
- `frontend/src/pages/MainImagePage.tsx`：主图生成工作台页，负责真实任务提交、轮询 runtime、结果区展示和大图预览。
- `frontend/src/pages/MainImagePage.css`：主图工作台布局样式，包含结果图区占位态和真实结果卡片样式。
- `frontend/src/pages/TasksPage.tsx`：任务记录页，支持恢复任务到工作台和下载结果 ZIP。
- `frontend/src/pages/TasksPage.css`：任务记录页样式。
- `frontend/src/services/mainImageApi.ts`：主图任务提交 API 封装。
- `frontend/src/services/taskApi.ts`：任务摘要和 runtime API 封装。
- `frontend/src/types/api.ts`：前后端共享的前端 contract 类型。
- `frontend/src/components/Layout.tsx`：路由壳层。
- `frontend/src/pages/DetailPageGeneratorPage.tsx`：详情页生成页面。
- `frontend/src/services/http.ts`：统一请求封装。
- `frontend/src/hooks/useTasks.ts`：任务列表查询 hook。

## 设计与规范文档
- `docs/api.md`：接口清单与运行时接口说明。
- `docs/workflow.md`：工作流与主图工作台真实数据流说明。
- `docs/contracts/task_runtime.md`：主图工作台 runtime 返回结构说明。
- `docs/design/page-layout-rules.md`：主图工作台页面级布局规则。
- `docs/design/component-rules.md`：上传卡片、结果卡片、预览弹层等组件规则。
- `docs/design/anti-patterns.md`：禁止事项与常见反模式清单。
