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

### 2.7 收尾与导出
`detail_finalize` 会：
1. 根据成功页数和 QC 状态决定任务状态
2. 写入 `detail_manifest.json`
3. 打包 `exports/detail_bundle.zip`

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
