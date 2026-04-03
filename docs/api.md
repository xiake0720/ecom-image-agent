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

## 2. 主图接口

### 2.1 `POST /api/image/generate-main`
- `Content-Type`：`multipart/form-data`
- 文件字段：
  - `white_bg` 必填
  - `detail_files[]` 可选
  - `bg_files[]` 可选
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

### 2.2 `GET /api/tasks`
- 返回任务摘要列表。

### 2.3 `GET /api/tasks/{task_id}`
- 返回单个任务摘要。

### 2.4 `GET /api/tasks/{task_id}/runtime`
- 返回主图运行时聚合：
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

### 2.5 `GET /api/tasks/{task_id}/files/{file_name}`
- 下载主图任务文件。

## 3. 详情图接口

### 3.1 `POST /api/detail/jobs`
- 作用：执行完整 detail graph
- `Content-Type`：`multipart/form-data`
- 文件字段：
  - `packaging_files[]`
  - `dry_leaf_files[]`
  - `tea_soup_files[]`
  - `leaf_bottom_files[]`
  - `scene_ref_files[]`
  - `bg_ref_files[]`
- 文本字段：
  - `brand_name`
  - `product_name`
  - `tea_type`
  - `platform`，当前默认 `tmall`
  - `style_preset`，当前默认 `tea_tmall_premium_light`
  - `price_band`
  - `target_slice_count`，当前支持 `4~6`
  - `image_size`，当前默认 `2K`
  - `main_image_task_id`
  - `selected_main_result_ids`，JSON 数组字符串
  - `selling_points_json`，JSON 数组字符串
  - `specs_json`，JSON 对象字符串
  - `style_notes`
  - `brew_suggestion`
  - `extra_requirements`
  - `prefer_main_result_first`

返回 data：

```json
{
  "task_id": "detail_xxx",
  "status": "created"
}
```

### 3.2 `POST /api/detail/jobs/plan`
- 作用：只执行到 `detail_generate_prompt`
- 不执行：
  - `detail_render_pages`
  - `detail_run_qc`
  - `detail_finalize`

### 3.3 `GET /api/detail/jobs/{task_id}`
- 返回详情图任务摘要。

### 3.4 `GET /api/detail/jobs/{task_id}/runtime`
- 返回 detail graph 运行时聚合，核心字段：
  - `task_id`
  - `status`
  - `progress_percent`
  - `current_stage`
  - `current_stage_label`
  - `message`
  - `error_message`
  - `generated_count`
  - `planned_count`
  - `plan`
  - `copy_blocks`
  - `prompt_plan`
  - `qc_summary`
  - `images`
  - `export_zip_url`

`plan` 结构核心字段：
- `template_name`
- `global_style_anchor`
- `narrative`
- `total_pages`
- `total_screens`
- `pages[]`

`copy_blocks[]` 结构核心字段：
- `page_id`
- `screen_id`
- `headline`
- `subheadline`
- `selling_points`
- `body_copy`
- `parameter_copy`
- `cta_copy`
- `notes`

`prompt_plan[]` 结构核心字段：
- `page_id`
- `page_title`
- `global_style_anchor`
- `screen_themes`
- `layout_notes`
- `prompt`
- `negative_prompt`
- `references[]`
- `target_aspect_ratio`
- `target_width`
- `target_height`

`qc_summary` 结构核心字段：
- `passed`
- `review_required`
- `warning_count`
- `failed_count`
- `issues[]`
- `checks[]`
- `pages[]`

`images[]` 结构核心字段：
- `image_id`
- `page_id`
- `title`
- `status`
- `file_name`
- `image_url`
- `width`
- `height`
- `reference_roles`
- `error_message`

### 3.5 `GET /api/detail/jobs/{task_id}/files/{file_name}`
- 下载详情图任务文件。

## 4. detail graph 节点链路
完整链路：
1. `detail_ingest_assets`
2. `detail_plan`
3. `detail_generate_copy`
4. `detail_generate_prompt`
5. `detail_render_pages`
6. `detail_run_qc`
7. `detail_finalize`

plan-only 链路：
1. `detail_ingest_assets`
2. `detail_plan`
3. `detail_generate_copy`
4. `detail_generate_prompt`

## 5. mock / real 模式

### 5.1 mock
- `ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE=mock`
- `ECOM_IMAGE_AGENT_IMAGE_PROVIDER_MODE=mock`

说明：
- mock text provider 返回稳定结构化 plan/copy/prompt
- mock image provider 直接复制预置样张到 `generated/`
- runtime、预览、下载、ZIP 仍走真实 detail graph 链路
- mock mode 不再使用运行时 PIL 画占位详情长图

### 5.2 real
- `ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE=real`
- `ECOM_IMAGE_AGENT_IMAGE_PROVIDER_MODE=real`
- `ECOM_IMAGE_AGENT_IMAGE_PROVIDER=banana2`

说明：
- 文本规划/文案/prompt 继续走统一文本 provider/router
- 图片渲染默认走 Banana2 provider
- Banana2 provider 优先用 `ECOM_IMAGE_AGENT_GOOGLE_API_KEY`
- 若未配置 Google API Key，则回退到 `ECOM_IMAGE_AGENT_RUNAPI_API_KEY` 对应的统一图片通道

## 6. 模板与静态资源接口
- `GET /api/templates/main-images`
- `GET /api/templates/detail-pages`
- `POST /api/templates/detail-pages/preview`
- `GET /api/assets/{file_name}`

## 7. 错误处理
- 参数校验失败：HTTP `422`
- 业务错误：HTTP `400`
- 未处理异常：HTTP `500`

detail 运行失败时，`runtime.message` 优先返回 `task.json.error_message`，前端中栏与右栏都会直接展示。
