# 代码地图

## 1. 根目录入口
- [`README.md`](/D:/python/ecom-image-agent/README.md)：项目总览与启动说明
- [`AGENTS.md`](/D:/python/ecom-image-agent/AGENTS.md)：仓库级执行规范
- [`backend/main.py`](/D:/python/ecom-image-agent/backend/main.py)：FastAPI 应用入口
- [`frontend/src/main.tsx`](/D:/python/ecom-image-agent/frontend/src/main.tsx)：React 应用入口
- [`alembic.ini`](/D:/python/ecom-image-agent/alembic.ini)：Alembic 配置入口
- [`docs/database-schema-v1.md`](/D:/python/ecom-image-agent/docs/database-schema-v1.md)：数据库 schema 事实文档
- [`docs/v1-scope-freeze.md`](/D:/python/ecom-image-agent/docs/v1-scope-freeze.md)：一期范围冻结文档

## 2. 后端 API 层
- [`backend/api/image.py`](/D:/python/ecom-image-agent/backend/api/image.py)：主图任务提交
- [`backend/api/tasks.py`](/D:/python/ecom-image-agent/backend/api/tasks.py)：任务列表、摘要、runtime、文件访问
- [`backend/api/detail_jobs.py`](/D:/python/ecom-image-agent/backend/api/detail_jobs.py)：详情图 V2 任务 API
- [`backend/api/v1/auth.py`](/D:/python/ecom-image-agent/backend/api/v1/auth.py)：v1 认证接口
- [`backend/api/dependencies.py`](/D:/python/ecom-image-agent/backend/api/dependencies.py)：FastAPI 依赖注入
- [`backend/api/detail.py`](/D:/python/ecom-image-agent/backend/api/detail.py)：`deprecated`，旧详情页 JSON 生成接口
- [`backend/api/templates.py`](/D:/python/ecom-image-agent/backend/api/templates.py)：`deprecated`，旧模板接口
- [`backend/api/assets.py`](/D:/python/ecom-image-agent/backend/api/assets.py)：通用静态资产访问接口

## 3. 后端核心层
- [`backend/core/config.py`](/D:/python/ecom-image-agent/backend/core/config.py)：FastAPI 配置与环境变量
- [`backend/core/exceptions.py`](/D:/python/ecom-image-agent/backend/core/exceptions.py)：统一业务异常
- [`backend/core/security.py`](/D:/python/ecom-image-agent/backend/core/security.py)：JWT、密码哈希、refresh cookie 工具
- [`backend/core/request_context.py`](/D:/python/ecom-image-agent/backend/core/request_context.py)：请求上下文抽象
- [`backend/core/middleware.py`](/D:/python/ecom-image-agent/backend/core/middleware.py)：request_id 和耗时注入
- [`backend/core/response.py`](/D:/python/ecom-image-agent/backend/core/response.py)：统一响应 envelope

## 4. 数据库基础设施
- [`backend/db/session.py`](/D:/python/ecom-image-agent/backend/db/session.py)：Async Engine / Session 管理
- [`backend/db/base.py`](/D:/python/ecom-image-agent/backend/db/base.py)：Declarative Base 与 metadata
- [`backend/db/enums.py`](/D:/python/ecom-image-agent/backend/db/enums.py)：集中枚举定义
- [`backend/db/types.py`](/D:/python/ecom-image-agent/backend/db/types.py)：PostgreSQL / SQLite 类型适配
- [`backend/db/models/user.py`](/D:/python/ecom-image-agent/backend/db/models/user.py)：`users`
- [`backend/db/models/auth.py`](/D:/python/ecom-image-agent/backend/db/models/auth.py)：`refresh_tokens` / `idempotency_keys`
- [`backend/db/models/audit.py`](/D:/python/ecom-image-agent/backend/db/models/audit.py)：`audit_logs`
- [`backend/db/models/task.py`](/D:/python/ecom-image-agent/backend/db/models/task.py)：阶段 2 任务域表
- [`alembic/env.py`](/D:/python/ecom-image-agent/alembic/env.py)：Alembic 运行环境
- [`alembic/versions/20260418_01_initial_auth_and_task_schema.py`](/D:/python/ecom-image-agent/alembic/versions/20260418_01_initial_auth_and_task_schema.py)：初始 migration

## 5. Service 与 Repository
### 5.1 正式链路
- [`backend/services/main_image_service.py`](/D:/python/ecom-image-agent/backend/services/main_image_service.py)：主图任务入口
- [`backend/services/detail_page_job_service.py`](/D:/python/ecom-image-agent/backend/services/detail_page_job_service.py)：详情图 V2 任务入口
- [`backend/services/task_runtime_service.py`](/D:/python/ecom-image-agent/backend/services/task_runtime_service.py)：主图 runtime 聚合
- [`backend/services/detail_runtime_service.py`](/D:/python/ecom-image-agent/backend/services/detail_runtime_service.py)：详情图 runtime 聚合
- [`backend/services/auth_service.py`](/D:/python/ecom-image-agent/backend/services/auth_service.py)：注册、登录、刷新、登出、当前用户
- [`backend/repositories/task_repository.py`](/D:/python/ecom-image-agent/backend/repositories/task_repository.py)：JSON 任务索引仓储
- `backend/repositories/db/*.py`：数据库 repository 骨架与认证仓储

### 5.2 已冻结旧实现
- [`backend/services/detail_page_service.py`](/D:/python/ecom-image-agent/backend/services/detail_page_service.py)：`deprecated`
- [`backend/services/template_service.py`](/D:/python/ecom-image-agent/backend/services/template_service.py)：`deprecated`
- [`backend/legacy/streamlit_app.py`](/D:/python/ecom-image-agent/backend/legacy/streamlit_app.py)：`deprecated`
- `backend/legacy/ui/**`：`deprecated`

## 6. 生成引擎
### 6.1 Workflow
- [`backend/engine/workflows/graph.py`](/D:/python/ecom-image-agent/backend/engine/workflows/graph.py)：main graph
- [`backend/engine/workflows/detail_graph.py`](/D:/python/ecom-image-agent/backend/engine/workflows/detail_graph.py)：detail graph
- [`backend/engine/workflows/nodes/`](/D:/python/ecom-image-agent/backend/engine/workflows/nodes)：主图节点
- [`backend/engine/workflows/detail_nodes/`](/D:/python/ecom-image-agent/backend/engine/workflows/detail_nodes)：详情图节点

### 6.2 Provider 与底层能力
- [`backend/engine/providers/router.py`](/D:/python/ecom-image-agent/backend/engine/providers/router.py)：统一 capability 路由
- [`backend/engine/providers/image/banana2_image.py`](/D:/python/ecom-image-agent/backend/engine/providers/image/banana2_image.py)：默认图片 provider
- [`backend/engine/providers/llm/runapi_openai_text.py`](/D:/python/ecom-image-agent/backend/engine/providers/llm/runapi_openai_text.py)：文本 provider
- [`backend/engine/services/storage/local_storage.py`](/D:/python/ecom-image-agent/backend/engine/services/storage/local_storage.py)：本地任务存储与 artifact 落盘

## 7. 前端与范围冻结
- [`frontend/src/config/v1Scope.ts`](/D:/python/ecom-image-agent/frontend/src/config/v1Scope.ts)：一期路由开关
- [`frontend/src/pages/LoginPage.tsx`](/D:/python/ecom-image-agent/frontend/src/pages/LoginPage.tsx)：登录页壳层
- [`frontend/src/pages/RegisterPage.tsx`](/D:/python/ecom-image-agent/frontend/src/pages/RegisterPage.tsx)：注册页壳层
- [`frontend/src/pages/MainImagePage.tsx`](/D:/python/ecom-image-agent/frontend/src/pages/MainImagePage.tsx)：主图工作台
- [`frontend/src/pages/DetailPageGeneratorPage.tsx`](/D:/python/ecom-image-agent/frontend/src/pages/DetailPageGeneratorPage.tsx)：详情图工作台
- [`frontend/src/pages/TasksPage.tsx`](/D:/python/ecom-image-agent/frontend/src/pages/TasksPage.tsx)：历史任务页
- [`frontend/src/components/layout/AppTopBar.tsx`](/D:/python/ecom-image-agent/frontend/src/components/layout/AppTopBar.tsx)：顶部导航
- `frontend/src/pages/DashboardPage.tsx` 等一期外页面：`deprecated`

## 8. 建议阅读顺序
1. [`docs/v1-scope-freeze.md`](/D:/python/ecom-image-agent/docs/v1-scope-freeze.md)
2. [`docs/architecture.md`](/D:/python/ecom-image-agent/docs/architecture.md)
3. [`docs/database-schema-v1.md`](/D:/python/ecom-image-agent/docs/database-schema-v1.md)
4. [`docs/api.md`](/D:/python/ecom-image-agent/docs/api.md)
5. [`docs/storage.md`](/D:/python/ecom-image-agent/docs/storage.md)
6. [`docs/frontend-workbench.md`](/D:/python/ecom-image-agent/docs/frontend-workbench.md)
