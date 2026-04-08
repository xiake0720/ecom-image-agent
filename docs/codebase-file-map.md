# 代码地图

## 1. 根目录入口
- [`README.md`](/D:/python/ecom-image-agent/README.md)：项目总览与启动方式
- [`AGENTS.md`](/D:/python/ecom-image-agent/AGENTS.md)：仓库执行规范
- [`backend/main.py`](/D:/python/ecom-image-agent/backend/main.py)：FastAPI 应用入口
- [`frontend/src/main.tsx`](/D:/python/ecom-image-agent/frontend/src/main.tsx)：React 应用入口

## 2. 后端 API 层
- [`backend/api/image.py`](/D:/python/ecom-image-agent/backend/api/image.py)：主图任务提交
- [`backend/api/tasks.py`](/D:/python/ecom-image-agent/backend/api/tasks.py)：主图任务列表、runtime、文件访问
- [`backend/api/detail_jobs.py`](/D:/python/ecom-image-agent/backend/api/detail_jobs.py)：详情图任务 API
- [`backend/api/detail.py`](/D:/python/ecom-image-agent/backend/api/detail.py)：旧详情页 JSON 生成接口
- [`backend/api/templates.py`](/D:/python/ecom-image-agent/backend/api/templates.py)：模板列表与详情页预览

## 3. 后端服务层

### 3.1 主图
- [`backend/services/main_image_service.py`](/D:/python/ecom-image-agent/backend/services/main_image_service.py)：主图任务创建与 workflow 执行入口
- [`backend/services/task_queue_service.py`](/D:/python/ecom-image-agent/backend/services/task_queue_service.py)：主图进程内队列
- [`backend/services/task_runtime_service.py`](/D:/python/ecom-image-agent/backend/services/task_runtime_service.py)：主图 runtime 聚合

### 3.2 详情图
- [`backend/services/detail_page_job_service.py`](/D:/python/ecom-image-agent/backend/services/detail_page_job_service.py)：详情图任务创建、素材落盘、detail graph 执行入口
- [`backend/services/detail_runtime_service.py`](/D:/python/ecom-image-agent/backend/services/detail_runtime_service.py)：详情图 runtime 聚合
- [`backend/services/detail_planner_service.py`](/D:/python/ecom-image-agent/backend/services/detail_planner_service.py)：导演 Agent 的 plan 生成服务
- [`backend/services/detail_copy_service.py`](/D:/python/ecom-image-agent/backend/services/detail_copy_service.py)：导演 Agent 的 copy 生成服务
- [`backend/services/detail_prompt_service.py`](/D:/python/ecom-image-agent/backend/services/detail_prompt_service.py)：导演 Agent 的 render prompt 生成服务
- [`backend/services/detail_render_service.py`](/D:/python/ecom-image-agent/backend/services/detail_render_service.py)：详情图 provider 渲染、render report 与 ZIP
- [`backend/services/detail_page_service.py`](/D:/python/ecom-image-agent/backend/services/detail_page_service.py)：旧详情页模块化预览服务
- [`backend/services/template_service.py`](/D:/python/ecom-image-agent/backend/services/template_service.py)：模板读取

## 4. schema 与仓储
- [`backend/schemas/task.py`](/D:/python/ecom-image-agent/backend/schemas/task.py)：主图任务 schema
- [`backend/schemas/detail.py`](/D:/python/ecom-image-agent/backend/schemas/detail.py)：详情图 plan/copy/prompt/render/qc/runtime schema
- [`backend/repositories/task_repository.py`](/D:/python/ecom-image-agent/backend/repositories/task_repository.py)：任务索引 `storage/tasks/index.json` 的读写

## 5. engine 核心

### 5.1 workflow
- [`backend/engine/workflows/graph.py`](/D:/python/ecom-image-agent/backend/engine/workflows/graph.py)：main graph
- [`backend/engine/workflows/state.py`](/D:/python/ecom-image-agent/backend/engine/workflows/state.py)：main graph state
- [`backend/engine/workflows/detail_graph.py`](/D:/python/ecom-image-agent/backend/engine/workflows/detail_graph.py)：detail graph
- [`backend/engine/workflows/detail_state.py`](/D:/python/ecom-image-agent/backend/engine/workflows/detail_state.py)：detail graph state
- [`backend/engine/workflows/nodes/`](/D:/python/ecom-image-agent/backend/engine/workflows/nodes)：主图节点
- [`backend/engine/workflows/detail_nodes/`](/D:/python/ecom-image-agent/backend/engine/workflows/detail_nodes)：详情图节点

### 5.2 provider/router
- [`backend/engine/providers/router.py`](/D:/python/ecom-image-agent/backend/engine/providers/router.py)：统一 capability 路由
- [`backend/engine/providers/image/banana2_image.py`](/D:/python/ecom-image-agent/backend/engine/providers/image/banana2_image.py)：默认图片 provider，优先走 Google 官方 `google.genai` SDK，缺失 Google Key 时回退到 RunAPI
- [`backend/engine/providers/image/gemini_image.py`](/D:/python/ecom-image-agent/backend/engine/providers/image/gemini_image.py)：mock Banana2 图片 provider
- [`backend/engine/providers/image/runapi_gemini31_image.py`](/D:/python/ecom-image-agent/backend/engine/providers/image/runapi_gemini31_image.py)：保留的旧图片 provider
- [`backend/engine/providers/llm/gemini_text.py`](/D:/python/ecom-image-agent/backend/engine/providers/llm/gemini_text.py)：mock text provider
- [`backend/engine/providers/llm/runapi_openai_text.py`](/D:/python/ecom-image-agent/backend/engine/providers/llm/runapi_openai_text.py)：real text provider

### 5.3 底层服务
- [`backend/engine/services/storage/local_storage.py`](/D:/python/ecom-image-agent/backend/engine/services/storage/local_storage.py)：本地存储与 JSON artifact 落盘
- [`backend/engine/core/config.py`](/D:/python/ecom-image-agent/backend/engine/core/config.py)：provider/router、尺寸与模型配置
- [`backend/engine/core/paths.py`](/D:/python/ecom-image-agent/backend/engine/core/paths.py)：任务目录路径工具

## 6. 模板与 mock 资源
- [`backend/templates/detail_pages/tea_tmall_premium_v1.json`](/D:/python/ecom-image-agent/backend/templates/detail_pages/tea_tmall_premium_v1.json)：茶叶天猫高端 detail 模板
- [`assets/mock/banana2/`](/D:/python/ecom-image-agent/assets/mock/banana2)：mock Banana2 详情图样张

## 7. 前端页面
- [`frontend/src/pages/MainImagePage.tsx`](/D:/python/ecom-image-agent/frontend/src/pages/MainImagePage.tsx)：主图工作台
- [`frontend/src/pages/DetailPageGeneratorPage.tsx`](/D:/python/ecom-image-agent/frontend/src/pages/DetailPageGeneratorPage.tsx)：详情图正式工作台
- [`frontend/src/pages/DetailPageGeneratorPage.css`](/D:/python/ecom-image-agent/frontend/src/pages/DetailPageGeneratorPage.css)：详情图工作台专属样式

## 8. 前端 detail 组件
- [`frontend/src/components/detail/DetailTaskSourcePicker.tsx`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailTaskSourcePicker.tsx)：主图任务来源选择
- [`frontend/src/components/detail/DetailMainResultGallery.tsx`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailMainResultGallery.tsx)：主图结果图卡多选
- [`frontend/src/components/detail/DetailAssetUploader.tsx`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailAssetUploader.tsx)：详情图素材上传器
- [`frontend/src/components/detail/DetailProductForm.tsx`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailProductForm.tsx)：商品信息表单
- [`frontend/src/components/detail/DetailGoalForm.tsx`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailGoalForm.tsx)：目标与额外要求表单
- [`frontend/src/components/detail/DetailPlanPreview.tsx`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailPlanPreview.tsx)：规划预览
- [`frontend/src/components/detail/DetailCopyPreview.tsx`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailCopyPreview.tsx)：文案预览
- [`frontend/src/components/detail/DetailPromptPreview.tsx`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailPromptPreview.tsx)：Prompt 摘要预览
- [`frontend/src/components/detail/DetailResultGallery.tsx`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailResultGallery.tsx)：结果图画廊
- [`frontend/src/components/detail/DetailRuntimeSidebar.tsx`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailRuntimeSidebar.tsx)：运行时侧栏

## 9. 前端 API 与类型
- [`frontend/src/services/detailPageApi.ts`](/D:/python/ecom-image-agent/frontend/src/services/detailPageApi.ts)：详情图 API 封装
- [`frontend/src/types/detail.ts`](/D:/python/ecom-image-agent/frontend/src/types/detail.ts)：详情图前端 contract
- [`frontend/src/services/taskApi.ts`](/D:/python/ecom-image-agent/frontend/src/services/taskApi.ts)：主图任务 API
- [`frontend/src/types/api.ts`](/D:/python/ecom-image-agent/frontend/src/types/api.ts)：主图任务类型

## 10. 文档建议阅读顺序
1. [`docs/architecture.md`](/D:/python/ecom-image-agent/docs/architecture.md)
2. [`docs/workflow.md`](/D:/python/ecom-image-agent/docs/workflow.md)
3. [`docs/api.md`](/D:/python/ecom-image-agent/docs/api.md)
4. [`docs/frontend-workbench.md`](/D:/python/ecom-image-agent/docs/frontend-workbench.md)
5. [`docs/storage.md`](/D:/python/ecom-image-agent/docs/storage.md)
