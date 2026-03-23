# Workflow

## 当前主链路
项目默认且仅支持 v2 固定主链：

1. `ingest_assets`
2. `director_v2`
3. `prompt_refine_v2`
4. `render_images`
5. `run_qc`
6. `finalize`

不再保留：
- `analyze_product`
- `style_director`
- `plan_shots`
- `generate_copy`
- `generate_layout`
- `shot_prompt_refiner`
- `build_prompts`
- `overlay_text`
- `workflow_version` 分流

## 节点职责

### `ingest_assets`
- 校验上传素材是否存在
- 补齐素材宽高信息
- 产出 `uploaded_files`

### `director_v2`
- 基于任务信息和参考图生成 8 张图的导演规划
- 落盘 `director_output.json`

### `prompt_refine_v2`
- 把导演规划收口为逐图可执行 prompt
- 同时产出主标题、副标题和版式提示
- 落盘 `prompt_plan_v2.json`

### `render_images`
- 优先调用图片 provider 的 v2 生图能力
- 单张直出失败时，在节点内部执行 overlay fallback
- 每完成一张图，都会通过 workflow 进度回调回传局部结果
- UI 会立即展示当前已完成的图片，不需要等整批结束
- 落盘：
  - `generated/*`
  - `final/*`
  - `final_text_regions.json`

### `run_qc`
- 只执行最小闭环 QC：
  - 图数完整性
  - 文件存在性
  - overlay fallback 使用情况
- 落盘 `qc_report.json`

### `finalize`
- 根据 QC 更新任务状态
- 导出最终图片 ZIP 和完整任务包 ZIP

## 进度字段
任务和 workflow state 都会维护以下字段：
- `current_step`
- `current_step_label`
- `progress_percent`
- `error_message`

阶段映射：
- `ingest_assets`: `10%`
- `director_v2`: `30%`
- `prompt_refine_v2`: `55%`
- `render_images`: `85%`
- `run_qc`: `100%`
- `finalize`: `100%`

其中 `render_images` 节点内部还会把步骤文案细化成：
- `正在生成图片（1/8）`
- `正在生成图片（2/8）`
- ...

## UI 读取方式
- Streamlit 在执行 workflow 时通过 `on_progress` 回调读取最新状态
- `render_images` 节点内部会继续通过依赖注入的 `progress_callback` 按张推送局部结果
- 前端会同步刷新：
  - 进度条
  - 当前步骤文案
  - 最终图片网格
- 不展示节点日志、debug JSON 或中间产物详情

## 任务目录
每个任务落盘到：

- `outputs/tasks/{task_id}/`

主要产物：
- `task.json`
- `director_output.json`
- `prompt_plan_v2.json`
- `final_text_regions.json`
- `qc_report.json`
- `generated/*`
- `final/*`
- `exports/*`
