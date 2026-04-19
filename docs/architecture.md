# 架构说明

## 1. 总体结构
当前仓库采用前后端分离：
- `frontend/`：React + TypeScript + Vite 工作台
- `backend/`：FastAPI API 服务
- `backend/engine/`：主图/详情图生成引擎
- `alembic/`：数据库迁移脚本

当前正式后端存在两条并行主线：
- 任务执行主线：继续使用本地文件系统 + JSON 索引 + 任务目录产物，执行调度可选 Celery + Redis
- 元数据与用户主线：使用 PostgreSQL + SQLAlchemy Async + Alembic

## 2. FastAPI 分层
### 2.1 应用入口
- `backend/main.py`
  - 注册旧版生成路由 `/api/*`
  - 注册 v1 认证与任务路由 `/api/v1/*`
  - 统一异常处理
  - 统一 request middleware

### 2.2 API 层
- `backend/api/*.py`
  - 继续承载主图、详情图和旧任务路径
- `backend/api/v1/auth.py`
  - v1 认证 API
- `backend/api/v1/tasks.py`
  - v1 历史任务查询 API
- `backend/api/v1/storage.py`
  - v1 文件预签名上传与签名下载 API
- `backend/api/dependencies.py`
  - `get_db_session`
  - `get_auth_service`
  - `get_request_context`
  - `get_current_user`
  - `get_current_user_optional`

### 2.3 Service 层
- 生成任务服务：
  - `backend/services/main_image_service.py`
  - `backend/services/detail_page_job_service.py`
- 认证服务：
  - `backend/services/auth_service.py`
- 任务数据库兼容层：
  - `backend/services/task_db_mirror_service.py`
  - 负责把旧 JSON / 文件任务元数据镜像写入 PostgreSQL
- 文件存储服务：
  - `backend/services/storage/cos_service.py`
  - `backend/services/storage/upload_guard_service.py`
  - `backend/services/storage/storage_service.py`
  - 负责 COS 预签名上传、签名下载、文件校验和本地兼容 URL
- Celery 执行状态服务：
  - `backend/services/task_execution_state_service.py`
  - 负责 worker 外层的 running、retry、failed 状态和事件写入
- v1 任务查询服务：
  - `backend/services/task_query_service.py`
  - 负责按用户隔离读取 `tasks`、`task_events`、`task_results`
- task usage 预留写入服务：
  - `backend/services/task_usage_record_service.py`

### 2.4 Repository 层
- 旧 JSON 仓储：
  - `backend/repositories/task_repository.py`
- 数据库仓储：
  - `backend/repositories/db/*.py`
  - 包含 `users`、`refresh_tokens`、`audit_logs`、`idempotency_keys`
  - 以及 `tasks`、`task_assets`、`task_results`、`task_events`、`task_usage_records`

## 3. 数据库基础设施
### 3.1 核心文件
- `backend/db/session.py`
- `backend/db/base.py`
- `backend/db/models/`
- `alembic/env.py`
- `alembic/versions/20260418_01_initial_auth_and_task_schema.py`
- `alembic/versions/20260418_02_task_enum_alignment_for_v1_history.py`

### 3.2 当前数据库职责
数据库当前正式承载：
- 用户主数据
- refresh token 持久化
- 审计日志
- 幂等键
- 主图/详情图任务元数据镜像
- 历史任务查询
- 关键任务事件
- 结果摘要与结果文件元数据
- 私有文件签名上传 / 签名下载

数据库当前尚未承载：
- 任务文件二进制
- 任务队列本身
- 旧 JSON 索引的完全替代
- provider 全量 usage 自动落库
- COS 上传完成确认状态

### 3.3 Redis / Celery
Celery + Redis 是阶段 4 新增的可选任务调度层：
- `backend/workers/celery_app.py` 创建 Celery app
- `backend/workers/tasks/main_image_tasks.py` 执行主图任务
- `backend/workers/tasks/detail_page_tasks.py` 执行详情图任务
- `backend/workers/tasks/image_edit_tasks.py` 执行单图局部编辑任务
- Redis 默认作为 broker 和 result backend
- `ECOM_CELERY_ENABLED=false` 时继续使用旧进程内队列 fallback

Celery 只替换执行调度，不替换本地任务目录、旧 runtime 聚合和数据库任务镜像。

## 4. 认证架构
### 4.1 登录态设计
- Access token：JWT
- Refresh token：HttpOnly cookie + 数据库哈希存储
- 密码哈希：`scrypt`
- 当前用户依赖：`get_current_user`
- 前端通过 `AuthProvider` 保存 access token，并由统一 HTTP client 注入 Bearer token
- refresh cookie 依赖 CORS credentials，`ECOM_CORS_ORIGINS` 必须配置明确 origin

### 4.2 审计
当前已记录以下动作：
- `auth.register`
- `auth.login`
- `auth.logout`

写入表：`audit_logs`

## 5. 任务迁移策略
### 5.1 兼容原则
- 不改主图/详情图 workflow 核心执行逻辑
- 不移除 `storage/tasks/index.json`
- 不替换任务目录落盘结构
- 先做双写：旧链路继续跑，数据库补齐可查询元数据

### 5.2 当前双写范围
创建任务时：
- 本地：`task.json`、上传素材、JSON 索引
- 数据库：`tasks`、`task_assets`、初始 `task_events`

任务运行中 / 完成时：
- 本地：继续由旧 runtime 回写 JSON
- 数据库：同步 `tasks`、`task_events`、`task_results`

### 5.3 用户归属
- 旧生成接口支持可选 Bearer token
- 带 token：任务归属当前登录用户
- 不带 token：任务归属禁用的兼容系统用户，用于保持旧接口可用但不污染普通用户历史列表

## 6. 生成链路
### 6.1 主图系统
- 工作流入口：`backend/engine/workflows/graph.py`
- 服务入口：`backend/services/main_image_service.py`
- runtime 聚合：`backend/services/task_runtime_service.py`
- Celery task：`backend/workers/tasks/main_image_tasks.py`

### 6.2 详情图系统
- 工作流入口：`backend/engine/workflows/detail_graph.py`
- 服务入口：`backend/services/detail_page_job_service.py`
- runtime 聚合：`backend/services/detail_runtime_service.py`
- Celery task：`backend/workers/tasks/detail_page_tasks.py`

### 6.3 执行调度
- 默认模式：API 创建任务后提交旧进程内队列。
- Celery 模式：API 创建任务和数据库镜像后提交 Celery，worker 根据 `task_id` 从任务目录恢复输入并执行原 workflow。
- 两种模式共用同一套本地任务目录、runtime 聚合和数据库兼容写入。

### 6.4 单图二次编辑
- API 入口：`POST /api/v1/results/{result_id}/edits`、`GET /api/v1/results/{result_id}/edits`
- 服务入口：`backend/services/image_edit_service.py`
- 数据表：`image_edits`、`tasks(task_type=image_edit)`、`task_results(result_type=image_edit)`
- Celery task：`backend/workers/tasks/image_edit_tasks.py`
- 当前 provider 未暴露原生 inpainting，执行模式明确写入 `full_image_constrained_regeneration`
- 编辑结果以派生版本写入 `task_results.parent_result_id`

## 7. 存储结构
### 7.1 本地文件与 JSON
- 任务索引：`storage/tasks/index.json`
- 任务目录：`outputs/tasks/{task_id}/`

### 7.2 PostgreSQL
- 结构定义见 `docs/database-schema-v1.md`
- `cos_key` 在本地兼容模式保存任务目录相对路径，在 COS 模式保存对象 key
- 当前不存文件二进制
- 当前不替代现有任务文件落盘逻辑

### 7.3 腾讯云 COS
- 配置见 `backend/core/config.py` 的 `ECOM_COS_*`
- 预签名上传：`POST /api/v1/storage/presign`
- 签名下载：`GET /api/v1/files/{file_id}/download-url`
- 对象 key 规范：`users/{user_id}/tasks/{task_id}/{kind}/{filename}`
- COS 未启用时，旧本地文件接口继续可用

## 8. deprecated / frozen 模块
以下模块继续保留，但不属于当前正式主线：
- `backend/api/detail.py`
- `backend/services/detail_page_service.py`
- `backend/api/templates.py`
- `backend/services/template_service.py`
- `backend/legacy/**`
