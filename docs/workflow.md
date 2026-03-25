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
  - `style_type`
  - `style_notes`
- 高级设置：
  - `shot_count`
  - `aspect_ratio`
  - `image_size`

### UI 不再暴露的字段
- `title_text`
- `subtitle_text`
- `selling_points`
- `copy_mode`
- `style_preferences`
- `custom_elements`
- `avoid_elements`
- 任何逐张图文案输入

### 上传素材分类
- `white_bg`
  - 外包装白底图，作为产品保真主参考。
- `product_references`
  - 可选，用于展开图、细节图、内部结构图、材质图。
- `background_style_references`
  - 可选，只用于学习背景氛围、光线、色调、场景语言和材质语言。
  - 不允许提取广告文案。

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
- 基于任务高层意图和参考图生成整套图导演规划。
- 融合：
  - `style_type`
  - `style_notes`
  - 产品参考图
  - 背景风格参考图
- 自动决定每张图的：
  - 图位目标
  - 卖点方向
  - `copy_strategy`
  - `text_density`
  - `should_render_text`
  - `layout_hint`
  - `typography_hint`
- 明确整套图策略：
  - `series_strategy`
  - `background_style_strategy`
- 对 `hero` 写入主体比例硬规则：
  - `subject_occupancy_ratio=0.66`
  - `product_scale_guideline` 要求产品主体约占画面 `2/3`
- 落盘 `director_output.json`。

### `prompt_refine_v2`
- 把导演规划收口为逐图可执行 prompt。
- 输出：
  - `render_prompt`
  - `copy_strategy`
  - `text_density`
  - `should_render_text`
  - `title_copy`
  - `subtitle_copy`
  - `selling_points_for_render`
  - `layout_hint`
  - `typography_hint`
  - `copy_source`
  - `subject_occupancy_ratio`
- 文案规则：
  - 不再接收用户逐条输入文案
  - 可适度利用 `brand_name / product_name`
  - 其余由系统自动生成
  - 默认不是每张图都带字
- 角色级策略：
  - `hero`：强文案
  - `packaging_feature / process_or_quality`：适量文案
  - `gift_scene`：轻量文案
  - `dry_leaf_detail / tea_soup / brewed_leaf_detail / lifestyle`：少字或无字
- 落盘 `prompt_plan_v2.json`。

### `render_images`
- 优先调用图片 provider 的 v2 生图能力。
- 最终 prompt 组装时再次补强：
  - 禁止参考图文案泄漏
  - 产品参考图与背景风格参考图分流
  - 显式下发 `copy_strategy / text_density / should_render_text`
  - `hero` 继续强调主体 2/3
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

## 自动文案策略
- 当前产品定位是“整套电商产品图生成器”，不是“手工配置每张图文案的编辑器”。
- 生成逻辑遵循：
  - `hero`
    - 可带主标题 + 短副标题
    - 产品主体约占画面 `2/3`
  - `packaging_feature / process_or_quality / gift_scene`
    - 可带适量文案
  - `dry_leaf_detail / tea_soup / brewed_leaf_detail / lifestyle`
    - 优先少字或无字
- 文案不来自用户逐条填写，也不来自参考图可见文字。

## 参考图文案保护
- 当前主链禁止把参考图可见文字转成广告标题、副标题、卖点、背景大字、宣传语。
- 参考图文字只允许作为包装自身标签一致性的一部分被保留。
- 背景风格参考图中的文字内容一律无效。

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
  - `copy_strategy`
  - `text_density`
  - `should_render_text`
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
