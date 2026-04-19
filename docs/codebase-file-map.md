# 代码地图

## 1. 根目录入口
- `README.md`：项目总览与启动说明
- `AGENTS.md`：仓库级执行规范
- `backend/main.py`：FastAPI 应用入口
- `frontend/src/main.tsx`：React 应用入口
- `alembic.ini`：Alembic 配置入口
- `docker-compose.dev.yml`：本地 PostgreSQL / Redis 依赖编排
- `docs/database-schema-v1.md`：数据库 schema 事实文档
- `docs/task-migration-plan.md`：任务系统数据库迁移说明
- `docs/cos-integration.md`：腾讯云 COS 接入与兼容说明
- `docs/celery-task-architecture.md`：Celery + Redis 任务执行架构说明
- `docs/frontend-v1-pages.md`：前端登录态、受保护路由、历史任务和恢复说明
- `docs/v1-scope-freeze.md`：一期范围冻结文档

## 2. 后端 API 层
- `backend/api/image.py`：主图任务提交，支持可选当前用户归属
- `backend/api/tasks.py`：旧任务列表、摘要、runtime、文件访问
- `backend/api/detail_jobs.py`：详情图 V2 任务 API
- `backend/api/v1/auth.py`：v1 认证接口
- `backend/api/v1/tasks.py`：v1 历史任务查询接口
- `backend/api/v1/storage.py`：v1 文件预签名上传与签名下载接口
- `backend/api/dependencies.py`：FastAPI 依赖注入
- `backend/api/detail.py`：`deprecated`，旧详情页 JSON 生成接口
- `backend/api/templates.py`：`deprecated`，旧模板接口
- `backend/api/assets.py`：通用静态资产访问接口

## 3. 后端核心层
- `backend/core/config.py`：FastAPI 配置与环境变量
- `backend/core/exceptions.py`：统一业务异常
- `backend/core/security.py`：JWT、密码哈希、refresh cookie 工具
- `backend/core/request_context.py`：请求上下文抽象
- `backend/core/middleware.py`：request_id 和耗时注入
- `backend/core/response.py`：统一响应 envelope

## 4. 数据库基础设施
- `backend/db/session.py`：Async Engine / Session 管理
- `backend/db/base.py`：Declarative Base 与 metadata
- `backend/db/enums.py`：集中枚举定义
- `backend/db/types.py`：PostgreSQL / SQLite 类型适配
- `backend/db/models/user.py`：`users`
- `backend/db/models/auth.py`：`refresh_tokens` / `idempotency_keys`
- `backend/db/models/audit.py`：`audit_logs`
- `backend/db/models/task.py`：`tasks` / `task_assets` / `task_results` / `task_events` / `task_usage_records` / `image_edits`
- `alembic/env.py`：Alembic 运行环境
- `alembic/versions/20260418_01_initial_auth_and_task_schema.py`：初始 migration
- `alembic/versions/20260418_02_task_enum_alignment_for_v1_history.py`：v1 任务枚举对齐 migration
- `alembic/versions/20260418_03_image_edits.py`：单图编辑记录 migration

## 5. Service 与 Repository
### 5.1 正式链路
- `backend/services/main_image_service.py`：主图任务入口，兼容写 DB
- `backend/services/detail_page_job_service.py`：详情图 V2 任务入口，兼容写 DB
- `backend/services/task_runtime_service.py`：主图 runtime 聚合
- `backend/services/detail_runtime_service.py`：详情图 runtime 聚合
- `backend/services/auth_service.py`：注册、登录、刷新、登出、当前用户
- `backend/services/task_db_mirror_service.py`：任务数据库镜像写入
- `backend/services/task_query_service.py`：v1 历史任务查询编排
- `backend/services/task_usage_record_service.py`：task usage 数据库预留写入
- `backend/services/task_execution_state_service.py`：Celery worker 外层任务状态与事件写入
- `backend/services/image_edit_service.py`：单图编辑任务创建、查询和执行编排
- `backend/services/storage/cos_service.py`：腾讯云 COS 签名和上传封装
- `backend/services/storage/upload_guard_service.py`：上传前 MIME、大小、SHA256、文件名校验
- `backend/services/storage/storage_service.py`：v1 文件存储业务编排与所有权校验
- `backend/repositories/task_repository.py`：JSON 任务索引仓储
- `backend/repositories/db/*.py`：数据库 repository

### 5.2 已冻结旧实现
- `backend/services/detail_page_service.py`：`deprecated`
- `backend/services/template_service.py`：`deprecated`
- `backend/legacy/streamlit_app.py`：`deprecated`
- `backend/legacy/ui/**`：`deprecated`

## 6. 生成引擎
### 6.1 Workflow
- `backend/engine/workflows/graph.py`：main graph
- `backend/engine/workflows/detail_graph.py`：detail graph
- `backend/engine/workflows/nodes/`：主图节点
- `backend/engine/workflows/detail_nodes/`：详情图节点

### 6.2 Provider 与底层能力
- `backend/engine/providers/router.py`：统一 capability 路由
- `backend/engine/providers/image/banana2_image.py`：默认图片 provider
- `backend/engine/providers/llm/runapi_openai_text.py`：文本 provider
- `backend/engine/services/storage/local_storage.py`：本地任务存储与 artifact 落盘

## 7. Celery Worker
- `backend/workers/celery_app.py`：Celery app 创建与 broker / backend 配置
- `backend/workers/tasks/main_image_tasks.py`：主图异步任务入口
- `backend/workers/tasks/detail_page_tasks.py`：详情图异步任务入口
- `backend/workers/tasks/image_edit_tasks.py`：单图编辑异步任务入口

## 8. 前端与范围冻结
- `frontend/src/config/v1Scope.ts`：一期路由开关
- `frontend/src/auth/AuthProvider.tsx`：前端登录态 Provider
- `frontend/src/auth/RouteGuards.tsx`：受保护路由与公开路由守卫
- `frontend/src/hooks/useAuth.ts`：认证 Hook
- `frontend/src/pages/LoginPage.tsx`：真实登录页
- `frontend/src/pages/RegisterPage.tsx`：真实注册页
- `frontend/src/pages/MainImagePage.tsx`：主图工作台
- `frontend/src/pages/DetailPageGeneratorPage.tsx`：详情图工作台
- `frontend/src/pages/TasksPage.tsx`：v1 历史任务页
- `frontend/src/services/authApi.ts`：认证 API service
- `frontend/src/services/authToken.ts`：access token 存储工具
- `frontend/src/services/apiError.ts`：前端 API 错误信息提取工具
- `frontend/src/services/storageApi.ts`：COS 直传和签名下载前端 service
- `frontend/src/services/imageEditApi.ts`：图片编辑创建与历史查询 service
- `frontend/src/components/layout/AppTopBar.tsx`：顶部导航
- `frontend/src/pages/DashboardPage.tsx` 等一期外页面：`deprecated`

## 9. 建议阅读顺序
1. `docs/v1-scope-freeze.md`
2. `docs/task-migration-plan.md`
3. `docs/cos-integration.md`
4. `docs/celery-task-architecture.md`
5. `docs/frontend-v1-pages.md`
6. `docs/image-edit-v1.md`
7. `docs/architecture.md`
8. `docs/database-schema-v1.md`
9. `docs/api.md`
10. `docs/storage.md`
11. `docs/frontend-workbench.md`
