# Workflow 说明

## 1. 主图生成链路（当前实现）

### 1.1 提交阶段
1. 前端在 `MainImagePage` 收集上传文件与参数。
2. `frontend/src/services/mainImageApi.ts` 组装 multipart 并调用 `POST /api/image/generate-main`。
3. 后端 `MainImageService.prepare_generation`：
   - 生成 `task_id`；
   - 创建任务目录并落盘 `task.json`；
   - 保存上传素材到 `outputs/tasks/{task_id}/inputs/`；
   - 在 `storage/tasks/index.json` 写入任务摘要；
   - 将任务放入进程内主图队列。

### 1.2 执行阶段
队列 worker 取任务后，执行 `backend.engine.workflows.graph.run_workflow` 固定顺序：
1. `ingest_assets`
2. `director_v2`
3. `prompt_refine_v2`
4. `render_images`
5. `run_qc`
6. `finalize`

执行中通过 `TaskRepository.save_runtime_task` 持续回写进度与状态。

### 1.3 查询与展示阶段
1. 前端轮询 `GET /api/tasks/{task_id}/runtime`。
2. `TaskRuntimeService` 聚合：
   - `task.json`
   - `prompt_plan_v2.json`（若存在）
   - `qc_report.json`（若存在）
   - `final/` 与 `generated/` 目录文件
   - 队列快照（位置、队列长度）
3. 前端渲染进度条、阶段标签、QC 摘要与结果卡片。
4. 结果预览/下载通过 `/api/tasks/{task_id}/files/{file_name}` 读取真实文件。

## 2. 任务状态流转（主图）
常见状态：
- `created`：已提交并排队
- `running`：执行中
- `review_required`：执行完成但建议人工复核
- `completed`：执行完成
- `failed`：执行失败

## 3. 详情图任务链路（V2）
1. 前端在 `/detail-pages` 提交 `POST /api/detail/jobs/plan`（仅规划）或 `POST /api/detail/jobs`（全量生成）。
2. `DetailPageJobService` 创建独立详情图任务并落盘输入：
   - `inputs/request_payload.json`
   - `inputs/asset_manifest.json`（含主图导入的 `main_result`）
3. worker 执行规划阶段，输出：
   - `plan/detail_plan.json`
   - `plan/detail_copy_plan.json`
   - `plan/detail_prompt_plan.json`
4. 全量任务进入渲染阶段：`DetailRenderService` 复用 `backend/engine/providers/router.py` 的图片 provider 路由逐页调用模型生成，不再使用 PIL 占位图。
5. 生成后输出 QC 与打包：
   - `qc/detail_qc_report.json`
   - `exports/detail_bundle.zip`
6. 前端轮询 `GET /api/detail/jobs/{task_id}/runtime`，中栏/右栏同步展示阶段、规划、结果、错误信息；失败原因来自 `task.json.error_message`。

## 4. 与前端工作台的对应关系
- 提交入口：左侧上传和参数区。
- 执行观测：右侧进度区（`progress_percent/current_step/message`）。
- 结果消费：结果卡片（`results[]`），支持预览与下载。
- 页面恢复：`localStorage` 保留最近 `task_id`，刷新后自动恢复。
