# Database Schema V1

## 1. 概览
当前数据库技术栈：
- PostgreSQL
- SQLAlchemy Async
- Alembic

本文件描述当前仓库已经落地的 v1 数据库 schema。

## 2. 统一约束
- 主键统一为 `UUID`
- 时间字段统一为 `TIMESTAMPTZ`
- `updated_at` 通过数据库触发器 `set_updated_at_timestamp()` 自动更新
- 文件二进制不入库，只存元数据和对象键
- 所有任务相关表都带 `user_id`
- 当前阶段 `cos_key` 保存任务目录相对路径，作为未来 COS 对象键占位字段

## 3. 集中枚举
定义位置：`backend/db/enums.py`

### 3.1 users.status
- `active`
- `disabled`
- `suspended`

### 3.2 tasks.task_type
- `main_image`
- `detail_page`
- `image_edit`

### 3.3 tasks.status
- `pending`
- `queued`
- `running`
- `succeeded`
- `failed`
- `partial_failed`
- `cancelled`

### 3.4 task_results.status
- `pending`
- `succeeded`
- `failed`

### 3.5 task_assets.scan_status
- `pending`
- `clean`
- `blocked`

### 3.6 task_events.level
- `info`
- `warning`
- `error`

### 3.7 task_results.qc_status
- `pending`
- `passed`
- `review_required`
- `failed`

## 4. 阶段 1 表
### 4.1 users
| 字段 | 类型 | 约束 |
| --- | --- | --- |
| id | UUID | PK |
| email | VARCHAR(255) | NOT NULL, UNIQUE |
| password_hash | VARCHAR(255) | NOT NULL |
| nickname | VARCHAR(100) | NULL |
| avatar_url | VARCHAR(500) | NULL |
| status | VARCHAR(32) | NOT NULL, default `active` |
| email_verified | BOOLEAN | NOT NULL, default `false` |
| last_login_at | TIMESTAMPTZ | NULL |
| last_login_ip | INET | NULL |
| created_at | TIMESTAMPTZ | NOT NULL, default `now()` |
| updated_at | TIMESTAMPTZ | NOT NULL, default `now()` |
| deleted_at | TIMESTAMPTZ | NULL |

索引：
- `uq_users_email`
- `ix_users_status_created_at`

### 4.2 refresh_tokens
| 字段 | 类型 | 约束 |
| --- | --- | --- |
| id | UUID | PK |
| user_id | UUID | FK -> users.id, NOT NULL |
| token_hash | VARCHAR(255) | NOT NULL, UNIQUE |
| device_id | VARCHAR(128) | NULL |
| user_agent | VARCHAR(500) | NULL |
| ip_address | INET | NULL |
| expires_at | TIMESTAMPTZ | NOT NULL |
| revoked_at | TIMESTAMPTZ | NULL |
| replaced_by_token_id | UUID | FK -> refresh_tokens.id, NULL |
| created_at | TIMESTAMPTZ | NOT NULL, default `now()` |
| updated_at | TIMESTAMPTZ | NOT NULL, default `now()` |

索引：
- `uq_refresh_tokens_token_hash`
- `ix_refresh_tokens_user_id_revoked_at`
- `ix_refresh_tokens_user_id_expires_at`

### 4.3 audit_logs
| 字段 | 类型 | 约束 |
| --- | --- | --- |
| id | UUID | PK |
| user_id | UUID | FK -> users.id, NULL |
| action | VARCHAR(100) | NOT NULL |
| object_type | VARCHAR(50) | NULL |
| object_id | UUID | NULL |
| request_id | VARCHAR(64) | NULL |
| ip_address | INET | NULL |
| user_agent | VARCHAR(500) | NULL |
| payload | JSONB | NULL |
| created_at | TIMESTAMPTZ | NOT NULL, default `now()` |

索引：
- `ix_audit_logs_user_id_created_at`
- `ix_audit_logs_action_created_at`
- `ix_audit_logs_request_id`

### 4.4 idempotency_keys
| 字段 | 类型 | 约束 |
| --- | --- | --- |
| id | UUID | PK |
| user_id | UUID | FK -> users.id, NOT NULL |
| request_key | VARCHAR(128) | NOT NULL |
| request_hash | VARCHAR(128) | NOT NULL |
| endpoint | VARCHAR(255) | NOT NULL |
| response_status | INTEGER | NULL |
| response_body | JSONB | NULL |
| expires_at | TIMESTAMPTZ | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL, default `now()` |

约束与索引：
- `UNIQUE (user_id, request_key)`
- `ix_idempotency_keys_expires_at`
- `ix_idempotency_keys_user_id_endpoint`

## 5. 阶段 2 表
### 5.1 tasks
| 字段 | 类型 | 约束 |
| --- | --- | --- |
| id | UUID | PK |
| user_id | UUID | FK -> users.id, NOT NULL |
| task_type | VARCHAR(32) | NOT NULL |
| status | VARCHAR(32) | NOT NULL, default `pending` |
| title | VARCHAR(255) | NULL |
| platform | VARCHAR(50) | NULL |
| biz_id | VARCHAR(100) | NULL |
| source_task_id | UUID | FK -> tasks.id, NULL |
| parent_task_id | UUID | FK -> tasks.id, NULL |
| current_step | VARCHAR(100) | NULL |
| progress_percent | NUMERIC(5,2) | NOT NULL, default `0` |
| input_summary | JSONB | NULL |
| params | JSONB | NULL |
| runtime_snapshot | JSONB | NULL |
| result_summary | JSONB | NULL |
| error_code | VARCHAR(100) | NULL |
| error_message | TEXT | NULL |
| retry_count | INTEGER | NOT NULL, default `0` |
| started_at | TIMESTAMPTZ | NULL |
| finished_at | TIMESTAMPTZ | NULL |
| created_at | TIMESTAMPTZ | NOT NULL, default `now()` |
| updated_at | TIMESTAMPTZ | NOT NULL, default `now()` |
| deleted_at | TIMESTAMPTZ | NULL |

索引：
- `ix_tasks_user_id_created_at`
- `ix_tasks_user_id_status`
- `ix_tasks_user_id_task_type`
- `ix_tasks_biz_id`
- `ix_tasks_source_task_id`
- `ix_tasks_parent_task_id`

### 5.2 task_assets
| 字段 | 类型 | 约束 |
| --- | --- | --- |
| id | UUID | PK |
| task_id | UUID | FK -> tasks.id, NOT NULL |
| user_id | UUID | FK -> users.id, NOT NULL |
| role | VARCHAR(50) | NOT NULL |
| source_type | VARCHAR(50) | NOT NULL |
| source_task_result_id | UUID | FK -> task_results.id, NULL |
| file_name | VARCHAR(255) | NULL |
| cos_key | VARCHAR(500) | NOT NULL |
| mime_type | VARCHAR(100) | NOT NULL |
| size_bytes | BIGINT | NOT NULL |
| sha256 | CHAR(64) | NOT NULL |
| width | INTEGER | NULL |
| height | INTEGER | NULL |
| duration_ms | INTEGER | NULL |
| metadata | JSONB | NULL |
| scan_status | VARCHAR(32) | NOT NULL, default `pending` |
| sort_order | INTEGER | NOT NULL, default `0` |
| created_at | TIMESTAMPTZ | NOT NULL, default `now()` |
| updated_at | TIMESTAMPTZ | NOT NULL, default `now()` |

索引：
- `ix_task_assets_task_id_sort_order`
- `ix_task_assets_user_id_created_at`
- `ix_task_assets_task_id_role`
- `ix_task_assets_source_task_result_id`

### 5.3 task_results
| 字段 | 类型 | 约束 |
| --- | --- | --- |
| id | UUID | PK |
| task_id | UUID | FK -> tasks.id, NOT NULL |
| user_id | UUID | FK -> users.id, NOT NULL |
| result_type | VARCHAR(50) | NOT NULL |
| page_no | INTEGER | NULL |
| shot_no | INTEGER | NULL |
| version_no | INTEGER | NOT NULL, default `1` |
| parent_result_id | UUID | FK -> task_results.id, NULL |
| status | VARCHAR(32) | NOT NULL, default `succeeded` |
| cos_key | VARCHAR(500) | NOT NULL |
| mime_type | VARCHAR(100) | NOT NULL |
| size_bytes | BIGINT | NOT NULL |
| sha256 | CHAR(64) | NOT NULL |
| width | INTEGER | NULL |
| height | INTEGER | NULL |
| prompt_plan | JSONB | NULL |
| prompt_final | JSONB | NULL |
| render_meta | JSONB | NULL |
| qc_status | VARCHAR(32) | NULL |
| qc_score | NUMERIC(5,2) | NULL |
| is_primary | BOOLEAN | NOT NULL, default `true` |
| created_at | TIMESTAMPTZ | NOT NULL, default `now()` |
| updated_at | TIMESTAMPTZ | NOT NULL, default `now()` |

索引：
- `ix_task_results_task_id_created_at`
- `ix_task_results_user_id_created_at`
- `ix_task_results_task_id_result_type`
- `ix_task_results_parent_result_id`
- `ix_task_results_task_id_page_no_shot_no`

### 5.4 task_events
| 字段 | 类型 | 约束 |
| --- | --- | --- |
| id | UUID | PK |
| task_id | UUID | FK -> tasks.id, NOT NULL |
| user_id | UUID | FK -> users.id, NOT NULL |
| event_type | VARCHAR(50) | NOT NULL |
| level | VARCHAR(20) | NOT NULL, default `info` |
| step | VARCHAR(100) | NULL |
| message | TEXT | NOT NULL |
| payload | JSONB | NULL |
| created_at | TIMESTAMPTZ | NOT NULL, default `now()` |

索引：
- `ix_task_events_task_id_created_at`
- `ix_task_events_user_id_created_at`
- `ix_task_events_task_id_event_type`

### 5.5 task_usage_records
| 字段 | 类型 | 约束 |
| --- | --- | --- |
| id | UUID | PK |
| task_id | UUID | FK -> tasks.id, NOT NULL |
| user_id | UUID | FK -> users.id, NOT NULL |
| provider_type | VARCHAR(50) | NOT NULL |
| provider_name | VARCHAR(100) | NOT NULL |
| model_name | VARCHAR(100) | NULL |
| action_name | VARCHAR(100) | NOT NULL |
| request_units | INTEGER | NULL |
| prompt_tokens | INTEGER | NULL |
| completion_tokens | INTEGER | NULL |
| image_count | INTEGER | NULL |
| latency_ms | INTEGER | NULL |
| cost_amount | NUMERIC(12,4) | NULL |
| cost_currency | VARCHAR(10) | NOT NULL, default `CNY` |
| success | BOOLEAN | NOT NULL, default `true` |
| error_code | VARCHAR(100) | NULL |
| metadata | JSONB | NULL |
| created_at | TIMESTAMPTZ | NOT NULL, default `now()` |

索引：
- `ix_task_usage_records_task_id_created_at`
- `ix_task_usage_records_user_id_created_at`
- `ix_task_usage_records_provider_type_provider_name`

## 6. 自动更新时间方案
更新触发器定义于 migration：
- 函数：`set_updated_at_timestamp()`
- 触发表：
  - `users`
  - `refresh_tokens`
  - `tasks`
  - `task_results`
  - `task_assets`

这层方案保证：
- ORM 更新会刷新 `updated_at`
- 未来如果有直连 SQL 更新，也不会漏写 `updated_at`

## 7. 当前接入状态
- 已正式接入业务：`users`、`refresh_tokens`、`audit_logs`、`idempotency_keys`
- 已接入兼容双写：`tasks`、`task_assets`、`task_results`、`task_events`
- 已提供预留写入服务：`task_usage_records`
- 当前任务 runtime 真源仍是本地文件和 JSON，数据库承担元数据镜像与历史查询职责
