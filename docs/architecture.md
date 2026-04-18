# 架构说明

## 1. 总体结构
当前仓库采用前后端分离：
- `frontend/`：React + TypeScript + Vite 工作台
- `backend/`：FastAPI API 服务
- `backend/engine/`：主图/详情图生成引擎
- `alembic/`：数据库迁移脚本

当前正式后端存在两条并行主线：
- 任务执行主线：继续使用本地文件系统 + JSON 索引 + 任务目录产物
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

数据库当前尚未承载：
- 任务文件二进制
- 真实任务执行调度
- 旧 JSON 索引的完全替代
- provider 全量 usage 自动落库

## 4. 认证架构
### 4.1 登录态设计
- Access token：JWT
- Refresh token：HttpOnly cookie + 数据库哈希存储
- 密码哈希：`scrypt`
- 当前用户依赖：`get_current_user`

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

### 6.2 详情图系统
- 工作流入口：`backend/engine/workflows/detail_graph.py`
- 服务入口：`backend/services/detail_page_job_service.py`
- runtime 聚合：`backend/services/detail_runtime_service.py`

## 7. 存储结构
### 7.1 本地文件与 JSON
- 任务索引：`storage/tasks/index.json`
- 任务目录：`outputs/tasks/{task_id}/`

### 7.2 PostgreSQL
- 结构定义见 `docs/database-schema-v1.md`
- `cos_key` 当前保存任务目录内的相对路径，占位未来对象存储键
- 当前不存文件二进制
- 当前不替代现有任务文件落盘逻辑

## 8. deprecated / frozen 模块
以下模块继续保留，但不属于当前正式主线：
- `backend/api/detail.py`
- `backend/services/detail_page_service.py`
- `backend/api/templates.py`
- `backend/services/template_service.py`
- `backend/legacy/**`
