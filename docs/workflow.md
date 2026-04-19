# Workflow 说明

## 1. 主图任务流

### 1.1 提交阶段
1. 前端在 `/main-images` 组装 multipart，调用 `POST /api/image/generate-main`
2. `MainImageService.prepare_generation`
3. 创建 `task_id`
4. 落盘上传素材与 `task.json`
5. 写入 `storage/tasks/index.json`
6. 推入进程内主图队列

### 1.2 执行阶段
主图 worker 调用 `run_workflow(...)`，固定顺序为：
1. `ingest_assets`
2. `director_v2`
3. `prompt_refine_v2`
4. `render_images`
5. `run_qc`
6. `finalize`

### 1.3 展示阶段
1. 前端轮询 `GET /api/tasks/{task_id}/runtime`
2. `TaskRuntimeService` 聚合进度、队列、QC 与结果
3. 前端展示进度条、QC 摘要、结果卡片和下载入口

## 2. 详情图任务流

### 2.1 提交模式
- `/detail-pages` -> `POST /api/detail/jobs/plan`
  - 只跑到 `detail_generate_prompt`
- `/detail-pages` -> `POST /api/detail/jobs`
  - 跑完整 detail graph

### 2.2 创建阶段
`DetailPageJobService` 负责：
1. 创建独立 `task_id`
2. 落盘上传素材到 `outputs/tasks/{task_id}/inputs/`
3. 如选择主图结果，则复制主图 completed 文件并标记为 `main_result`
4. 写入任务摘要到 `storage/tasks/index.json`
5. 构建 detail initial state
6. 触发 `run_detail_workflow(...)`

### 2.3 执行阶段
`run_detail_workflow(...)` 固定顺序：
1. `detail_ingest_assets`
2. `detail_plan`
3. `detail_generate_copy`
4. `detail_generate_prompt`
5. `detail_render_pages`
6. `detail_run_qc`
7. `detail_finalize`

plan-only 模式停在第 4 步，并把任务状态收口为 `completed`。

### 2.4 detail V2 关键行为
- 规划阶段固定走 `tea_tmall_premium_v2` 模板
- 每页固定为 `3:4`、`single_screen_vertical_poster`
- 每页必须有明确 `page_role`
- planner 会按素材可用性选择页职责
- 缺失 `dry_leaf / leaf_bottom` 时不伪造证据页
- 缺失 `tea_soup / scene_ref / bg_ref` 时允许 AI 在页内补足辅助素材
- prompt 按页职责生成，不再递归拼接 `Prompt 草案=`
- 图内可见文案只来自 `title_copy / subtitle_copy / selling_points_for_render`
- `body_copy / notes / 合规说明` 不再混入 render prompt
- 首屏与包装主视觉页会补充接地感、接触阴影、环境遮蔽与统一光向约束
- packaging / main_result 会按页轮换绑定，避免所有页面都复用同一张包装图

### 2.5 渲染与容错
- detail 渲染仍统一走图片 provider
- 每页一次只生成 1 张 `3:4` 单屏图
- 渲染阶段改成页级容错：
  - 单页失败不会立即中断整条任务
  - provider 抖动会触发页级重试
  - 会记录 `retry_count` 与 `retry_strategies`
- 因此一条详情任务现在可能是：
  - 全部成功
  - 部分成功并进入 `review_required`
  - 全部失败并进入 `failed`

### 2.6 评审与 QC
`detail_run_qc` 会同时写出：
- `review/visual_review.json`
- `review/retry_decisions.json`
- `qc/detail_qc_report.json`

当前 QC 覆盖：
- 页数完成度
- 包装参考是否过度复用
- copy 是否缺失
- 锚点素材是否绑定正确
- 比例是否满足 `3:4`
- 标题/参数页是否过密或出现占位值
- 用户可见 copy 是否混入规则句或提示词
- 参数卡是否出现英文 key 或 `snake_case`
- 首屏 prompt 是否具备接地感关键词

### 2.7 收尾与导出
`detail_finalize` 会：
1. 根据成功页数和 QC 状态决定任务状态
2. 写入 `detail_manifest.json`
3. 打包 `exports/detail_bundle.zip`
4. 统一以任务绝对目录计算 bundle 相对路径，避免已生成 ZIP 却把任务误判为失败

状态规则：
- 全部通过：`completed`
- 部分成功或存在 QC 问题：`review_required`
- 0 页成功：`failed`

## 3. 详情图落盘结构
完整任务当前至少包含：
- `inputs/request_payload.json`
- `inputs/asset_manifest.json`
- `inputs/preflight_report.json`
- `plan/director_brief.json`
- `plan/detail_plan.json`
- `plan/detail_copy_plan.json`
- `plan/detail_prompt_plan.json`
- `generated/*.png`
- `generated/detail_render_report.json`
- `review/visual_review.json`
- `review/retry_decisions.json`
- `qc/detail_qc_report.json`
- `detail_manifest.json`
- `exports/detail_bundle.zip`

## 4. 任务状态
主图与详情图共用状态枚举：
- `created`
- `running`
- `review_required`
- `completed`
- `failed`

detail 失败或部分失败时：
- `task.json.error_message` 写用户可读错误
- `GET /api/detail/jobs/{task_id}/runtime` 的 `message` 与 `error_message` 会直接透出
- `review_required` 表示任务已产出部分结果，但仍需要复核 `review/` 与 `qc/`

## 5. 前端轮询关系

### 5.1 主图
- `GET /api/tasks/{task_id}/runtime`

### 5.2 详情图
- `GET /api/detail/jobs/{task_id}/runtime`

详情图前端当前会同步展示：
- 中栏错误横幅
- 右栏 runtime 侧栏
- 规划 / 文案 / Prompt / 结果图

详情图 runtime 现在还会提供：
- `preflight_report`
- `director_brief`
- `visual_review`
- `retry_decisions`

## 6. Celery + Redis 执行调度补充
阶段 4 后，主图和详情图的任务执行调度支持两种模式：
- 默认模式：`ECOM_CELERY_ENABLED=false`，继续使用旧进程内队列。
- Celery 模式：`ECOM_CELERY_ENABLED=true`，API 创建本地任务和数据库任务镜像后，把 `task_id` 提交给 Celery worker。

Celery 模式不改变 workflow 核心顺序：
- 主图 worker 仍执行 `run_workflow(...)`。
- 详情图 worker 仍执行 `run_detail_workflow(...)`。
- 输入文件、`task.json`、runtime 文件和结果产物仍写在 `outputs/tasks/{task_id}/`。
- `storage/tasks/index.json` 仍保留，用于旧 runtime 聚合和本地兼容。

状态写入规则：
- API 创建任务时写入本地任务索引和数据库任务镜像。
- Worker 开始执行时写入 `tasks.status=running` 和 `task_running` 事件。
- Worker 触发 retry 时写入 `tasks.status=queued`、`retry_count` 和 `task_retrying` 事件。
- Worker 最终失败时写入 `tasks.status=failed`、`error_message`、`finished_at` 和 `task_failed` 事件。
- workflow 内部进度仍由 progress callback 同步本地 JSON，并通过兼容层同步到 `tasks`、`task_events`、`task_results`。

部署约束：
- API 和 worker 必须共享同一份 `outputs/tasks/`、`storage/tasks/` 和 provider 环境变量。
- Redis 只作为 Celery broker / result backend，不保存图片文件和任务产物。

## 7. 前端登录态与任务恢复补充
阶段 5 后，前端工作台路由统一要求登录：
- `/main-images`
- `/detail-pages`
- `/tasks`

登录态恢复规则：
- 前端优先使用本地 access token 调用 `GET /api/v1/auth/me`。
- access token 失效时尝试调用 `POST /api/v1/auth/refresh`。
- refresh 成功后更新本地 access token。
- refresh 失败时清理本地 token 并跳转登录页。

历史任务恢复规则：
- `main_image` 从历史任务页恢复到 `/main-images`，并写入 `main-image-active-task-id`。
- `detail_page` 从历史任务页恢复到 `/detail-pages?task_id={task_id}`。
- `image_edit` 只保留类型展示，正式编辑恢复留到阶段 6。

历史任务页数据源：
- 列表：`GET /api/v1/tasks`
- runtime 摘要：`GET /api/v1/tasks/{task_id}/runtime`
- 结果摘要：`GET /api/v1/tasks/{task_id}/results`
- 结果下载：`GET /api/v1/files/{file_id}/download-url`
## 8. 单图编辑工作流补充
阶段 6 后，历史任务结果图支持最小可用的局部编辑：

1. 前端在 `/tasks` 的结果卡片展开编辑面板。
2. 用户拖拽矩形选区，坐标按原图可视区域归一化为 `ratio`。
3. 用户输入编辑指令并调用 `POST /api/v1/results/{result_id}/edits`。
4. 后端创建 `tasks(task_type=image_edit)`、`image_edits` 和初始 `task_events`。
5. Celery 启用时提交 `ecom.image_edit.run`；本地开发未启用 Celery 时使用同一执行服务的后台线程 fallback。
6. worker 复制源图到编辑任务目录，当前以 `full_image_constrained_regeneration` 模式调用现有图片 provider。
7. 生成图写入 `outputs/tasks/{edit_task_id}/final/edited_result.png`。
8. 后端写入新的 `task_results(result_type=image_edit)`，并把 `parent_result_id` 指向源结果。
9. 前端通过 `GET /api/v1/results/{result_id}/edits` 展示编辑历史和派生版本。
