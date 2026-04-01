# director_output contract

## 文件
- `director_output.json`
- Python 模型：
  - `backend/engine/domain/director_output.py`

## 顶层字段
- `product_summary`
- `category`
- `platform`
- `visual_style`
- `series_strategy`
- `background_style_strategy`
- `shots`

## `shots[]`
- `shot_id`
- `shot_role`
- `objective`
- `audience`
- `selling_point_direction`
- `scene`
- `composition`
- `visual_focus`
- `copy_goal`
- `copy_strategy`
- `text_density`
- `should_render_text`
- `compliance_notes`
- `product_scale_guideline`
- `subject_occupancy_ratio`
- `layout_hint`
- `typography_hint`
- `style_reference_policy`

## 关键语义
- `director_v2` 固定输出整套图的导演规划，而不是最终 render prompt。
- `series_strategy`
  - 描述整套 8 张图如何形成统一叙事。
  - 当前默认从包装识别，逐步过渡到细节、茶汤、礼赠与品质说明。
- `background_style_strategy`
  - 明确背景风格参考图只用于学习背景氛围、光线、色调、空间层次和材质语言。
  - 禁止替换产品主体，禁止提取其中任何文字。
- `selling_point_direction`
  - 表示该图位适合表达的卖点方向，不是最终图内广告文案。
- `copy_strategy`
  - `strong`：适合较明确的标题/副标题表达。
  - `light`：适合轻量文案。
  - `none`：该图位优先无广告文案。
- `text_density`
  - 当前使用 `medium / low / none`。
- `should_render_text`
  - `true`：该图位允许图内广告文字。
  - `false`：该图位应优先保留无字或极弱文字画面。
- `subject_occupancy_ratio`
  - 只有 `hero` 图要求硬规则，默认约为 `0.66`。
  - 非 `hero` 图可为空。
- `product_scale_guideline`
  - 用于在导演阶段明确主体尺寸策略。
  - `hero` 必须强调产品主体约占画面 `60%-70%`，即约 `2/3`。

## 自动文案策略
- `hero`
  - `copy_strategy=strong`
  - 强调品牌识别与产品识别
- `packaging_feature / process_or_quality`
  - `copy_strategy=strong`
  - 偏卖点转化和可信说明
- `gift_scene`
  - `copy_strategy=light`
  - 偏礼赠氛围和高级感
- `dry_leaf_detail / tea_soup / brewed_leaf_detail / lifestyle`
  - `copy_strategy=none`
  - 优先弱化文案或无文案

## 文案保护规则
- `copy_goal` 和 `compliance_notes` 必须体现以下约束：
  - 忽略参考图中的可见文案内容，不得转写、复用、概括为广告文案。
  - 产品参考图用于保持包装结构、材质、颜色与标签一致。
  - 背景风格参考图只用于背景氛围，不得替换产品包装。
  - 背景风格参考图中的文字内容一律无效。

## 使用位置
- `director_v2` 的结构化输出
- `prompt_refine_v2` 的直接输入
- 任务目录中的导演级调试产物
