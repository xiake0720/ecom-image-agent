# 任务系统数据库迁移说明

## 1. 迁移目标
本阶段目标是把任务系统从本地 JSON / 文件索引逐步迁移到数据库，同时保持现有主图和详情图生成链路可用。

当前策略是“兼容双写”：
- 任务执行真源仍是本地 `task.json`、`storage/tasks/index.json` 和 `outputs/tasks/{task_id}/`。
- PostgreSQL 负责保存任务元数据镜像、用户归属、历史任务查询、结果摘要和关键事件。
- 不直接替换主图 / 详情图 workflow，不破坏现有轮询、预览和下载能力。

## 2. 当前已落地范围
### 2.1 数据库表
已新增并接入以下任务表：
- `tasks`：任务主表，保存任务类型、状态、用户归属、进度、runtime 快照、结果摘要和错误信息。
- `task_assets`：任务输入素材表，保存上传文件或来源结果文件的元数据。
- `task_results`：任务结果表，保存主图、详情图结果文件的摘要信息。
- `task_events`：任务事件表，保存创建、排队、运行、成功、失败、部分失败等关键状态变化。
- `task_usage_records`：任务用量记录表，当前先提供模型、repository 和写入服务，尚未接入所有 provider 自动写入。

模型定义：
- `backend/db/models/task.py`

Repository：
- `backend/repositories/db/task_db_repository.py`
- `backend/repositories/db/task_asset_repository.py`
- `backend/repositories/db/task_result_repository.py`
- `backend/repositories/db/task_event_repository.py`
- `backend/repositories/db/task_usage_record_repository.py`

### 2.2 任务枚举
任务类型：
- `main_image`
- `detail_page`
- `image_edit`

任务状态：
- `pending`
- `queued`
- `running`
- `succeeded`
- `failed`
- `partial_failed`
- `cancelled`

定义位置：
- `backend/db/enums.py`

旧 workflow 状态映射规则位于：
- `backend/services/task_db_mirror_service.py`

映射关系：
- `created` -> `queued`
- `running` -> `running`
- `completed` -> `succeeded`
- `review_required` -> `partial_failed`
- `failed` -> `failed`

### 2.3 v1 历史任务 API
已新增：
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/tasks/{task_id}/runtime`
- `GET /api/v1/tasks/{task_id}/results`

实现位置：
- `backend/api/v1/tasks.py`
- `backend/services/task_query_service.py`
- `backend/schemas/task_v1.py`

能力：
- 必须携带 `Authorization: Bearer <access_token>`。
- 所有查询按当前登录用户的 `user_id` 过滤。
- 历史列表支持 `page`、`page_size`、`task_type`、`status`。
- 详情接口返回 `runtime_snapshot`、`result_summary`、错误信息和生命周期时间。
- runtime 接口返回数据库任务摘要、旧 runtime 聚合结果和 `task_events`。
- results 接口返回 `task_results` 摘要，并继续生成旧文件接口 URL。

## 3. 兼容写入方案
### 3.1 主图任务
主图任务创建入口：
- `POST /api/image/generate-main`

当前写入顺序：
1. 创建本地 `task_id` 和任务目录。
2. 保存上传素材和 `task.json`。
3. 写入 `storage/tasks/index.json`。
4. 调用 `TaskDbMirrorService.create_task_record(...)` 写入：
   - `tasks`
   - `task_assets`
   - 初始 `task_events`
5. worker 执行旧 workflow。
6. 每次 progress 回写时调用 `sync_runtime_from_local_sync(...)` 同步：
   - `tasks.status`
   - `tasks.current_step`
   - `tasks.progress_percent`
   - `tasks.runtime_snapshot`
   - `tasks.result_summary`
   - `task_events`
   - `task_results`

接入位置：
- `backend/services/main_image_service.py`

### 3.2 详情图任务
详情图任务创建入口：
- `POST /api/detail/jobs`
- `POST /api/detail/jobs/plan`

当前写入顺序与主图一致，但任务类型写为 `detail_page`。

详情图会额外记录：
- `source_task_id`：来源主图任务。
- `task_assets.source_task_result_id`：如果来源主图结果已经镜像到数据库，则建立输入素材到上游结果的引用。
- `task_results.page_no`：详情图结果页码。
- `task_results.render_meta`：渲染 provider、模型、重试次数等摘要。

接入位置：
- `backend/services/detail_page_job_service.py`

### 3.3 兼容用户
旧生成接口允许不带 token 调用。为了避免破坏旧链路：
- 带 token：任务归属当前登录用户。
- 不带 token：任务归属禁用的兼容系统用户。

配置项：
- `ECOM_COMPAT_TASK_USER_EMAIL`
- `ECOM_COMPAT_TASK_USER_NICKNAME`

兼容用户只用于承接匿名旧任务，不会让这些任务出现在普通用户的 v1 历史列表中。

## 4. 用户隔离规则
v1 任务查询必须使用当前登录用户：
- 路由层依赖 `get_current_user`。
- service 层调用 `get_by_id_for_user(...)`、`list_by_user(...)`、`list_by_task_for_user(...)`。
- 用户 B 查询用户 A 的任务时返回 `404 / code=4044`，不暴露任务是否属于其他用户。

相关实现：
- `backend/api/dependencies.py`
- `backend/repositories/db/task_db_repository.py`
- `backend/repositories/db/task_result_repository.py`
- `backend/repositories/db/task_event_repository.py`

## 5. 迁移边界
当前尚未迁移：
- 任务执行调度仍是进程内队列。
- workflow 真源仍是本地 `task.json`。
- 前端历史任务页已切到 `/api/v1/tasks*`，旧 `/api/tasks*` 继续服务主图 / 详情图 runtime 兼容轮询。
- 文件二进制不入库。
- `cos_key` 本地兼容模式保存任务目录相对路径，COS 模式保存真实对象 key。
- `task_usage_records` 尚未自动覆盖所有 provider 调用。
- 任务取消、任务重试、image_edit 正式生成链路尚未完成。

## 6. 验证方式
已有集成测试覆盖：
- 创建主图任务后可从 `/api/v1/tasks` 查询到。
- 历史任务列表支持 `task_type` 和 `status` 过滤。
- 用户 A 创建的任务，用户 B 在列表中不可见。
- 用户 B 直接访问用户 A 的任务详情返回 404。
- 任务详情可返回 `result_summary`。
- runtime 接口可返回 runtime 摘要和 `task_events`。
- results 接口可返回 `task_results` 摘要和旧文件 URL。

测试文件：
- `tests/integration/test_task_api.py`
- `tests/integration/test_auth_api.py`

建议命令：
```bash
python -m pytest tests/integration/test_task_api.py tests/integration/test_auth_api.py -q
```

## 7. 后续迁移顺序
建议按以下顺序继续：
1. 补充详情图完整任务的数据库镜像测试。
2. 将 provider 调用逐步接入 `TaskUsageRecordService`。
3. 把主图 / 详情图上传流程切换为“先建任务 / 再直传 COS / 再触发生成”。
4. 评估 task runtime 是否可以从数据库快照直接恢复，减少对 JSON 索引的依赖。
5. 增加 COS 上传完成确认接口，避免 presign 后未上传也长期保留 pending 素材。
6. 最后再评估是否移除或降级 `storage/tasks/index.json`。

## 8. 当前完成口径
本阶段可对外描述为：
- 后端任务数据库镜像和 v1 历史查询接口已完成。
- 主图 / 详情图旧生成链路保持兼容，并已补充数据库写入。
- 历史任务查询已按当前登录用户隔离。
- 任务 runtime 和结果摘要可通过 v1 API 查询。

不得描述为：
- 任务系统已经完全迁移到数据库。
- 本地 JSON 索引已经可以删除。
- 任务调度已经数据库化。
- provider 用量统计已经全量自动落库。
## 9. 阶段 6 图片编辑补充
- `image_edit` 正式生成链路已接入：`POST /api/v1/results/{result_id}/edits` 创建编辑任务，`GET /api/v1/results/{result_id}/edits` 查询编辑历史。
- 新增 `image_edits` 表，保存源结果、编辑任务、派生结果、矩形选区、编辑指令、执行模式和状态。
- 编辑任务写入 `tasks(task_type=image_edit)`，编辑完成后写入 `task_results(result_type=image_edit)`，并以 `parent_result_id` 关联源结果。
- 当前 provider 无原生局部重绘接口，代码明确标记 `mode=full_image_constrained_regeneration`。
- 历史任务页已可查看 `image_edit` 任务和派生结果摘要。
