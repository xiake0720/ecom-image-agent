# director_output contract

## 文件
- `director_output.json`
- Python 模型：
  - `src/domain/director_output.py`

## 顶层字段
- `product_summary`
- `category`
- `platform`
- `visual_style`
- `shots`

## `shots[]`
- `shot_id`
- `shot_role`
- `objective`
- `audience`
- `selling_points`
- `scene`
- `composition`
- `visual_focus`
- `copy_direction`
- `compliance_notes`
- `product_scale_guideline`
- `subject_occupancy_ratio`
- `layout_hint`
- `typography_hint`

## 关键语义
- `director_v2` 固定输出 8 张图位规划。
- `subject_occupancy_ratio`
  - 只有 `hero` 图要求硬规则，默认约为 `0.66`。
  - 非 `hero` 图可为空，不强制复制首图比例。
- `product_scale_guideline`
  - 用于在导演阶段明确主体尺寸策略。
  - `hero` 必须强调产品主体约占画面 `60%-70%`，即约 `2/3`。
- `layout_hint`
  - 描述文字大致区域，不允许遮挡关键产品区。
- `typography_hint`
  - 描述标题、副标题、卖点的层级强弱，供 `prompt_refine_v2` 继续收口。

## 文案保护规则
- `copy_direction` 和 `compliance_notes` 必须体现以下约束：
  - 忽略参考图中的可见文案内容，不得转写、复用、概括为广告文案。
  - 参考图只用于学习包装结构、颜色、材质、陈列方式、氛围与风格，不用于提取广告文字。
  - 产品参考图用于保持包装结构、材质、颜色与标签一致。
  - 背景风格参考图只用于背景氛围，不得替换产品包装。

## 使用位置
- `director_v2` 的结构化输出
- `prompt_refine_v2` 的直接输入
- 任务目录中的导演级调试产物
