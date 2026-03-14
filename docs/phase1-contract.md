# Phase 1 Contract

## 适用范围
本文档描述当前茶叶类 Phase 1 的主链路 contract，重点约束：
- 商品锁定分析
- 整组风格架构
- 固定五图图位规划
- 单张结构化 spec
- 向旧 prompt plan 的兼容映射

## 主链路核心 contract
当前四类核心产物已经正式接入 workflow state：

- `product_analysis`
  - 落盘：`product_analysis.json`
  - state：
    - `product_analysis`
    - `product_lock`，作为同一份分析结果的兼容别名
- `style_architecture`
  - 落盘：`style_architecture.json`
  - state：`style_architecture`
- `shot_plan`
  - 落盘：`shot_plan.json`
  - state：`shot_plan`
- `shot_prompt_specs`
  - 落盘：`shot_prompt_specs.json`
  - state：`shot_prompt_specs`

说明：
- 这四类文件不是仅供人工排查的旁路产物，而是后续节点可直接读取的正式 contract。
- `render_images` 当前阶段仍保留旧 prompt plan 执行链路，但已经要求 `shot_prompt_specs` 在 state 中可读。

## 茶叶类固定五图
当商品属于茶叶类族群时，`plan_shots` 必须固定输出：

1. `shot_01: hero_brand`
2. `shot_02: carry_action`
3. `shot_03: open_box_structure`
4. `shot_04: dry_leaf_detail`
5. `shot_05: tea_soup_experience`

模型只能补这些图位细节字段：
- `goal`
- `focus`
- `scene_direction`
- `composition_direction`
- `text_safe_zone_preference`

## `shot_plan.json`
每个 shot 至少包含：
- `shot_id`
- `shot_type`
- `title`
- `purpose`
- `composition_hint`
- `copy_goal`
- `goal`
- `focus`
- `scene_direction`
- `composition_direction`
- `preferred_text_safe_zone`
- `required_subjects`
- `optional_props`

## `style_architecture.json`
`style_director` 会基于：
- `product_analysis / product_lock`
- 平台
- 用户偏好

输出整组风格架构，至少包含：
- `platform`
- `user_preferences`
- `style_theme`
- `main_light_direction`
- `color_strategy`
- `lighting_strategy`
- `lens_strategy`
- `prop_system`
- `background_strategy`
- `text_strategy`
- `global_negative_rules`

## `shot_prompt_specs.json`
`shot_prompt_refiner` 会基于：
- `product_analysis / product_lock`
- `style_architecture`
- `shot_plan`
- `layout_plan`

输出每张图的结构化 spec。

每个 shot 至少包含：
- `shot_id`
- `shot_type`
- `goal`
- `product_lock`
- `subject_prompt`
- `package_appearance_prompt`
- `composition_prompt`
- `background_prompt`
- `lighting_prompt`
- `style_prompt`
- `quality_prompt`
- `negative_prompt`
- `layout_constraints`
- `render_constraints`
- `copy_intent`

其中 8 层 prompt 为：
- `subject_prompt`
- `package_appearance_prompt`
- `composition_prompt`
- `background_prompt`
- `lighting_prompt`
- `style_prompt`
- `quality_prompt`
- `negative_prompt`

## 强约束
`shot_prompt_refiner` 当前会固化：
- 首图：文字留白优先 `top_left / top_right / top`
- 动作图：文字放在动作反方向
- 开盒图：优先 `top / top_right`
- 茶干图：文字放背景留白区
- 茶汤图：文字优先上方留白
- 高饱和产品必须配低饱和背景
- 全组继承 `style_architecture` 的统一光线、镜头和道具体系

## `render_constraints`
当前至少包含：
- `generation_mode`
- `reference_image_priority`
- `consistency_strength`
- `allow_human_presence`
- `allow_hand_only`

说明：
- 它表达的是 spec 设计期的目标渲染策略。
- 它不直接替代 render 阶段的真实 provider 路由。

## image_edit 执行 contract 使用说明
当 `render_images` 判定当前 shot 走 `image_edit` 时，执行 prompt 当前按以下优先级组装：

1. `product_lock / product_analysis`
2. `style_architecture`
3. 当前 shot 的 `shot_prompt_spec`
4. `layout_constraints` 中的 `preferred_text_safe_zone`

其中 product lock 当前必须可被程序明确展开为：
- `must_preserve`
- `must_preserve_texts`
- `editable_regions`
- `must_not_change`

组装结构固定为：
- `Product Identity Lock`
- `Global Style Architecture`
- `Current Shot Direction`
- `Layout And Text Safe Zone`
- `Render Constraints`
- `Negative Rules`

如果缺少任一关键 contract，才回退到旧链路：
- 优先 `edit_instruction`
- 否则回退 `prompt`

## 落盘产物
茶叶类 Phase 1 当前任务目录至少包含：
- `task.json`
- `product_analysis.json`
- `style_architecture.json`
- `shot_plan.json`
- `copy_plan.json`
- `layout_plan.json`
- `shot_prompt_specs.json`
- `image_prompt_plan.json`
- `qc_report.json`

`finalize` 还会把这些核心 contract 的固定路径回写到 state：
- `artifact_paths.product_analysis`
- `artifact_paths.style_architecture`
- `artifact_paths.shot_plan`
- `artifact_paths.shot_prompt_specs`

## 茶叶 Phase 1 最低 QC 合同
当前 `run_qc` 对茶叶 Phase 1 还会执行三类图像层检查：
- `shot_completeness_check`
  - `final` 必须完整 5 张
- `product_consistency_check`
  - 至少检查 `image_edit` 是否真的带参考图，以及品牌/主色/主体锚点是否还在
- `shot_type_match_check`
  - 至少检查固定图位是否仍满足对应的最小语义约束
## 茶叶包装模板族
- 茶叶 Phase 1 现在不再把所有商品都强制视为礼盒。
- `product_analysis` 新增：
  - `package_template_family`
- 当前至少支持：
  - `tea_gift_box`
  - `tea_tin_can`
  - `tea_pouch`

### `tea_gift_box`
- 五图保持为：
  1. `shot_01: hero_brand`
  2. `shot_02: carry_action`
  3. `shot_03: open_box_structure`
  4. `shot_04: dry_leaf_detail`
  5. `shot_05: tea_soup_experience`

### `tea_tin_can`
- 当前用于圆柱金属罐、单罐装等更适合“包型细节 + 冲泡场景”的商品。
- 五图为：
  1. `shot_01: hero_brand`
  2. `shot_02: package_detail`
  3. `shot_03: dry_leaf_detail`
  4. `shot_04: tea_soup_experience`
  5. `shot_05: lifestyle_or_brewing_context`

### `tea_pouch`
- 当前沿用轻量袋装模板，五图结构与金属罐类似，但围绕袋装结构描述。
