# Celery + Redis 任务架构

## 1. 当前目标
阶段 4 的目标是把主图和详情图任务从进程内队列迁移到 Celery + Redis，同时复用现有 workflow，不重写 prompt、渲染和落盘核心逻辑。

当前策略：
- API 进程负责接收请求、保存输入文件、创建本地任务目录、写入数据库任务镜像，并提交 Celery。
- Celery worker 只接收 `task_id` 和少量执行参数。
- Worker 从 `outputs/tasks/{task_id}/` 恢复 `task.json`、`inputs/asset_manifest.json`、`inputs/request_payload.json` 后执行原 workflow。
- workflow 内部仍通过现有 progress callback 更新本地 JSON，并由兼容层同步到数据库。
- 默认保留 `ECOM_CELERY_ENABLED=false` 的进程内队列 fallback，便于本地无 Redis 时开发调试。

## 2. 新增配置
定义位置：`backend/core/config.py`

环境变量：
- `ECOM_CELERY_ENABLED`
- `ECOM_REDIS_URL`
- `ECOM_CELERY_BROKER_URL`
- `ECOM_CELERY_RESULT_BACKEND`
- `ECOM_CELERY_TASK_ALWAYS_EAGER`
- `ECOM_CELERY_TASK_SERIALIZER`
- `ECOM_CELERY_ACCEPT_CONTENT`
- `ECOM_CELERY_RESULT_SERIALIZER`
- `ECOM_CELERY_TASK_TIME_LIMIT_SECONDS`
- `ECOM_CELERY_TASK_SOFT_TIME_LIMIT_SECONDS`
- `ECOM_CELERY_MAX_RETRIES`
- `ECOM_CELERY_RETRY_COUNTDOWN_SECONDS`

默认行为：
- `ECOM_CELERY_ENABLED=false`：继续使用旧进程内队列。
- `ECOM_CELERY_ENABLED=true`：API 提交 Celery task，实际生成由 worker 执行。
- `ECOM_CELERY_TASK_ALWAYS_EAGER=true`：测试环境可同步执行 Celery task。
- `ECOM_CELERY_BROKER_URL` 或 `ECOM_CELERY_RESULT_BACKEND` 留空时，分别回退到 `ECOM_REDIS_URL`。

## 3. 文件职责
- `backend/workers/celery_app.py`：创建 Celery app，配置 broker、backend、序列化、超时、重试和任务模块。
- `backend/workers/tasks/main_image_tasks.py`：主图 Celery task，按 `task_id` 恢复任务并执行主图 workflow。
- `backend/workers/tasks/detail_page_tasks.py`：详情图 Celery task，按 `task_id` 恢复任务并执行详情图 workflow。
- `backend/services/task_execution_state_service.py`：worker 外层状态、失败和 retry 事件写入。
- `backend/services/main_image_service.py`：新增 `load_prepared_task(task_id)`，从任务目录恢复主图任务输入。
- `backend/services/detail_page_job_service.py`：新增 `load_prepared(...)` 和 `enqueue_existing_task(...)`，从任务目录恢复详情图任务输入。

## 4. 主图流程
1. 前端调用 `POST /api/image/generate-main`。
2. API 调用 `MainImageService.prepare_generation(...)`，保存上传素材，写入 `task.json` 和 `inputs/asset_manifest.json`。
3. 兼容层写入本地 `storage/tasks/index.json`、数据库 `tasks`、`task_assets` 和初始 `task_events`。
4. `ECOM_CELERY_ENABLED=true` 时提交 `ecom.main_image.run(task_id)`。
5. `ECOM_CELERY_ENABLED=false` 时继续提交旧进程内队列。
6. Worker 调用 `MainImageService.load_prepared_task(task_id)` 恢复任务。
7. Worker 调用原 `run_prepared_task(...)` 执行 workflow。
8. progress callback 持续同步本地 JSON、`tasks`、`task_events` 和 `task_results`。

## 5. 详情图流程
1. 前端调用 `POST /api/detail/jobs` 或 `POST /api/detail/jobs/plan`。
2. API 调用 `DetailPageJobService.create_job(..., enqueue=False)`，保存上传素材，写入 `task.json`、`inputs/request_payload.json` 和 `inputs/asset_manifest.json`。
3. 兼容层写入本地任务索引和数据库任务镜像。
4. `ECOM_CELERY_ENABLED=true` 时提交 `ecom.detail_page.run(task_id, plan_only)`。
5. `ECOM_CELERY_ENABLED=false` 时通过 `enqueue_existing_task(...)` 回退旧进程内队列。
6. Worker 调用 `DetailPageJobService.load_prepared(...)` 恢复任务。
7. Worker 调用原 `run_prepared(...)` 执行 detail workflow。
8. progress callback 持续同步本地 JSON、`tasks`、`task_events` 和 `task_results`。

## 6. 状态与失败处理
Worker 外层记录：
- 开始执行：`tasks.status=running`，新增 `task_running` 事件。
- 任务重试：`tasks.status=queued`，更新 `retry_count`，新增 `task_retrying` 事件。
- 最终失败：`tasks.status=failed`，写入 `error_message`、`retry_count` 和 `finished_at`，新增 `task_failed` 事件。

workflow 内部状态仍由 `TaskDbMirrorService.sync_runtime_from_local_sync(...)` 同步。这样做的原因是：当前本地 runtime 仍是旧前端轮询和任务恢复的事实来源，Celery 只替换执行调度层，不替换产物结构。

## 7. 本地启动
启动依赖：
```bash
docker compose -f docker-compose.dev.yml up -d postgres redis
```

迁移数据库：
```bash
alembic upgrade head
```

启动 API：
```bash
uvicorn backend.main:app --reload --port 8000
```

Windows 本地启动 Celery worker 建议使用 solo pool：
```bash
celery -A backend.workers.celery_app.celery_app worker -l info -P solo
```

Linux / macOS 可使用默认 prefork：
```bash
celery -A backend.workers.celery_app.celery_app worker -l info
```

## 8. 当前限制
- API 和 worker 必须共享 `outputs/tasks`、`storage/tasks` 和相同环境变量。
- Celery 模式下暂不返回 Redis 队列精确位置，runtime 仍以数据库状态和本地 runtime 为准。
- 未实现任务取消 API。
- 失败重试是基础策略，当前默认最多重试 1 次。
- 进程内队列代码仍保留，仅作为本地 fallback。
## 9. 阶段 6 图片编辑任务
阶段 6 新增 `backend/workers/tasks/image_edit_tasks.py`：

- Celery task name：`ecom.image_edit.run`
- 入参：`edit_task_id`
- 执行服务：`ImageEditService.run_edit_task_sync(edit_task_id)`
- 数据写入：`tasks(task_type=image_edit)`、`image_edits`、`task_results(result_type=image_edit)`、`task_events`
- 当前 provider 无原生 inpainting 时，执行模式写为 `full_image_constrained_regeneration`
- `ECOM_CELERY_ENABLED=false` 的本地开发环境会使用同一执行服务的后台线程 fallback，生产环境仍建议启用 Celery worker
