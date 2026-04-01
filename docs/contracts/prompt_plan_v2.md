# prompt_plan_v2 contract

## 文件
- `prompt_plan_v2.json`
- Python 模型：
  - `backend/engine/domain/prompt_plan_v2.py`

## 顶层字段
- `shots`

## `shots[]`
- `shot_id`
- `shot_role`
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
- `aspect_ratio`
- `image_size`

## 约束
- `copy_strategy`
  - `strong`：需要较明确的标题/副标题结构。
  - `light`：只允许轻量文案。
  - `none`：优先无广告文案。
- `text_density`
  - 当前使用 `medium / low / none`。
- `should_render_text`
  - `true`：允许渲染广告文字。
  - `false`：该图位优先不渲染广告文字。
- `title_copy`
  - 系统自动生成时建议 `4-8` 字。
  - 当前 hero 标题允许使用品牌名或商品名作为锚点，必要时可接受 3 字中文标题。
- `subtitle_copy`
  - 系统自动生成时建议 `8-15` 字。
- `selling_points_for_render`
  - 当前最多保留 1-2 条短语。
  - 仅用于适合带字的图位。
- `copy_source`
  - `system_auto`：完全由系统自动生成。
  - `system_brand_anchor`：自动文案中利用了品牌名或商品名锚点。
- `subject_occupancy_ratio`
  - `hero` 默认约 `0.66`。
  - 非 `hero` 图可为空。
- 默认 `aspect_ratio=1:1`
- 默认 `image_size=2K`

## 自动带字策略
- `hero`
  - 强文案，允许主标题 + 副标题
- `packaging_feature / process_or_quality`
  - 适度带字，偏卖点说明
- `gift_scene`
  - 轻量带字，偏礼赠氛围
- `dry_leaf_detail / tea_soup / brewed_leaf_detail / lifestyle`
  - 默认 `should_render_text=false`
  - 标题、副标题、卖点应为空

## render_prompt 硬约束
- 必须保留包装结构、品牌识别、标签层级。
- 必须显式写出产品参考图与背景风格参考图的边界。
- 必须强调：
  - 忽略参考图中的可见文案内容，不得将其转写、复用、概括为广告文案。
  - 产品参考图只用于产品保真。
  - 背景风格参考图只用于背景氛围。
- `hero` 图必须明确主体约占画面 `2/3`。
- `should_render_text=false` 的图位必须显式弱化或取消广告文字。

## 使用位置
- `prompt_refine_v2` 的最终输出
- `render_images` 的直接输入
- overlay fallback 的文案与版式输入
