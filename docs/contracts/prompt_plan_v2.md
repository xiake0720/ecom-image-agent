# prompt_plan_v2 contract

## 文件
- `prompt_plan_v2.json`
- Python 模型：
  - `src/domain/prompt_plan_v2.py`

## 顶层字段
- `shots`

## `shots[]` 字段
- `shot_id`
- `shot_role`
- `render_prompt`
- `title_copy`
- `subtitle_copy`
- `layout_hint`
- `aspect_ratio`
- `image_size`

## 业务建议
- `title_copy`
  - 建议 4 到 8 字
- `subtitle_copy`
  - 建议 8 到 15 字
- `aspect_ratio`
  - 默认 `1:1`
- `image_size`
  - 默认 `2K`

## 用途
- `prompt_refine_v2` 的稳定输出
- `render_images` v2 分支的直接输入
- `overlay_text` fallback 的复用输入
