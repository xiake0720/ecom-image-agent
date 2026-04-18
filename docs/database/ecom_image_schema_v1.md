# 电商作图项目数据库表结构说明（V1）

## 设计目标

这版表结构面向一期上线，覆盖以下核心能力：

- 用户注册、登录、登出、刷新令牌
- 主图生成任务
- 详情图生成任务
- 历史任务查询
- 任务素材管理
- 任务结果管理
- 模型调用与成本统计
- 单张图片局部编辑与二次生成
- 审计日志与幂等控制

数据库建议：**PostgreSQL 14+**

---

## 表清单

### 1. users
用户主表。

### 2. refresh_tokens
刷新令牌表，用于维护多设备登录会话和令牌轮换。

### 3. audit_logs
审计日志表，记录登录、任务创建、下载、编辑等关键操作。

### 4. idempotency_keys
幂等键表，避免重复提交创建出多个相同任务。

### 5. tasks
任务主表，统一承载主图生成、详情图生成、图片编辑任务。

### 6. task_assets
任务素材表，记录上传素材、参考图、遮罩图、标注图等。

### 7. task_results
任务结果表，记录主图、详情图分页结果、编辑新版本图等。

### 8. task_events
任务事件表，记录任务执行过程中的状态变化和事件流。

### 9. task_usage_records
任务用量记录表，记录模型调用、耗时、成本、图片数量等统计数据。

### 10. image_edits
图片编辑表，记录单图局部编辑请求和新版本结果关系。

---

## 核心关系

```text
users
 ├── refresh_tokens
 ├── audit_logs
 ├── idempotency_keys
 ├── tasks
 │    ├── task_assets
 │    ├── task_results
 │    ├── task_events
 │    └── task_usage_records
 │
 └── image_edits

任务来源关系：
- tasks.source_task_id -> tasks.id
- tasks.parent_task_id -> tasks.id

结果派生关系：
- task_results.parent_result_id -> task_results.id
- image_edits.result_id -> task_results.id
- image_edits.new_result_id -> task_results.id
```

---

## 状态与枚举建议

### 用户状态
- active：正常
- disabled：禁用
- pending_verification：待验证

### 任务类型
- main_image：主图生成
- detail_page：详情图生成
- image_edit：图片编辑

### 任务状态
- pending：待处理
- queued：已入队
- running：执行中
- succeeded：成功
- failed：失败
- partial_failed：部分失败
- cancelled：已取消

### 编辑模式
- rect：矩形选区
- brush：画笔遮罩
- mask：遮罩图模式
- fallback_regen：局部编辑能力不支持时退化为受约束全图重生成

---

## 索引策略

### 高频查询场景
- 按用户分页查询任务：`tasks(user_id, created_at desc)`
- 按用户 + 类型 + 状态过滤任务：`tasks(user_id, task_type, status, created_at desc)`
- 按任务查询结果：`task_results(task_id)`
- 按任务查询事件流：`task_events(task_id, created_at asc)`
- 按任务查询素材：`task_assets(task_id)`
- 按用户聚合统计调用成本：`task_usage_records(user_id, created_at desc)`

### JSONB 检索场景
这些字段已经预留 GIN 索引：
- audit_logs.payload
- tasks.params
- tasks.runtime_snapshot
- task_assets.metadata
- task_results.prompt_plan
- task_results.prompt_final
- task_events.payload
- task_usage_records.metadata
- image_edits.annotation_data

---

## 设计说明

### 1. 为什么所有任务相关表都带 user_id
这样做便于：
- 权限校验更直接
- 分区或索引更容易优化
- 审计与统计更方便

### 2. 为什么文件不进数据库
图片和遮罩图全部进入腾讯云 COS，数据库只保存：
- `cos_key`
- 文件元数据
- hash
- 所属任务、所属用户、来源关系

### 3. 为什么保留 JSONB
以下数据结构天然变化较大，适合 JSONB：
- prompt 规划结果
- 任务参数
- 运行时快照
- provider 原始元数据
- 标注坐标数据

### 4. 为什么用软删除
首版仅对 `users`、`tasks` 预留 `deleted_at`，避免误删后无法追溯。

### 5. 为什么保留审计日志
后续上线后排查问题最常依赖：
- 谁创建了任务
- 谁下载了图片
- 谁执行了编辑
- 哪个请求出错了

---

## 落地建议

建议你把 SQL 文件放到项目里，例如：

```text
backend/db/sql/001_init_schema.sql
```

如果后面要切 Alembic，建议拆成：

```text
001_users_and_auth
002_tasks_core
003_assets_and_results
004_usage_and_audit
005_image_edits
```

这样后续迁移更稳。

---

## 本次输出文件

- `ecom_image_schema_v1.sql`：可直接执行的 PostgreSQL 建表脚本
- `ecom_image_schema_v1.md`：表结构说明文档
