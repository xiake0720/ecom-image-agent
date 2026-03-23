<<<<<<< HEAD
# Workflow 说明

## 当前状态
- 项目已支持 `v1 / v2` 双流程。
- `v1` 保留旧链路和旧 schema。
- `v2` 围绕“天猫茶叶电商图 8 张、图内文案、可 overlay fallback”收口。
- `build_workflow()` 会根据 `state.workflow_version` 或 `settings.workflow_version` 分流。

## v1 链路
=======
# 工作流说明

## 当前主链路
当前 workflow 使用 LangGraph 固定编排，节点顺序为：

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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

<<<<<<< HEAD
## v2 链路
1. `ingest_assets`
2. `director_v2`
3. `prompt_refine_v2`
4. `render_images`
5. `overlay_text`
6. `run_qc`
7. `finalize`

说明：
- v2 中的 `overlay_text` 是 fallback 节点，不是默认全量贴字节点。
- v2 优先尝试图片模型直接生成图内文案。

## v2 节点职责

### `director_v2`
- 输入：
  - `task`
  - `assets`
  - 可选 `product_analysis`
- 输出：
  - `state.director_output`
  - `director_output.json`
- 作用：
  - 生成 8 张图的导演级图组规划。

### `prompt_refine_v2`
- 输入：
  - `director_output`
- 输出：
  - `state.prompt_plan_v2`
  - `prompt_plan_v2.json`
- 作用：
  - 生成每张图最终可执行的 `render_prompt`
  - 同时产出 `title_copy / subtitle_copy / layout_hint / aspect_ratio / image_size`

### `render_images`
- v1：
  - 读取 `image_prompt_plan`
- v2：
  - 读取 `prompt_plan_v2`
  - 优先图内直出文字
  - 单张图失败时写出：
    - `needs_overlay_fallback`
    - `overlay_fallback_candidates`
  - 结果写回：
    - `generation_result`
    - `generation_result_v2`

### `overlay_text`
- v1：
  - 保持原有全量 Pillow 后贴字
- v2：
  - 仅处理 `overlay_fallback_candidates`
  - 非 fallback 图片直接透传到最终结果目录
  - 写出：
    - `text_render_reports`
    - `final_text_regions.json`
    - `preview_text_regions.json`

### `run_qc`
- v1：
  - 保持原有工程检查和文字可读性检查
- v2：
  - 以 `prompt_plan_v2` 为目标图位集合
  - OCR 对比 `title_copy / subtitle_copy`
  - 复用现有产品一致性检查
  - 必要时补充 `overlay_fallback_candidates`
  - 结果写回：
    - `qc_report`
    - `qc_report_v2`

## 关键 state 字段

### v1 保留字段
- `style_architecture`
- `shot_plan`
- `copy_plan`
- `layout_plan`
- `shot_prompt_specs`
- `image_prompt_plan`
- `generation_result`
- `qc_report`

### v2 新增字段
- `workflow_version`
- `director_output`
- `prompt_plan_v2`
- `generation_result_v2`
- `qc_report_v2`
- `direct_text_on_image`
- `enable_overlay_fallback`
- `needs_overlay_fallback`
- `overlay_fallback_candidates`
- `text_render_reports`
- `preview_qc_report`

## 任务和产物

### `task.json`
- 新增：
  - `workflow_version`
  - `enable_overlay_fallback`

### v2 新增产物
- `director_output.json`
- `prompt_plan_v2.json`

### 通用产物
- `generated/` 或 `generated_preview/`
- `final/` 或 `final_preview/`
- `qc_report.json` 或 `qc_report_preview.json`
- `final_text_regions.json` 或 `preview_text_regions.json`
- `exports/`

## UI 默认项
- `workflow_version = v2`
- `platform = tmall`
- `shot_count = 8`
- `enable_overlay_fallback = true`

## 调试字段
- `workflow_version`
- `render_generation_mode`
- `render_reference_asset_ids`
- `needs_overlay_fallback`
- `overlay_fallback_candidates`
- `prompt_plan_v2_available_for_render`

## 本地验证
```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit -q
.\.venv\Scripts\python.exe -m compileall src
```
=======
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
- 优先提取真实包装文字锚点，供后续 `image_edit` 锁品和 `QC / OCR` 对比使用。
- 输出后续节点都会消费的 `ProductAnalysis`。

### 关键输出
- state：
  - `product_analysis`
  - `product_lock`
  - `analyze_text_anchor_source`
  - `analyze_text_anchor_count`
  - `analyze_extracted_text_anchors`
- 落盘：
  - `product_analysis.json`

说明：
- `product_lock` 是 `product_analysis` 的兼容别名，目的是让后续“结构化锁定”语义更直观，同时不破坏旧链路。
- `must_preserve_texts`
  - 偏真实包装文字锚点，最多保留 `1~5` 个短而关键的文本
  - 优先提取品牌名、产品名、香型/口味/副品名、净含量、清晰英文副标
- `locked_elements`
  - 偏视觉结构、版式、轮廓、标签位置，不等同于真实文字
- 如果 provider 没有稳定返回 `must_preserve_texts`，程序会尝试从 `visual_identity.must_preserve / locked_elements` 中回收短文本锚点
- 仍然拿不到时，不再静默空数组，而是显式写出：
  - `text_anchor_status=uncertain|unreadable`
  - `text_anchor_source=none`
  - `text_anchor_notes`
- 当前日志会显式记录：
  - `extracted_text_anchors`
  - `text_anchor_source=provider|fallback|none`
  - `text_anchor_count`
  - 如果拿不到锚点，还会追加 `warning text anchor evidence weak`

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
当商品属于茶叶类族群时，`plan_shots` 现在按两层信息同时分流：

1. `package_template_family`
2. `asset_completeness_mode`

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

## `generate_copy`

### 节点位置
- 上游：`plan_shots`
- 下游：`generate_layout`

### 节点职责
- 基于 `task + product_analysis + shot_plan` 生成结构化 `CopyPlan`。
- 把模型输出从“说明文字”收紧到“可直接贴图”的 1440x1440 中文电商文案。
- 在进入 `overlay_text` 前做程序级归一化，避免超长文案直接传入后贴字链路。

### 当前文案生成约束
- 只能使用输入任务、商品分析、shot plan 中可确认的信息。
- 不允许创造新的品牌名、系列名、虚构 slogan 或包装上不存在的品牌锚点。
- `title`
  - 优先 `8~14` 个中文字符，最长不超过 `18`
- `subtitle`
  - 优先 `8~16` 个中文字符，最长不超过 `22`
- `bullets`
  - 默认尽量为空，除非当前 shot 明确需要
- `cta`
  - 默认关闭，不主动生成
- 文风必须是短句、贴图句、卖点句，不允许散文、诗句、解释句。

### shot_type copy 风格分流
- `hero_brand`
  - 品牌感 + 品类信息 + 简洁价值点
- `package_detail`
  - 强调材质 / 工艺 / 结构卖点，不能写成 hero slogan
- `dry_leaf_detail`
  - 强调原料、条索、干茶纹理和原叶质感
- `tea_soup_experience`
  - 强调汤色、口感、饮用体验，不回到包装介绍
- `lifestyle_or_brewing_context / package_in_brewing_context`
  - 强调场景体验、日常饮用氛围和冲泡感
- `label_or_material_detail / package_with_leaf_hint / open_box_structure / carry_action`
  - 使用各自图位的卖点短句，不与 hero 文案混用

### 程序级兜底
- `generate_copy` 会先按 `shot_id` 合并缺失项，再补 shot-aware fallback 文案。
- provider 或 mock 输出超长、散文化、品牌漂移时，会自动重构为短版 `title/subtitle`。
- 归一化后默认清空 `bullets` 并关闭 `cta`，避免把冗长信息继续传给 `overlay_text`。

### 新增日志字段
- 每个 shot 都会显式记录：
  - `original_length`
  - `normalized_length`
  - `copy_shortened`
  - `brand_anchor_valid`
- 这些日志用于定位“文案本身过长”还是“布局/字体阶段压缩过度”。

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
- `shot_prompt_refiner` 先为每个 `shot_type` 生成 `ShotExecutionProfile`，统一收口主次主体、排他规则、构图约束和渲染锁定等级。
- 茶叶 `tea_tin_can` 模板下，`hero_brand / package_detail / dry_leaf_detail / tea_soup_experience / lifestyle_or_brewing_context / package_in_brewing_context / package_with_leaf_hint / label_or_material_detail` 会输出强约束执行说明，而不是宽泛描述。
- `package_detail / dry_leaf_detail / tea_soup_experience / lifestyle_or_brewing_context / package_in_brewing_context` 均带显式 negative constraints，用来阻止退化成 hero packshot。

### `render_constraints`
当前是结构化对象，至少包含：
- `generation_mode`
- `reference_image_priority`
- `consistency_strength`
- `product_lock_level`
- `editable_region_strategy`
- `allow_human_presence`
- `allow_hand_only`

当前分层语义：
- `strong_product_lock`
  - 包装主体保持绝对主导，适用于 `hero_brand / carry_action / open_box_structure`
- `medium_product_lock`
  - 产品身份稳定但允许更近裁切或上下文扩展，适用于 `package_detail / label_or_material_detail / package_with_leaf_hint / package_in_brewing_context`
- `anchor_only_product_lock`
  - 包装只做品牌锚点，前景主体可以改为茶干、茶汤或冲泡语境，适用于 `dry_leaf_detail / tea_soup_experience / lifestyle_or_brewing_context`

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
  - `primary_subject / secondary_subject`
  - `allowed_scene_change_level`
  - `forbidden_regression_pattern`
  - `editable_regions_final`
  - `must_preserve_visuals / must_preserve_texts / must_not_change`
  - `text_anchor_source / text_anchor_status`

### image_edit 执行 prompt 组装顺序
`render_images` 在 `image_edit` 模式下按以下结构组装执行 prompt，而不是简单把字段拼成一大段散文：

1. `Task Type And Current Shot Objective`
   - 先说明当前是 `image_edit`，并明确 `shot_type / shot goal / allowed_scene_change_level`
2. `Shot Differentiation Rules`
   - 优先强调当前分镜不得退化回去的形态
   - 组合 `subject_prompt` 剩余执行规则、构图方向、背景方向、光线方向、质量方向
3. `Subject Hierarchy`
   - 单独声明 `primary_subject / secondary_subject`
   - 明确上传参考图在当前分镜里承担什么锚点角色
4. `Allowed Editable Regions`
   - 输出 `editable_regions_final`
   - 输出 `editable_region_strategy`
5. `Product Identity Lock`
   - 锁定规则改成三组：
     - `must_preserve_visuals`
     - `must_preserve_texts`
     - `must_not_change`
6. `Global Style Architecture`
   - 整组风格主题、色彩策略、光线策略、镜头策略、道具体系、背景策略、文字策略
7. `Layout And Text Safe Zone`
   - 文字安全区、主体避让、文本层数、文案意图
8. `Negative Rules`
   - 组合 `style_architecture.global_negative_rules` 和 shot 级 `negative_prompt`

说明：
- 这套组装只影响 `image_edit` 主路径。
- `t2i` 仍然兼容旧 prompt plan。
- 参考图链路仍由 provider 路由层控制，不在这里替换。
- `build_prompts` 和 `render_images` 现在都会先把 `editable_regions` 收敛成 shot-aware 的稳定标签，避免频繁出现空数组。
- `render_images` 日志中的 `keep_subject_rules` 现在来自三组锁定规则的清洗合并结果，便于兼容旧日志字段。

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

补充说明：
- `final_text_regions.json / preview_text_regions.json` 现在除真实文本区域外，还会回写：
  - `font_source`
  - `font_loaded`
  - `fallback_used`
  - `requested_font_path`
  - `resolved_font_path`
  - `fallback_target`
- 每个 block 还会带出：
  - `requested_font_size`
  - `used_font_size`
  - `min_font_size_hit`
  - `overflow_detected`

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
  - 优先读取 `product_analysis.must_preserve_texts`
  - 如果锚点为空，才对 `visual_identity.must_preserve / locked_elements` 做严格过滤 fallback
  - 避免把 `front label layout / package silhouette` 这类视觉结构误当作 OCR 对比锚点
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
- 这些文字报告除了真实区域，还会带出字体解析元数据：
  - `font_source`
  - `font_loaded`
  - `fallback_used`
  - `resolved_font_path`
- 每个 block 还会显式回写：
  - `requested_font_size`
  - `used_font_size`
  - `min_font_size_hit`
  - `overflow_detected`
- `run_qc` 会优先读取这些实际文本区域做：
  - 文字安全区检查
  - 文案可读性检查
- 如果 state 里没有 `text_render_reports`，会继续尝试从对应 JSON 恢复
- 只有在两者都不存在时，才回退到 `layout_plan.blocks`

### product_consistency_check 的文字证据字段
- `details` 当前会显式写出：
  - `brand_text_targets`
  - `text_anchor_source`
  - `text_anchor_status`
  - `text_anchor_count`
- 这样可以直接区分：
  - analyze 阶段已经提取到稳定包装文字
  - 只拿到了 fallback 锚点
  - 完全没有可靠文字证据，只能人工复核

### 中文后贴字的当前约束
- `TextRenderer` 优先加载项目内配置字体；如果配置字体不存在，会按平台尝试系统中文字体候选。
- Windows 当前优先候选包含：
  - `msyh.ttc / msyhbd.ttc`
  - `Deng.ttf / Dengb.ttf`
  - `simhei.ttf / simsun.ttc`
- 不再静默回退到 `DejaVuSans.ttf` 或 `ImageFont.load_default()`。
- 最小可读字号当前固定为：
  - `title >= 40`
  - `subtitle >= 24`
  - `bullets >= 22`
  - `cta >= 22`
- 如果文本在最小字号下仍放不下：
  - 停止继续缩小
  - 标记 `overflow_detected=true`
  - 由 `text_readability_check` 按可读性失败处理

### 中文文字渲染测试产物
- 本地测试图仍输出到：
  - `outputs/previews/text_render_test.png`
  - `outputs/previews/text_render_base.png`
- 现在额外输出：
  - `outputs/previews/text_render_test.meta.json`
- sidecar metadata 会明确写出：
  - `font_source`
  - `font_loaded`
  - `fallback_used`
  - `requested_font_path`
  - `resolved_font_path`
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
- `analyze_product` 还会把素材完备度写入：
  - `product_analysis.asset_completeness_mode`
  - 当前支持：
    - `packshot_only`
    - `packshot_plus_detail`
- `analyze_product` 会把模板判断结果写入 `product_analysis.package_template_family`。
- `plan_shots` 会根据这个字段分流：
  - `tea_gift_box`：保留 `carry_action / open_box_structure`
  - `tea_tin_can + packshot_plus_detail`：使用 `package_detail / dry_leaf_detail / tea_soup_experience / lifestyle_or_brewing_context`
  - `tea_tin_can + packshot_only`：改为 `package_detail / label_or_material_detail / package_with_leaf_hint / package_in_brewing_context`
  - `tea_pouch`：走轻量袋装场景模板
- 这一步不改变 `shot_plan.json` 的字段结构，只改变固定五图的 `shot_type` 组合。

### 茶叶模板调试日志
`analyze_product` 和 `plan_shots` 当前都会显式记录：
- `package_template_family`
- `asset_completeness_mode`
- `selected_main_asset_id`
- `selected_detail_asset_id`
- `chosen_template_name`

## 本次补充：结果图导向 QC

`run_qc` 当前不再只依赖 `shot_plan / shot_prompt_specs / metadata` 自证，而是额外读取最终结果图本身做轻量规则检查。

新增和强化的重点如下：
- `text_readability_check`
  - 直接读取 `overlay_text` 回写的 `used_font_size / min_font_size_hit / overflow_detected`
  - 按商用最小可读字号检查：
    - `title >= 40`
    - `subtitle >= 24`
    - `bullets >= 22`
    - `cta >= 22`
  - 如果实际字号低于阈值，即使没有 overflow，也会进入 `warning`
  - 如果实际字号低于阈值的 `80%`，或 `merged_text_region_ratio < 0.006`，则直接 `failed`
  - 同时检查 `merged_text_region_ratio`
    - `< 0.012` 记为过小 warning
    - `< 0.006` 记为 failed
- `shot_type_match_check`
  - 仍保留 metadata 级最小语义校验
  - 现在额外增加结果图规则：
    - `package_detail` 会和 hero 图做轻量相似度比较，避免仍是同构 packshot
    - `dry_leaf_detail` 会检查前景纹理信号是否足够强
    - `tea_soup_experience` 会检查茶汤/杯具类信号
    - `lifestyle_or_brewing_context / package_in_brewing_context` 会检查外围 props / scene context 信号
  - `details` 会同时输出 `metadata_warnings / visual_warnings / visual_metrics`
- `product_consistency_check`
  - 现在把证据拆成：
    - `visual_consistency`
    - `text_anchor_consistency`
    - `evidence_completeness`
  - 如果 `must_preserve_texts` 存在但 OCR 读不到，`evidence_completeness` 不能再是 `full`
  - `details` 会明确写出 `text_anchor_source / text_anchor_status / text_anchor_count`
- `visual_shot_diversity_check`
  - 新增任务级检查，比较五张图的轻量视觉签名
  - 会输出哪些 shot 彼此过于接近，哪些 shot 过于接近 hero 构图
  - 用于预警“虽然 prompt 不同，但结果图仍退化成一组相似 packshot”

`qc_report` 当前根级摘要字段包括：
- `shot_completeness_check`
- `product_consistency_check`
- `shot_type_match_check`
- `visual_shot_diversity_check`
- `text_safe_zone_check`
- `text_readability_check`

`run_qc` 节点日志当前会额外输出：
- `text_readability_summary`
- `product_consistency_summary`
- `shot_type_match_summary`
- `visual_shot_diversity_summary`
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
