# 主图工作台 Runtime Contract

## 接口
- `GET /api/tasks/{task_id}/runtime`

## 用途
- 供 `MainImagePage` 轮询读取当前任务进度和结果图列表。
- 尽量复用 `outputs/tasks/{task_id}/` 已落盘文件，不引入额外数据库结构。

## 返回字段
```json
{
  "task_id": "string",
  "status": "created | running | completed | review_required | failed",
  "progress_percent": 0,
  "current_step": "queued | ingest_assets | director_v2 | prompt_refine_v2 | render_images | run_qc | finalize",
  "current_step_label": "string",
  "message": "string",
  "queue_position": 0,
  "queue_size": 1,
  "provider_label": "runapi_gemini31",
  "model_label": "Gemini 3.1 Flash Image Preview",
  "detail_image_count": 2,
  "background_image_count": 1,
  "result_count_completed": 4,
  "result_count_total": 8,
  "export_zip_url": "/api/tasks/{task_id}/files/exports/{task_id}_final_images.zip",
  "full_bundle_zip_url": "/api/tasks/{task_id}/files/exports/{task_id}_full_task_bundle.zip",
  "qc_summary": {
    "passed": false,
    "review_required": true,
    "warning_count": 2,
    "failed_count": 0
  },
  "results": [
    {
      "id": "shot_01",
      "title": "东方茶礼",
      "subtitle": "hero",
      "status": "queued | running | completed | failed",
      "image_url": "/api/tasks/{task_id}/files/final/01_shot_01.png",
      "file_name": "final/01_shot_01.png",
      "width": 2048,
      "height": 2048,
      "generated_at": "2026-04-01T12:00:00"
    }
  ]
}
```

## 字段语义
- `status`
  - 任务级状态，直接来自 `task.json`
- `progress_percent`
  - 当前任务整体进度，直接来自 `task.json`
- `current_step`
  - 当前 workflow 步骤名，用于前端阶段高亮
- `current_step_label`
  - 当前步骤中文提示
- `message`
  - 前端右侧进度卡副标题
  - 失败时优先使用 `error_message`
  - 运行中时优先使用“正在生成第 x / y 张结果图”
- `queue_position`
  - 表示“前方还有多少任务”
  - `0` 表示当前任务已被 worker 取走并正在执行
- `queue_size`
  - 当前进程内主图队列总长度，包含执行中的任务
- `provider_label / model_label`
  - 任务创建时写入索引的 provider / model 快照
  - 用于避免全局配置变化后旧任务显示错误模型
- `detail_image_count / background_image_count`
  - 当前任务提交时的参考图数量摘要
- `result_count_completed / result_count_total`
  - 用于工作台结果区头部、任务记录页摘要和恢复展示
- `export_zip_url / full_bundle_zip_url`
  - 分别对应最终结果 ZIP 和完整任务包 ZIP 下载入口
- `qc_summary`
  - 对 `qc_report.json` 的轻量聚合，便于工作台直接显示 `passed / warning / failed`
- `results[]`
  - 优先读取 `final/` 目录中的真实图片
  - `final/` 为空时回退读取 `generated/`
  - 未生成的槽位根据任务状态补成 `queued / running / failed`
  - 已落盘图片会附带 `width / height / generated_at`

## 结果卡片组装规则
- 标题优先使用 `prompt_plan_v2.json` 中的 `title_copy`
- 副标题优先使用 `prompt_plan_v2.json` 中的 `shot_role`
- 如果 `prompt_plan_v2.json` 不存在，则按 `shot_count` 生成 `结果 01 / 结果 02 ...` 占位卡

## 任务文件访问
- `GET /api/tasks/{task_id}/files/{file_name}`
- 仅允许访问当前任务目录下的相对路径
- 典型路径：
  - `final/01_shot_01.png`
  - `generated/01_shot_01.png`
  - `exports/{task_id}_final_images.zip`
  - `exports/{task_id}_full_task_bundle.zip`
