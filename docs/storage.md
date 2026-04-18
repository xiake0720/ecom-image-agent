# 存储方案说明

## 1. 当前存储分层
当前仓库使用两套并行存储：
- 本地文件系统 + JSON：继续承载任务执行真源、任务目录产物和旧 runtime 聚合
- PostgreSQL：承载用户体系、认证、安全审计，以及任务元数据镜像

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
- `cos_key` 当前保存任务目录相对路径，为未来 COS 接入保留字段语义

## 4. 用户隔离与兼容用户
- v1 任务查询接口只返回当前登录用户的数据
- 旧生成接口支持可选 Bearer token
- 不带 token 时，任务会落到禁用的兼容系统用户名下
- 这样做的目的：
  - 不破坏旧生成入口
  - 不让匿名旧任务进入普通用户历史列表

## 5. Alembic 与迁移
### 5.1 入口
- `alembic.ini`
- `alembic/env.py`
- `alembic/versions/20260418_01_initial_auth_and_task_schema.py`
- `alembic/versions/20260418_02_task_enum_alignment_for_v1_history.py`

### 5.2 常用命令
```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head --sql
```

### 5.3 当前验证边界
- 已验证：
  - Alembic 离线 SQL 生成
  - SQLite 下的认证与任务接口测试
- 未验证：
  - 真实 PostgreSQL 实例上的 `alembic upgrade head`

## 6. 后续迁移方向
建议顺序：
1. 继续把 `task_events`、`task_results` 与现有运行态字段对齐
2. 把历史任务前端页面切到 `/api/v1/tasks*`
3. 再评估是否移除 `storage/tasks/index.json`
4. 最后再接入 COS，并把 `cos_key` 切换为真实对象键

在这之前，对外口径必须明确：当前正式任务执行真源仍是本地文件和 JSON，PostgreSQL 负责任务元数据镜像与用户隔离查询。
