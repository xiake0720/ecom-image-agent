# prompt_plan_v2 contract

## 文件
- `prompt_plan_v2.json`
- Python 模型：
  - `src/domain/prompt_plan_v2.py`

## 顶层字段
- `shots`

## `shots[]`
- `shot_id`
- `shot_role`
- `render_prompt`
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
- `title_copy`
  - 自动生成时建议 `4-8` 字。
  - 用户手动输入时按原文保留，不做改写。
- `subtitle_copy`
  - 自动生成时建议 `8-15` 字。
  - 用户手动输入时按原文保留，不做改写。
- `selling_points_for_render`
  - 支持多条卖点。
  - 用户输入时优先使用用户原文。
- `copy_source`
  - `user`：当前图位文案来自用户输入。
  - `auto`：当前图位文案由新流程自动生成。
  - `manual_empty`：用户选择 `manual`，但该字段未提供，因此不自动补位。
- `subject_occupancy_ratio`
  - `hero` 默认约 `0.66`。
  - 非 `hero` 图可为空。
- 默认 `aspect_ratio=1:1`
- 默认 `image_size=2K`

## render_prompt 硬约束
- 必须保留包装结构、品牌识别、标签层级。
- 必须显式写出标题、副标题、卖点、文字区域和层级提示。
- 必须强调：
  - 忽略参考图中的可见文案内容，不得将其转写、复用、概括为广告文案。
  - 产品参考图只用于产品保真。
  - 背景风格参考图只用于背景氛围。
- `hero` 图必须明确主体约占画面 `2/3`。

## 使用位置
- `prompt_refine_v2` 的最终输出
- `render_images` 的直接输入
- overlay fallback 的文案与版式输入
