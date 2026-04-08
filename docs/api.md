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
  - `white_bg`
  - `detail_files[]`
  - `bg_files[]`
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
- 返回单个主图任务摘要。

### 2.4 `GET /api/tasks/{task_id}/runtime`
- 返回主图 runtime 聚合：
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
- 作用：执行完整 detail graph。
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
  - `platform`
  - `style_preset`
  - `price_band`
  - `target_slice_count`
  - `image_size`
  - `main_image_task_id`
  - `selected_main_result_ids`
  - `selling_points_json`
  - `specs_json`
  - `style_notes`
  - `brew_suggestion`
  - `extra_requirements`
  - `prefer_main_result_first`

返回：

```json
{
  "task_id": "detail_xxx",
  "status": "created"
}
```

### 3.2 `POST /api/detail/jobs/plan`
- 作用：只执行到 `detail_generate_prompt`。
- 不执行：
  - `detail_render_pages`
  - `detail_run_qc`
  - `detail_finalize`

### 3.3 `GET /api/detail/jobs/{task_id}`
- 返回详情图任务摘要。

### 3.4 `GET /api/detail/jobs/{task_id}/runtime`
- 返回 detail runtime 聚合。

核心字段：
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
- `preflight_report`
- `director_brief`
- `visual_review`
- `retry_decisions`
- `qc_summary`
- `images`
- `export_zip_url`

`plan` 关键字段：
- `template_name`
- `canvas_aspect_ratio`
- `screens_per_page`
- `layout_mode`
- `global_style_anchor`
- `narrative`
- `total_pages`
- `pages[]`

`pages[]` 关键字段：
- `page_id`
- `title`
- `page_role`
- `layout_mode`
- `primary_headline_screen_id`
- `asset_strategy`
- `anchor_roles`
- `supplement_roles`
- `allow_generated_supporting_materials`
- `review_focus`
- `screens[]`

`copy_blocks[]` 关键字段：
- `page_id`
- `screen_id`
- `headline_level`
- `headline`
- `subheadline`
- `selling_points`
- `body_copy`
- `parameter_copy`
- `cta_copy`
- `notes`

`prompt_plan[]` 关键字段：
- `page_id`
- `page_title`
- `page_role`
- `layout_mode`
- `primary_headline_screen_id`
- `title_copy`
- `subtitle_copy`
- `selling_points_for_render`
- `layout_notes`
- `prompt`
- `negative_prompt`
- `references[]`
- `asset_strategy`
- `allow_generated_supporting_materials`
- `copy_strategy`
- `text_density`
- `should_render_text`
- `retryable`
- `target_aspect_ratio`
- `target_width`
- `target_height`

`preflight_report` 关键字段：
- `passed`
- `warnings`
- `available_roles`
- `missing_required_roles`
- `missing_optional_roles`
- `asset_summary`
- `recommended_page_roles`
- `notes`

`director_brief` 关键字段：
- `template_name`
- `global_style_anchor`
- `page_rhythm`
- `anchor_priority`
- `required_page_roles`
- `optional_page_roles`
- `ai_supplement_page_roles`
- `planning_notes`
- `material_notes`
- `constraints`

`visual_review` 关键字段：
- `overall_status`
- `summary`
- `pages[]`

`retry_decisions` 关键字段：
- `pages[]`
  - `page_id`
  - `page_role`
  - `should_retry`
  - `reason`
  - `strategies`

`qc_summary` 关键字段：
- `passed`
- `review_required`
- `warning_count`
- `failed_count`
- `issues[]`
- `checks[]`
- `pages[]`

`images[]` 关键字段：
- `image_id`
- `page_id`
- `title`
- `page_role`
- `status`
- `file_name`
- `image_url`
- `width`
- `height`
- `reference_roles`
- `error_message`
- `retry_count`

当前 detail V2 约束：
- 成品固定为 `3:4`
- 每页固定为 `single_screen_vertical_poster`
- 缺失 `tea_soup / scene_ref / bg_ref` 时允许 AI 在页内补足辅助素材
- 缺失 `dry_leaf / leaf_bottom` 时不会伪造证据页，而是改用其他页职责补位
- 渲染阶段允许单页失败并继续后续页面，最终结果可能是部分成功

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

## 5. detail 落盘结构
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

## 6. mock / real 模式

### 6.1 mock
- `ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE=mock`
- `ECOM_IMAGE_AGENT_IMAGE_PROVIDER_MODE=mock`

说明：
- mock text provider 返回稳定结构化 plan/copy/prompt
- mock image provider 复制预置样张到 `generated/`
- runtime、预览、下载、ZIP 仍走真实 detail graph 链路

### 6.2 real
- `ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE=real`
- `ECOM_IMAGE_AGENT_IMAGE_PROVIDER_MODE=real`
- `ECOM_IMAGE_AGENT_IMAGE_PROVIDER=banana2`

说明：
- 文本规划继续走统一 planning provider/router
- 图片渲染默认走 Banana2 provider
- 当 provider 抖动或单页失败时，detail 渲染会做页级重试，不再因为单页异常直接中断整条任务

## 7. 错误处理
- 参数校验失败：HTTP `422`
- 业务错误：HTTP `400`
- 未处理异常：HTTP `500`

detail 运行失败或部分失败时：
- `runtime.message` 优先返回 `task.json.error_message`
- 若任务进入 `review_required`，说明至少有一部分页面成功，但仍存在失败页或 QC 风险页
