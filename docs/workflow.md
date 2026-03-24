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

## 输入层

### UI 表单字段
- 基础：
  - `brand_name`
  - `product_name`
  - `platform`
  - `shot_count`
  - `aspect_ratio`
  - `image_size`
- 图内文案控制：
  - `copy_mode`
  - `title_text`
  - `subtitle_text`
  - `selling_points`
- 风格控制：
  - `style_type`
  - `style_preferences`
  - `custom_elements`
  - `avoid_elements`

### 上传素材分类
- `white_bg`
  - 外包装白底图，作为产品保真主参考。
- `product_references`
  - 可选，用于展开图、细节图、内部结构图。
- `background_style_references`
  - 可选，只用于学习背景氛围、色调和场景语言。

## 节点职责

### `ingest_assets`
- 校验上传素材是否存在。
- 补齐素材宽高信息。
- 产出 `uploaded_files`。
- 保留素材类型：
  - `WHITE_BG`
  - `DETAIL`
  - `BACKGROUND_STYLE`

### `director_v2`
- 基于任务信息和参考图生成 8 张图的导演规划。
- 融合：
  - 用户文案模式
  - 风格类型
  - 风格偏好
  - 自定义元素
  - 避免元素
  - 用户卖点
- 明确产品参考图与背景风格参考图的不同用途。
- 对 `hero` 写入主体比例硬规则：
  - `subject_occupancy_ratio=0.66`
  - `product_scale_guideline` 要求产品主体约占画面 `2/3`
- 落盘 `director_output.json`。

### `prompt_refine_v2`
- 把导演规划收口为逐图可执行 prompt。
- 输出：
  - `render_prompt`
  - `title_copy`
  - `subtitle_copy`
  - `selling_points_for_render`
  - `layout_hint`
  - `typography_hint`
  - `copy_source`
  - `subject_occupancy_ratio`
- 文案优先级：
  - 用户输入优先
  - 用户未输入时才自动生成
  - `manual` 模式不自动补空字段
- 落盘 `prompt_plan_v2.json`。

### `render_images`
- 优先调用图片 provider 的 v2 生图能力。
- 最终 prompt 组装时再次补强：
  - 禁止参考图文案泄漏
  - 产品参考图与背景风格参考图分流
  - 显式下发标题、副标题、卖点、版式提示、字体层级、主体比例
- 单张直出失败时，在节点内部执行 overlay fallback。
- overlay fallback 仍属于新流程内部行为，不回退为独立旧节点。
- 每完成一张图，都会通过 workflow 进度回调回传局部结果。
- 落盘：
  - `generated/*`
  - `final/*`
  - `final_text_regions.json`

### `run_qc`
- 只执行最小闭环 QC：
  - 图数完整性
  - 文件存在性
  - overlay fallback 使用情况
- 落盘 `qc_report.json`。

### `finalize`
- 根据 QC 更新任务状态。
- 导出最终图片 ZIP 和完整任务包 ZIP。

## 参考图文案保护
- 当前主链禁止把参考图可见文字转成广告标题、副标题、卖点、背景大字、宣传语。
- 参考图文字只允许作为包装自身标签一致性的一部分被保留。
- 若用户没有输入标题、副标题、卖点，只能由当前新流程自动生成，不允许从参考图文字中提炼。

## Hero 构图规则
- 只有 `hero` 图执行主体 `2/3` 占比硬规则。
- 具体语义：
  - 产品优先
  - 文案次之
  - 装饰元素最弱
  - 不允许因为留白过大导致商品过小
- 非 `hero` 图保持正常商业审美，不强制复用首图比例。

## Fallback 语义
- 触发位置：`render_images` 节点内部。
- 当前触发条件：
  - 图片 provider 的 v2 直出失败
  - provider 不支持 v2 直出
  - v2 返回空图
- fallback 行为：
  - 用兼容 prompt 先生成底图
  - 再由 Pillow 中文后贴字补标题和副标题
- `final_text_regions.json` 会记录每张图的：
  - `overlay_applied`
  - `fallback_used`
  - `fallback_reason`
  - `copy_source`
  - `selling_points_for_render`
  - `selling_points_boxes`

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
- Streamlit 在执行 workflow 时通过 `on_progress` 回调读取最新状态。
- `render_images` 节点内部会继续通过依赖注入的 `progress_callback` 按张推送局部结果。
- 前端会同步刷新：
  - 进度条
  - 当前步骤文案
  - 最终图片网格
- 不展示节点日志、debug JSON 或中间产物详情。

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
