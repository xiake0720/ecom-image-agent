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
<<<<<<< HEAD
=======
    - `analyze_text_anchor_source`
    - `analyze_text_anchor_count`
    - `analyze_extracted_text_anchors`
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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

<<<<<<< HEAD
## 茶叶类固定五图
当商品属于茶叶类族群时，`plan_shots` 必须固定输出：

1. `shot_01: hero_brand`
2. `shot_02: carry_action`
3. `shot_03: open_box_structure`
4. `shot_04: dry_leaf_detail`
5. `shot_05: tea_soup_experience`
=======
## `product_analysis.json`
`analyze_product` 当前除视觉结构字段外，还必须尽量提取稳定包装文字锚点。

关键字段：
- `locked_elements`
  - 偏包装轮廓、标签位置、版式和视觉结构
- `must_preserve_texts`
  - 偏真实包装文字锚点，最多 `1~5` 个
- `text_anchor_status`
  - `readable / uncertain / unreadable`
- `text_anchor_source`
  - `provider / fallback / none`
- `text_anchor_notes`
  - 当文字不可稳定识别时，用简短说明解释原因

文字锚点提取优先级：
1. 品牌名
2. 产品名
3. 香型 / 口味 / 副品名
4. 净含量
5. 清晰可见的英文副标

程序级兜底：
- 如果 provider 返回的 `must_preserve_texts` 为空，会从 `visual_identity.must_preserve / locked_elements` 中筛短文本锚点
- 只保留适合 OCR 对比的短文本，不把视觉结构描述误写成文字锚点
- 如果仍拿不到锚点，允许 `must_preserve_texts=[]`，但必须显式写出 `text_anchor_status` 和 `text_anchor_source=none`

## 茶叶类固定五图
当商品属于茶叶类族群时，`plan_shots` 不再只按“茶叶”一个条件输出模板，而是同时看两层信息：

1. `package_template_family`
2. `asset_completeness_mode`

其中：
- `package_template_family`
  - 当前至少支持 `tea_gift_box / tea_tin_can / tea_pouch`
- `asset_completeness_mode`
  - `packshot_only`
    - 只有包装图，没有可靠细节图
  - `packshot_plus_detail`
    - 有包装图，同时有茶干或细节图

模型仍然只能补这些图位细节字段：
- `goal`
- `focus`
- `scene_direction`
- `composition_direction`
- `text_safe_zone_preference`

不能新增、删除或替换固定五图 slot。
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c

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

<<<<<<< HEAD
=======
## `copy_plan.json`
`generate_copy` 会基于：
- `task`
- `product_analysis`
- `shot_plan`

输出每个 shot 的结构化中文贴图文案。

每个 item 至少包含：
- `shot_id`
- `title`
- `subtitle`
- `bullets`
- `cta`

当前 contract 约束：
- `title`
  - 优先 `8~14` 个中文字符，最长 `18`
- `subtitle`
  - 优先 `8~16` 个中文字符，最长 `22`
- `bullets`
  - 默认留空
- `cta`
  - 默认关闭
- 内容只能使用输入中可确认的信息，不允许创造新的品牌名、系列名、虚构 slogan。

程序层会在落盘前做归一化：
- 超长文案会自动缩短或回退为 shot-aware fallback 文案
- 品牌锚点不合法时，不允许把原文案直接透传到 `overlay_text`
- mock 与 fallback 也必须输出适合 1440x1440 中文贴图的短版文案

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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
<<<<<<< HEAD
=======
- 每个 `shot_type` 都会先映射到 `ShotExecutionProfile`，再由它生成 `subject / composition / background / lighting / negative / render_constraints`。
- 茶叶 `tea_tin_can` 模板下的 `package_detail / dry_leaf_detail / tea_soup_experience / lifestyle_or_brewing_context / package_in_brewing_context` 都有显式排他规则，避免退化成 hero packshot。
- `hero_brand` 强制 full package hero subject；`package_detail` 强制近距离细节图；`dry_leaf_detail` 强制茶干前景第一主体；`tea_soup_experience` 强制茶汤与杯具第一主体；context 类图强制出现冲泡道具或场景锚点。
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c

## `render_constraints`
当前至少包含：
- `generation_mode`
- `reference_image_priority`
- `consistency_strength`
<<<<<<< HEAD
=======
- `product_lock_level`
- `editable_region_strategy`
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
- `allow_human_presence`
- `allow_hand_only`

说明：
- 它表达的是 spec 设计期的目标渲染策略。
- 它不直接替代 render 阶段的真实 provider 路由。
<<<<<<< HEAD
=======
- `product_lock_level` 当前分为：
  - `strong_product_lock`
  - `medium_product_lock`
  - `anchor_only_product_lock`
- `editable_region_strategy` 用来约束 provider 在 image_edit 模式下更偏向背景扩展、细节裁切、茶干前景、茶汤前景或场景构建哪类可编辑区域。
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c

## image_edit 执行 contract 使用说明
当 `render_images` 判定当前 shot 走 `image_edit` 时，执行 prompt 当前按以下优先级组装：

<<<<<<< HEAD
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

=======
1. 当前 shot 的差异化目标
   - `shot_type / goal / allowed_scene_change_level`
2. 当前 shot 的执行分镜规则
   - `primary_subject / secondary_subject`
   - `forbidden_regression_pattern`
   - shot-specific composition/background/lighting/quality 约束
3. `editable_regions_final`
4. `product_lock / product_analysis`
5. `style_architecture`
6. `layout_constraints` 中的 `preferred_text_safe_zone`

其中 product lock 当前必须可被程序明确展开为：
- `must_preserve_visuals`
- `must_preserve_texts`
- `must_not_change`

组装结构固定为：
- `Task Type And Current Shot Objective`
- `Shot Differentiation Rules`
- `Subject Hierarchy`
- `Allowed Editable Regions`
- `Product Identity Lock`
- `Global Style Architecture`
- `Layout And Text Safe Zone`
- `Negative Rules`

`shot_prompt_refiner` 当前还会为每个 shot 产生日志摘要：
- `primary_subject`
- `secondary_subject`
- `allowed_scene_change_level`
- `forbidden_regression_pattern`
- `editable_regions_final`

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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
<<<<<<< HEAD
=======
  - 当前优先消费 `product_analysis.must_preserve_texts`
  - 会在 `details` 中显式写出 `text_anchor_source / text_anchor_status / text_anchor_count`
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
- `shot_type_match_check`
  - 至少检查固定图位是否仍满足对应的最小语义约束
## 茶叶包装模板族
- 茶叶 Phase 1 现在不再把所有商品都强制视为礼盒。
- `product_analysis` 新增：
  - `package_template_family`
<<<<<<< HEAD
=======
  - `asset_completeness_mode`
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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
<<<<<<< HEAD
- 五图为：
=======
- `packshot_plus_detail` 五图为：
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
  1. `shot_01: hero_brand`
  2. `shot_02: package_detail`
  3. `shot_03: dry_leaf_detail`
  4. `shot_04: tea_soup_experience`
  5. `shot_05: lifestyle_or_brewing_context`
<<<<<<< HEAD

### `tea_pouch`
- 当前沿用轻量袋装模板，五图结构与金属罐类似，但围绕袋装结构描述。
=======
- `packshot_only` 五图为：
  1. `shot_01: hero_brand`
  2. `shot_02: package_detail`
  3. `shot_03: label_or_material_detail`
  4. `shot_04: package_with_leaf_hint`
  5. `shot_05: package_in_brewing_context`

说明：
- `packshot_only` 下不允许再硬生成标准 `dry_leaf_detail / tea_soup_experience`
- 这一步是为了避免只有一张包装图时，五图只是同一张 packshot 的伪细节变体

### `tea_pouch`
- 当前沿用轻量袋装模板，五图结构与金属罐类似，但围绕袋装结构描述。

## 分流日志与调试字段
`analyze_product` 和 `plan_shots` 当前必须显式输出：
- `package_template_family`
- `asset_completeness_mode`
- `selected_main_asset_id`
- `selected_detail_asset_id`
- `chosen_template_name`

其中：
- `asset_completeness_mode` 会写入 `product_analysis.json`
- `chosen_template_name` 当前示例：
  - `tea_tin_can_packshot_only`
  - `tea_tin_can_packshot_plus_detail`
  - `tea_gift_box_default`

## 本次补充：Phase 1 结果图 QC contract

茶叶 Phase 1 当前在 `run_qc` 中除了原有工程检查，还会执行更接近最终结果图的轻量商业可用性检查：

- `text_readability_check`
  - 读取真实叠字后的 `used_font_size / merged_text_region`
  - 商用最小可读字号固定为：
    - `title >= 40`
    - `subtitle >= 24`
    - `bullets >= 22`
    - `cta >= 22`
- `product_consistency_check`
  - 优先使用 `must_preserve_texts` 做 OCR 对比
  - `details` 中显式输出：
    - `visual_consistency`
    - `text_anchor_consistency`
    - `evidence_completeness`
- `shot_type_match_check`
  - 不再只看 `shot_type` metadata
  - 对 `package_detail / dry_leaf_detail / tea_soup_experience / lifestyle_or_brewing_context / package_in_brewing_context` 增加结果图规则
- `visual_shot_diversity_check`
  - 新增组图多样性预警
  - 用于识别五张图是否仍退化成相似 hero packshot

`qc_report.json` 根级摘要字段当前至少包括：
- `shot_completeness_check`
- `product_consistency_check`
- `shot_type_match_check`
- `visual_shot_diversity_check`
- `text_safe_zone_check`
- `text_readability_check`
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
