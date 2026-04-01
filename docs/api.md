# API 文档

统一返回结构：
```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "requestId": "..."
}
```

## 1. 健康检查
- `GET /api/health`

## 2. 主图生成
- `POST /api/image/generate-main`
- `multipart/form-data`
- 必填文件：`white_bg`
- 可选文件：`detail_files[]`、`bg_files[]`
- 文本字段：
  - `brand_name`
  - `product_name`
  - `category`
  - `platform`
  - `style_type`
  - `style_notes`
  - `shot_count`
  - `aspect_ratio`
  - `image_size`
- 当前行为：
  1. 创建任务并落盘素材
  2. 写入 `task.json` 与任务索引
  3. 放入进程内主图队列
  4. 立即返回 `task_id`
  5. 单 worker 串行执行 workflow

## 3. 任务查询
- `GET /api/tasks`
  - 任务摘要已补充：
    - `progress_percent`
    - `current_step`
    - `current_step_label`
    - `result_count_completed`
    - `result_count_total`
    - `export_zip_path`
    - `provider_label`
    - `model_label`
    - `detail_image_count`
    - `background_image_count`
- `GET /api/tasks/{task_id}`
- `GET /api/tasks/{task_id}/runtime`
  - 用于主图工作台轮询
  - 返回字段：
    - `task_id`
    - `status`
    - `progress_percent`
    - `current_step`
    - `current_step_label`
    - `message`
    - `queue_position`
    - `queue_size`
    - `provider_label`
    - `model_label`
    - `result_count_completed`
    - `result_count_total`
    - `export_zip_url`
    - `full_bundle_zip_url`
    - `qc_summary`
    - `results[]`
- `GET /api/tasks/{task_id}/files/{file_name}`
  - 访问 `outputs/tasks/{task_id}/` 下的真实产物
  - 支持 `final/01_shot_01.png`、`exports/{task_id}_final_images.zip` 这类相对路径

## 4. 详情页生成
- `POST /api/detail/generate`
- JSON 请求，核心字段：
  - `title`
  - `platform`
  - `style`
  - `selling_points[]`
- 返回：模块数组、预览数据、导出资产清单

## 5. 模板查询
- `GET /api/templates/main-images`
- `GET /api/templates/detail-pages`
- `POST /api/templates/detail-pages/preview`

## 6. 资产访问
- `GET /api/assets/{file_name}`
- 该接口仍只覆盖 `storage/` 根目录下的静态文件，不用于任务输出目录访问
