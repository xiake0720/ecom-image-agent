# 代码地图（面向新接手开发）

## 1. 根目录关键入口
- `AGENTS.md`：仓库执行规范（Codex/人工均需遵守）。
- `README.md`：项目启动与总览文档。
- `backend/main.py`：FastAPI 应用入口。
- `frontend/src/main.tsx`：React 应用入口。

## 2. 后端目录说明

### 2.1 `backend/api/`
- `health.py`：健康检查接口。
- `image.py`：主图任务提交接口。
- `detail.py`：详情页生成接口。
- `tasks.py`：任务列表、任务详情、runtime、任务文件访问。
- `templates.py`：模板列表与详情页预览接口。
- `assets.py`：静态资产访问。

### 2.2 `backend/services/`
- `main_image_service.py`：主图任务创建、落盘、队列执行入口。
- `task_queue_service.py`：进程内队列与 worker。
- `task_runtime_service.py`：工作台 runtime 聚合。
- `detail_page_service.py`：详情页模块化 JSON 生成。
- `template_service.py`：模板读取服务。

### 2.3 `backend/schemas/`
- `task.py`：主图提交、任务摘要、runtime、详情页生成等 schema。

### 2.4 `backend/repositories/`
- `task_repository.py`：任务索引 `storage/tasks/index.json` 的读写与补全。

### 2.5 `backend/engine/`
- 主图生成引擎目录（workflow、provider、domain、渲染、存储）。
- `workflows/graph.py` 为主图 workflow 编排入口。

### 2.6 `backend/templates/`
- `detail_pages/*.json`：详情页模板资源。

## 3. 前端目录说明

### 3.1 `frontend/src/pages/`
- `MainImagePage.tsx`：主图提交/轮询/结果展示（接入统一壳层）。
- `DetailPageGeneratorPage.tsx`：详情长图编辑页（左中右三栏 + mock 预览联动）。
- `TemplatesPage.tsx`：模板中心（筛选 + 模板卡片）。
- `PreviewPage.tsx`：预览中心（任务分组 + 大图预览）。
- `AssetsLibraryPage.tsx`：资源库页（分类/筛选/卡片网格）。
- `DashboardPage.tsx`：数据中心（统计卡片 + 趋势图 + 榜单）。
- `SettingsPage.tsx`：系统设置（左菜单 + 模型路由表单）。
- `TasksPage.tsx`：历史任务。
- `LoginPage.tsx`：登录页。

### 3.2 `frontend/src/services/`
- `http.ts`：统一 axios 实例与 URL 解析。
- `mainImageApi.ts`：主图提交 API。
- `taskApi.ts`：任务查询与 runtime 查询 API。

### 3.3 `frontend/src/components/`
- `Layout.tsx`：路由容器。
- `layout/AppTopBar.tsx`：统一顶部任务栏。
- `layout/PageShell.tsx`：统一页面外壳。
- `common/PageHeader.tsx`、`common/SectionCard.tsx`：通用标题/卡片组件。

### 3.4 `frontend/src/mocks/`
- `mainImageMock.ts`、`detailEditorMock.ts`、`templateCenterMock.ts`、`previewCenterMock.ts`、`settingsMock.ts`、`dashboardMock.ts`、`assetsLibraryMock.ts`、`sharedMock.ts`：页面 mock 数据集中管理。

### 3.5 `frontend/src/types/`
- `api.ts`：前端 API contract 类型。

## 4. 数据与产物目录
- `storage/tasks/index.json`：任务摘要索引。
- `outputs/tasks/{task_id}/`：任务全量产物（输入、生成、导出、中间 JSON）。

## 5. 文档目录建议阅读顺序
1. `docs/architecture.md`
2. `docs/workflow.md`
3. `docs/api.md`
4. `docs/frontend-workbench.md`
5. `docs/storage.md`
6. `docs/development-rules.md`


## 详情图 V2 新增文件
- `backend/api/detail_jobs.py`：详情图任务接口。
- `backend/schemas/detail.py`：详情图专属 schema。
- `backend/services/detail_page_job_service.py`：详情图任务创建/调度/落盘。
- `backend/services/detail_runtime_service.py`：详情图 runtime 聚合。
- `backend/services/detail_planner_service.py`：规划生成。
- `backend/services/detail_copy_service.py`：结构化文案生成。
- `backend/services/detail_prompt_service.py`：prompt 计划生成。
- `backend/services/detail_render_service.py`：V1 详情图渲染与 ZIP。
- `frontend/src/services/detailPageApi.ts`：详情图前端 API 封装。
- `frontend/src/types/detail.ts`：详情图前端类型。
- `backend/templates/detail_pages/tea_tmall_premium_v1.json`：茶叶天猫高端模板。
