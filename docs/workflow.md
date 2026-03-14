# 工作流说明

## 当前主链路
当前 workflow 使用 LangGraph 固定编排，节点顺序为：

1. `ingest_assets`
2. `analyze_product`
3. `style_director`
4. `plan_shots`
5. `generate_copy`
6. `generate_layout`
7. `shot_prompt_refiner`
8. `build_prompts`
9. `render_images`
10. `overlay_text`
11. `run_qc`
12. `finalize`

说明：
- `style_director` 负责整组视觉风格架构，不负责单张 prompt。
- `plan_shots` 负责固定五图模板和图位细节。
- `shot_prompt_refiner` 负责把单张图位提升为结构化生成 spec。
- `build_prompts` 是兼容层，把结构化 spec 映射成旧链路可消费的 `ImagePromptPlan`。

## 主链路核心 contract
以下四类结构化产物现在已经正式接入 workflow state，不再只是“落盘后给人看”的旁路文件：

- `product_analysis`
  - 来源：`analyze_product`
  - state 字段：`product_analysis`
  - 兼容别名：`product_lock`
  - 落盘文件：`product_analysis.json`
- `style_architecture`
  - 来源：`style_director`
  - state 字段：`style_architecture`
  - 落盘文件：`style_architecture.json`
- `shot_plan`
  - 来源：`plan_shots`
  - state 字段：`shot_plan`
  - 落盘文件：`shot_plan.json`
- `shot_prompt_specs`
  - 来源：`shot_prompt_refiner`
  - state 字段：`shot_prompt_specs`
  - 落盘文件：`shot_prompt_specs.json`

当前接线关系如下：
- `analyze_product -> style_director`
  - `style_director` 直接读取 `product_analysis / product_lock`
- `style_director -> plan_shots`
  - `plan_shots` 可读取 `style_architecture`，用于记录和约束后续图位规划上下文
- `plan_shots -> shot_prompt_refiner`
  - `shot_prompt_refiner` 读取 `shot_plan`
- `shot_prompt_refiner -> render_images`
  - 当前阶段先保证 `render_images` 可以读取 `shot_prompt_specs`，不强制它彻底替代旧 prompt 链路

## `analyze_product`

### 节点职责
- 分析商品包装、材质、主色、标签结构和必须保留元素。
- 输出后续节点都会消费的 `ProductAnalysis`。

### 关键输出
- state：
  - `product_analysis`
  - `product_lock`
- 落盘：
  - `product_analysis.json`

说明：
- `product_lock` 是 `product_analysis` 的兼容别名，目的是让后续“结构化锁定”语义更直观，同时不破坏旧链路。

## `style_director`

### 节点位置
- 上游：`analyze_product`
- 下游：`plan_shots`

### 节点职责
- 生成整组图统一的视觉世界观和拍摄约束。
- 只输出组级风格，不输出单张图 prompt。

### 关键输出
- state：
  - `style_architecture`
- 落盘：
  - `style_architecture.json`

### 关键字段兜底
- `style_director` 现在会在程序层补齐以下关键字段，避免日志出现 `unspecified` 或 `-`：
  - `main_light_direction`
  - `color_strategy`
  - `background_strategy`
  - `lens_strategy`
- 即使 LLM 返回缺字段，最终落盘的 `style_architecture.json` 仍要求这些字段完整可用。

### 固化规则
- 高饱和产品配低饱和背景。
- 产品是唯一高饱和视觉中心。
- 全套图主光方向固定。
- 全套图镜头语言固定。
- 全套图道具体系统一。
- 文本安全区策略优先 `left/top/right upper area`。

## `plan_shots`

### 茶叶类 Phase 1 固定五图
当商品属于茶叶类族群时，`plan_shots` 固定输出：

1. `shot_01: hero_brand`
2. `shot_02: carry_action`
3. `shot_03: open_box_structure`
4. `shot_04: dry_leaf_detail`
5. `shot_05: tea_soup_experience`

模型只允许补这些字段：
- `goal`
- `focus`
- `scene_direction`
- `composition_direction`
- `text_safe_zone_preference`

### `shot_plan.json`
每个 shot 当前至少包含：
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

## `shot_prompt_refiner`

### 节点位置
- 上游：`generate_layout`
- 下游：`build_prompts`

### 节点职责
基于以下输入生成单张结构化 spec：
- `product_analysis / product_lock`
- `style_architecture`
- `shot_plan`
- `layout_plan`
- 用户偏好摘要

### `shot_prompt_specs.json`
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

### 8 层结构
每张图必须完整输出：
- `subject_prompt`
- `package_appearance_prompt`
- `composition_prompt`
- `background_prompt`
- `lighting_prompt`
- `style_prompt`
- `quality_prompt`
- `negative_prompt`

### 固化规则
- 首图：文字留白优先 `top_left / top_right / top`
- 动作图：文字放在动作反方向
- 开盒图：优先 `top / top_right`
- 茶干图：文字放背景留白区
- 茶汤图：文字优先上方留白
- 高饱和产品必须配低饱和背景
- 全组继承 `style_architecture` 的统一光线、镜头和道具系统

### `render_constraints`
当前是结构化对象，至少包含：
- `generation_mode`
- `reference_image_priority`
- `consistency_strength`
- `allow_human_presence`
- `allow_hand_only`

## `build_prompts`

### 当前定位
`build_prompts` 当前不是主导演节点，而是兼容层：
- 读取 `shot_prompt_specs`
- 映射成旧链路可消费的 `ImagePromptPlan`
- 兼容 `t2i / image_edit`

## `render_images`

### 当前阶段定位
- 仍然保留旧的 `ImagePromptPlan` 主执行链路。
- 已经能从 state 中读取 `product_lock / style_architecture / shot_prompt_specs`。
- 当 `generation_mode=image_edit` 时，优先基于三层 contract 组装最终执行 prompt。
- 如果缺少任一关键 contract，则回退到旧的 `edit_instruction / prompt`。
- 当前日志会明确打印：
  - 已接通的 contract 文件列表
  - `style_architecture` 是否已接入
  - `shot_prompt_specs` 是否可供 `render_images` 使用
  - 当前 shot 是否使用 `image_edit_contract_mode` 还是 `legacy_prompt_fallback`

### image_edit 执行 prompt 组装顺序
`render_images` 在 `image_edit` 模式下按以下结构组装执行 prompt，而不是简单把字段拼成一大段散文：

1. `Product Identity Lock`
   - 保留包装主体、品牌文字、标签结构、主色、材质观感
   - 同时显式展开：
     - `must_preserve`
     - `must_preserve_texts`
     - `editable_regions`
     - `must_not_change`
2. `Global Style Architecture`
   - 整组风格主题、色彩策略、光线策略、镜头策略、道具体系、背景策略、文字策略
3. `Current Shot Direction`
   - 当前 shot 的 goal、subject、package appearance、composition、background、lighting、style、quality
4. `Layout And Text Safe Zone`
   - 文字安全区、主体避让、文本层数、文案意图
5. `Render Constraints`
   - `generation_mode / reference_image_priority / consistency_strength / allow_human_presence / allow_hand_only`
6. `Negative Rules`
   - 组合 `style_architecture.global_negative_rules` 和 shot 级 `negative_prompt`

说明：
- 这套组装只影响 `image_edit` 主路径。
- `t2i` 仍然兼容旧 prompt plan。
- 参考图链路仍由 provider 路由层控制，不在这里替换。
- `render_images` 日志中的 `keep_subject_rules / editable_regions` 现在会先做清洗，避免出现 tuple 字符串化内容。

## 落盘产物
当前任务目录核心产物包括：
- `task.json`
- `product_analysis.json`
- `style_architecture.json`
- `shot_plan.json`
- `copy_plan.json`
- `layout_plan.json`
- `shot_prompt_specs.json`
- `image_prompt_plan.json`
- `qc_report.json`
- `final_text_regions.json`
- `preview_text_regions.json`

`finalize` 现在会把以下信息回写到 state，便于 UI 和调试直接读取：
- `artifact_paths.product_analysis`
- `artifact_paths.style_architecture`
- `artifact_paths.shot_plan`
- `artifact_paths.shot_prompt_specs`

## 调试定位建议
如果单张图效果不对，建议按这个顺序看：

1. `product_analysis.json`
2. `style_architecture.json`
3. `shot_plan.json`
4. `layout_plan.json`
5. `shot_prompt_specs.json`
6. `image_prompt_plan.json`
7. `render_images` 日志中的 contract readiness、`execution_source` 和 execution prompt 摘要

如果怀疑接线问题，先看日志中是否出现：
- `connected_contract_files=[...]`
- `style_architecture_connected=true`
- `shot_prompt_specs_available_for_render=true`
- `execution_source=image_edit_contract_mode`

## `run_qc`

### 当前阶段定位
- 仍然保留原有工程检查和文字可读性检查。
- 新增茶叶 Phase 1 图像层合同检查：
  - `shot_completeness_check`
  - `product_consistency_check`
  - `shot_type_match_check`
- 新增文字层聚合检查：
  - `text_safe_zone_check`
  - `text_readability_check`

### 茶叶 Phase 1 图像层 QC 规则
- `shot_completeness_check`
  - `final` 必须完整 5 张，否则直接 `failed`
  - `preview` 可放宽，但必须在报告中明确是 `preview`
- `product_consistency_check`
  - 轻量检查 `image_edit` 是否带参考图
  - 检查 generation mode 是否一致
  - 检查品牌文字、主色、中心主体信号是否还在
- `shot_type_match_check`
  - 用 `shot_plan + shot_prompt_specs` 做 metadata-based 匹配
  - 检查每个固定图位是否仍满足最小语义约束

### `qc_report` 当前关键字段
- `checks`
  - 保留原有明细列表
- `shot_completeness_check`
- `product_consistency_check`
- `shot_type_match_check`
- `text_safe_zone_check`
- `text_readability_check`

这些根字段的每项至少包含：
- `status`
- `details`
- `related_shot_id`

### overlay_text 到 run_qc 的文字区域接线
- `overlay_text` 当前会把每个 shot 的实际渲染文本块摘要写入 `text_render_reports`
- 同时会把这些真实文本区域落盘到：
  - `final_text_regions.json`
  - `preview_text_regions.json`
- `run_qc` 会优先读取这些实际文本区域做：
  - 文字安全区检查
  - 文案可读性检查
- 如果 state 里没有 `text_render_reports`，会继续尝试从对应 JSON 恢复
- 只有在两者都不存在时，才回退到 `layout_plan.blocks`
## QC 补充说明：商品一致性证据
- `run_qc` 中的 `product_consistency_check` 已改为“有证据才能通过”。
- `details` 和 `qc_report.product_consistency_check` 摘要现在会带出：
  - `evidence_completeness=full|partial|missing`
  - `evidence_issues`
  - `decision_reason`
- 这意味着：
  - 品牌文字锚点、OCR 有效文本、主色证据缺失时，不能再默认 `passed`
  - `image_edit` 路径如果缺少 `reference_asset_ids`，会进一步拉高为 `warning/failed`
## 茶叶模板分流补充
- `plan_shots` 不再把所有茶叶都强制套用礼盒五图模板。
- 当前至少支持三种包装模板族：
  - `tea_gift_box`
  - `tea_tin_can`
  - `tea_pouch`
- `analyze_product` 会把模板判断结果写入 `product_analysis.package_template_family`。
- `plan_shots` 会根据这个字段分流：
  - `tea_gift_box`：保留 `carry_action / open_box_structure`
  - `tea_tin_can`：改为 `package_detail / lifestyle_or_brewing_context`
  - `tea_pouch`：走轻量袋装场景模板
- 这一步不改变 `shot_plan.json` 的字段结构，只改变固定五图的 `shot_type` 组合。
