# Workflow 说明

## 1. 主图任务流

### 1.1 提交阶段
1. 前端在 `/main-images` 组装 multipart，调用 `POST /api/image/generate-main`
2. [`MainImageService.prepare_generation`](/D:/python/ecom-image-agent/backend/services/main_image_service.py)：
   - 创建 `task_id`
   - 落盘上传素材与 `task.json`
   - 写入 `storage/tasks/index.json`
   - 推入进程内主图队列

### 1.2 执行阶段
主图队列 worker 调用 [`run_workflow`](/D:/python/ecom-image-agent/backend/engine/workflows/graph.py)：
1. `ingest_assets`
2. `director_v2`
3. `prompt_refine_v2`
4. `render_images`
5. `run_qc`
6. `finalize`

### 1.3 展示阶段
1. 前端轮询 `GET /api/tasks/{task_id}/runtime`
2. [`TaskRuntimeService`](/D:/python/ecom-image-agent/backend/services/task_runtime_service.py) 聚合进度、队列、QC 与结果
3. 前端展示进度条、QC 摘要、结果卡片、下载链接

## 2. 详情图任务流

### 2.1 提交模式
- `/detail-pages` -> `POST /api/detail/jobs/plan`
  - 只跑到 `detail_generate_prompt`
- `/detail-pages` -> `POST /api/detail/jobs`
  - 跑完整 detail graph

### 2.2 创建阶段
[`DetailPageJobService`](/D:/python/ecom-image-agent/backend/services/detail_page_job_service.py)：
1. 创建独立 `task_id`
2. 落盘上传素材到 `outputs/tasks/{task_id}/inputs/`
3. 若选择主图任务结果，则复制主图 completed 文件并标记为 `main_result`
4. 写入任务摘要到 `storage/tasks/index.json`
5. 构建 detail initial state
6. 触发 `run_detail_workflow(...)`

### 2.3 执行阶段
[`run_detail_workflow`](/D:/python/ecom-image-agent/backend/engine/workflows/detail_graph.py) 固定顺序：
1. `detail_ingest_assets`
2. `detail_plan`
3. `detail_generate_copy`
4. `detail_generate_prompt`
5. `detail_render_pages`
6. `detail_run_qc`
7. `detail_finalize`

plan-only 模式停在第 4 步，并把任务状态收口为已完成。

### 2.4 导演 Agent 与 Graph 的配合
导演 Agent 节点：
- `detail_plan`
- `detail_generate_copy`
- `detail_generate_prompt`

生产 Graph 节点：
- `detail_ingest_assets`
- `detail_render_pages`
- `detail_run_qc`
- `detail_finalize`

职责边界：
- Agent 负责“想”：规划、文案、Prompt
- Graph 负责“跑”：执行、落盘、QC、导出、runtime

### 2.5 详情图落盘结构
完整任务至少包含：
- `inputs/request_payload.json`
- `inputs/asset_manifest.json`
- `plan/detail_plan.json`
- `plan/detail_copy_plan.json`
- `plan/detail_prompt_plan.json`
- `generated/*.png`
- `generated/detail_render_report.json`
- `qc/detail_qc_report.json`
- `detail_manifest.json`
- `exports/detail_bundle.zip`

### 2.6 详情图渲染规则
- 正式模式统一走 Banana2 provider
- 每张详情图一次请求完成 1:3 长图
- 不允许本地拼图、叠字、占位图冒充正式结果
- 参考图通过 prompt plan 的 `references` 绑定下发

### 2.7 detail mock mode
- 通过统一 provider mode 切换
- mock text provider 返回稳定结构化输出
- mock image provider 复制预置样张到 `generated/`
- runtime、QC、下载、ZIP 与真实模式保持一致

## 3. 任务状态
主图与详情图共用任务状态枚举：
- `created`
- `running`
- `review_required`
- `completed`
- `failed`

detail 失败时：
- `task.json.error_message` 写入真实用户可读错误
- `GET /api/detail/jobs/{task_id}/runtime` 的 `message` 与 `error_message` 会直接透出

## 4. 前端轮询关系

### 4.1 主图
- `GET /api/tasks/{task_id}/runtime`

### 4.2 详情图
- `GET /api/detail/jobs/{task_id}/runtime`

详情图前端会同步展示：
- 中栏错误横幅
- 右栏 runtime 侧栏
- 规划 / 文案 / Prompt / 结果图
