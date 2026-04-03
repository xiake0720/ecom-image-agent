# API 文档

## 1. 统一响应结构
除文件流接口外，统一返回 envelope：

```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "requestId": "req_xxx"
}
```

- `code=0` 代表成功。
- 业务错误由 `AppException` 返回非 0 `code`。

## 2. 接口清单

### 2.1 健康检查
- **方法**：`GET`
- **路径**：`/api/health`
- **说明**：服务存活检查。

### 2.2 主图任务提交
- **方法**：`POST`
- **路径**：`/api/image/generate-main`
- **Content-Type**：`multipart/form-data`
- **文件字段**：
  - `white_bg`（必填，单文件）
  - `detail_files`（可选，多文件）
  - `bg_files`（可选，多文件）
- **文本字段**：
  - `brand_name`（默认空）
  - `product_name`（默认空）
  - `category`（默认 `tea`）
  - `platform`（默认 `tmall`）
  - `style_type`（默认 `高端极简`）
  - `style_notes`（默认空）
  - `shot_count`（默认 `8`，范围 `1~12`）
  - `aspect_ratio`（默认 `1:1`）
  - `image_size`（默认 `2K`）
- **成功返回 data（节选）**：`task_id`、`status`、`progress_percent`、`provider_label` 等任务摘要字段。

### 2.3 详情页生成
- **方法**：`POST`
- **路径**：`/api/detail/generate`
- **Body(JSON)**：
  - `title`（必填）
  - `subtitle`
  - `selling_points: string[]`
  - `category`
  - `specs: [{name, value}]`
  - `price_band`
  - `platform`（默认 `tmall`）
  - `style`（默认 `premium`）
  - `main_image_task_id`
  - `main_images: string[]`
  - `product_images: string[]`
  - `optional_copy: string[]`
- **成功返回 data**：`task_id`、`module_config_path`、`preview_data`、`export_assets`、`modules`。

### 2.4 任务列表
- **方法**：`GET`
- **路径**：`/api/tasks`
- **说明**：返回任务摘要列表（按更新时间倒序）。

### 2.5 任务详情
- **方法**：`GET`
- **路径**：`/api/tasks/{task_id}`
- **说明**：返回单任务摘要；任务不存在返回业务错误。

### 2.6 主图运行时（工作台轮询）
- **方法**：`GET`
- **路径**：`/api/tasks/{task_id}/runtime`
- **说明**：聚合 `task.json`、`prompt_plan_v2.json`、`qc_report.json`、结果目录与队列快照。
- **返回核心字段**：
  - 任务状态：`status`、`progress_percent`、`current_step`、`current_step_label`、`message`
  - 队列信息：`queue_position`、`queue_size`
  - 模型信息：`provider_label`、`model_label`
  - 统计信息：`result_count_completed`、`result_count_total`
  - 下载地址：`export_zip_url`、`full_bundle_zip_url`
  - 质检摘要：`qc_summary`
  - 结果卡片：`results[]`

### 2.7 任务文件访问
- **方法**：`GET`
- **路径**：`/api/tasks/{task_id}/files/{file_name}`
- **说明**：访问任务目录下真实文件，后端会校验路径不可越界。
- **返回类型**：文件流（`FileResponse`）。

### 2.8 模板接口
- `GET /api/templates/main-images`：主图模板占位列表。
- `GET /api/templates/detail-pages`：详情页模板列表（读取 `backend/templates/detail_pages/*.json`）。
- `POST /api/templates/detail-pages/preview`：按输入返回详情页预览结构。

### 2.9 静态资产访问
- **方法**：`GET`
- **路径**：`/api/assets/{file_name}`
- **说明**：按文件名访问 `storage_root` 下文件。

## 3. 典型示例

### 3.1 主图提交（curl）
```bash
curl -X POST "http://127.0.0.1:8000/api/image/generate-main" \
  -F "white_bg=@./demo/white_bg.png" \
  -F "detail_files=@./demo/detail1.png" \
  -F "bg_files=@./demo/bg1.png" \
  -F "brand_name=示例品牌" \
  -F "product_name=高山乌龙" \
  -F "platform=tmall" \
  -F "shot_count=8"
```

### 3.2 查询运行时
```bash
curl "http://127.0.0.1:8000/api/tasks/{task_id}/runtime"
```

## 4. 错误说明
- 参数校验失败：HTTP `422`。
- 业务错误：HTTP `400`（例如任务不存在、文件不存在、模板不存在等）。
- 未处理异常：HTTP `500`，返回统一错误文案。


## 详情图任务 API（V2）
- `POST /api/detail/jobs`：创建并执行详情图任务（multipart/form-data，支持 packaging_files / dry_leaf_files / tea_soup_files / leaf_bottom_files / scene_ref_files / bg_ref_files）。
- `POST /api/detail/jobs/plan`：仅生成详情规划、文案和 prompt，不执行渲染。
- `GET /api/detail/jobs/{task_id}`：查询详情图任务摘要。
- `GET /api/detail/jobs/{task_id}/runtime`：查询详情图 runtime（阶段、规划、copy、prompt、QC、结果图、ZIP、失败 message）。
- `GET /api/detail/jobs/{task_id}/files/{file_name}`：下载详情图任务文件。

### 详情图 runtime 关键字段补充
- `message`：运行提示或失败原因，失败时透传 `task.json.error_message`。
- `generated_count / planned_count`：已生成数量与规划数量。
- `images[].status`：单页状态（`queued/running/completed/failed`）。
- `images[].reference_roles`：该页绑定的参考角色（来自 prompt plan）。
- `export_zip_url`：成功后可下载 `exports/detail_bundle.zip`。
