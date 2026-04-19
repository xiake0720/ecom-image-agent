# 存储方案说明

## 1. 当前存储分层
当前仓库使用两套并行存储：
- 本地文件系统 + JSON：继续承载任务执行真源、任务目录产物和旧 runtime 聚合
- PostgreSQL：承载用户体系、认证、安全审计，以及任务元数据镜像
- 腾讯云 COS：在 `ECOM_COS_ENABLED=true` 时承载正式图片对象存储
- Redis：在 `ECOM_CELERY_ENABLED=true` 时作为 Celery broker / result backend，不保存任务产物

## 2. 本地文件存储
### 2.1 任务索引
- `storage/tasks/index.json`
- 由 `backend/repositories/task_repository.py` 负责读写

### 2.2 任务目录
`outputs/tasks/{task_id}/` 常见内容：
- `task.json`
- `inputs/`
- `generated/`
- `final/`
- `exports/`
- `prompt_plan_v2.json`
- `qc_report.json`
- `usage/`

### 2.3 文件访问
- `GET /api/tasks/{task_id}/files/{file_name}`
- `GET /api/detail/jobs/{task_id}/files/{file_name}`

后端会做任务目录越界校验，禁止访问任务目录之外的文件。

Celery 模式下，API 进程和 worker 必须共享同一份 `outputs/tasks/` 与 `storage/tasks/`。worker 只通过 `task_id` 恢复任务输入，不从 Redis 读取文件内容。

## 3. PostgreSQL 存储
### 3.1 当前正式使用的表
- `users`
- `refresh_tokens`
- `audit_logs`
- `idempotency_keys`
- `tasks`
- `task_assets`
- `task_results`
- `task_events`
- `task_usage_records`

### 3.2 当前接入方式
- 认证链路直接读写数据库
- 主图 / 详情图任务创建时做兼容双写
- 任务运行态通过兼容层把本地 JSON / 文件信息镜像到：
  - `tasks`
  - `task_events`
  - `task_results`
- `task_usage_records` 当前只提供预留写入服务，尚未接全量 provider 自动落库

### 3.3 关键设计约束
- 不把文件二进制写入数据库
- 不把强关系字段偷放进 JSONB
- 所有任务相关表都带 `user_id`
- `updated_at` 由数据库触发器统一维护
- `cos_key` 在本地兼容模式保存任务目录相对路径，在 COS 模式保存对象 key

## 4. 腾讯云 COS
### 4.1 启用条件
必须同时满足：
- `ECOM_COS_ENABLED=true`
- `ECOM_COS_SECRET_ID` 不为空
- `ECOM_COS_SECRET_KEY` 不为空
- `ECOM_COS_REGION` 不为空
- `ECOM_COS_BUCKET` 不为空

### 4.2 对象 key
统一格式：
```text
users/{user_id}/tasks/{task_id}/{kind}/{filename}
```

当前 `kind` 常用：
- `inputs`
- `results`

### 4.3 上传与下载
- 上传签名 API：`POST /api/v1/storage/presign`
- 下载签名 API：`GET /api/v1/files/{file_id}/download-url`
- 前端直传 service：`frontend/src/services/storageApi.ts`
- 后端不会把 COS Secret 下发给前端
- 下载前必须校验 `task_assets` 或 `task_results` 的 `user_id`

### 4.4 兼容写入
COS 启用时：
- 主图 / 详情图输入素材会在创建任务时同步上传到 COS
- 主图 / 详情图结果图会在 runtime 同步时上传到 COS
- `task_results.render_meta.local_relative_path` 保留本地相对路径，便于本地兼容预览

COS 未启用时：
- 旧本地任务目录和文件接口继续作为正式开发模式
- 不要求本地开发者配置腾讯云凭证

## 5. 用户隔离与兼容用户
- v1 任务查询接口只返回当前登录用户的数据
- 旧生成接口支持可选 Bearer token
- 不带 token 时，任务会落到禁用的兼容系统用户名下
- 这样做的目的：
  - 不破坏旧生成入口
  - 不让匿名旧任务进入普通用户历史列表

## 6. Alembic 与迁移
### 6.1 入口
- `alembic.ini`
- `alembic/env.py`
- `alembic/versions/20260418_01_initial_auth_and_task_schema.py`
- `alembic/versions/20260418_02_task_enum_alignment_for_v1_history.py`

### 6.2 常用命令
```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head --sql
```

### 6.3 当前验证边界
- 已验证：
  - Alembic 离线 SQL 生成
  - SQLite 下的认证与任务接口测试
- 未验证：
  - 真实 PostgreSQL 实例上的 `alembic upgrade head`

## 7. 后续迁移方向
建议顺序：
1. 把历史任务前端页面切到 `/api/v1/tasks*`
2. 把任务创建页面切换为 “先创建任务 / 再直传素材 / 再触发生成”
3. 增加 COS 上传完成确认接口
4. 把 Celery worker 和 API 部署到共享持久卷或统一对象存储工作目录
5. 再评估是否移除 `storage/tasks/index.json`

在这之前，对外口径必须明确：当前正式任务执行真源仍是本地文件和 JSON，PostgreSQL 负责任务元数据镜像与用户隔离查询，COS 提供私有文件对象存储能力但不替代 workflow 本地临时文件，Redis/Celery 只负责异步调度。
