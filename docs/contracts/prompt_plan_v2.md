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
- `layout_hint`
- `aspect_ratio`
- `image_size`

## 约束
- `title_copy` 建议 `4-8` 字
- `subtitle_copy` 建议 `8-15` 字
- 默认 `aspect_ratio=1:1`
- 默认 `image_size=2K`

## 使用位置
- `prompt_refine_v2` 的最终输出
- `render_images` 的直接输入
- overlay fallback 的文案与版式输入
