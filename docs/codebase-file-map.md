<<<<<<< HEAD
# 代码文件地图

## 入口
- `streamlit_app.py`
  - 唯一 UI 入口

## 配置与路由
- `src/core/config.py`
  - provider 路由、模型选择、v1/v2 默认参数
- `src/providers/router.py`
  - 构造文本、视觉、图片 provider

## v2 schema
- `src/domain/director_output.py`
  - `director_v2` 输出 contract
- `src/domain/prompt_plan_v2.py`
  - `prompt_refine_v2` 输出 contract
- `src/domain/task.py`
  - 任务级字段，包含 `workflow_version`、`enable_overlay_fallback`

## workflow
- `src/workflows/graph.py`
  - `build_workflow_v1 / build_workflow_v2 / build_workflow`
- `src/workflows/state.py`
  - v1/v2 共享 state、依赖容器和调试摘要

## v2 节点
- `src/workflows/nodes/director_v2.py`
  - 生成 8 张图导演规划
- `src/workflows/nodes/prompt_refine_v2.py`
  - 生成 render prompt、标题、副标题和版式提示

## 共用节点的 v2 扩展
- `src/workflows/nodes/render_images.py`
  - 同时兼容 v1 `image_prompt_plan` 与 v2 `prompt_plan_v2`
- `src/workflows/nodes/overlay_text.py`
  - v1 全量贴字，v2 仅处理 fallback 候选
- `src/workflows/nodes/run_qc.py`
  - v1/v2 共用入口，v2 识别图内文案与 fallback 需求
- `src/workflows/nodes/finalize.py`
  - 汇总 v1/v2 产物并导出

## provider
- `src/providers/llm/runapi_openai_text.py`
  - RunAPI 文本 provider，默认 `gpt-5-nano`
- `src/providers/image/runapi_gemini31_image.py`
  - RunAPI Gemini 3.1 图片 provider，默认 `gemini-3.1-flash-image-preview`

## UI
- `src/ui/pages/task_form.py`
  - 表单默认值与 workflow/version 开关
- `src/ui/pages/home.py`
  - 任务提交、workflow 调用、debug 聚合
- `src/ui/pages/result_view.py`
  - v1/v2 结果展示与调试摘要

## 存储恢复
- `src/services/storage/task_loader.py`
  - 从任务目录恢复 v1/v2 上下文

## 提示词
- `src/prompts/director_v2.md`
- `src/prompts/prompt_refine_v2.md`

## 测试
- `tests/unit/test_schema_models_v2.py`
- `tests/unit/test_director_v2.py`
- `tests/unit/test_prompt_refine_v2.py`
- `tests/unit/test_runapi_gemini31_image.py`
- `tests/unit/test_render_v2_and_qc.py`
- `tests/unit/test_workflow_v2_routing.py`
=======
# 全仓文件功能总表

## 仓库总体目录说明

### 根目录
- `src/`
  - 主代码目录，按 `core / domain / providers / services / ui / workflows` 分层。
- `docs/`
  - 项目事实来源，记录架构、workflow、provider、contract、QC 和阅读指南。
- `tests/`
  - 单元测试与回归测试。
- `outputs/`
  - 本地任务产物目录，`outputs/tasks/{task_id}/` 下可回放每次运行。
- `streamlit_app.py`
  - 唯一 UI 入口。
- `AGENTS.md`
  - Codex 执行规则、文档同步约束、最终检查清单。

### `src/` 子目录职责
- `src/core/`
  - 配置、路径、日志等基础设施。
- `src/domain/`
  - Pydantic schema，定义节点输入输出和落盘 JSON contract。
- `src/providers/`
  - 文本、视觉、图片 provider 与路由。
- `src/services/`
  - 存储、规划、布局、渲染、QC 等支撑逻辑。
- `src/workflows/`
  - LangGraph state、图结构、workflow 节点。
- `src/ui/`
  - Streamlit 页面、组件、调试展示。
- `src/prompts/`
  - LLM 提示模板。

### `docs/` 当前核心文档
- `docs/architecture.md`
  - 系统分层和主链路设计说明。
- `docs/workflow.md`
  - 节点顺序、state contract、落盘产物和调试链路。
- `docs/providers.md`
  - provider 路由、模型切换和 `t2i / image_edit` 相关说明。
- `docs/qc-policy.md`
  - QC 检查项和 review/fail 语义。
- `docs/phase1-contract.md`
  - 茶叶类 Phase 1 的固定五图和结构化 spec 约束。
- `docs/java-developer-reading-guide.md`
  - 面向 Java 开发者的项目阅读指南。
- `docs/contracts/`
  - schema、示例 JSON 和 contract 文档。

## 核心文件清单

### 入口与配置

#### `streamlit_app.py`
- 功能说明：
  - Streamlit 启动入口，负责把页面控制权交给 `src/ui/pages/home.py`。
- 关键类 / 函数：
  - `main()`
- 上游调用方：
  - `streamlit run streamlit_app.py`
- 下游影响对象：
  - 整个 UI 和 workflow 执行入口。
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/architecture.md`
  - `docs/workflow.md`

#### `src/core/config.py`
- 功能说明：
  - 读取环境变量、provider 路由、模型选择和运行开关。
  - 现在也集中管理中文字体候选解析和最小可读字号配置。
- 关键类 / 函数：
  - `Settings`
  - `get_settings()`
- 上游调用方：
  - graph、provider、UI
- 下游影响对象：
  - 所有 provider 和运行模式。
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/providers.md`
  - `docs/workflow.md`
  - 相关 contract 文档
  - `.env.example`

### domain / schema

#### `src/domain/product_analysis.py`
- 功能说明：
  - 商品锁定分析结果 contract，对应 `product_analysis.json`。
  - 当前额外承载茶叶模板分流所需的 `package_template_family / asset_completeness_mode`。
  - 当前还显式建模包装文字锚点相关字段：`must_preserve_texts / text_anchor_status / text_anchor_source / text_anchor_notes`。
- 关键类 / 函数：
  - `ProductAnalysis`
- 上游调用方：
  - `analyze_product`
- 下游影响对象：
  - `style_director`
  - `plan_shots`
  - `shot_prompt_refiner`
  - `render_images`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/contracts/*`

#### `src/domain/style_architecture.py`
- 功能说明：
  - 整组视觉总导演输出 contract，对应 `style_architecture.json`。
- 关键类 / 函数：
  - `StyleArchitecture`
- 上游调用方：
  - `style_director`
- 下游影响对象：
  - `plan_shots`
  - `shot_prompt_refiner`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/contracts/style_architecture.*`

#### `src/domain/shot_plan.py`
- 功能说明：
  - 图位规划 contract，对应 `shot_plan.json`。
  - 茶叶类 Phase 1 当前固定五图，`ShotSpec` 额外承载安全区偏好、必备主体和可选道具。
- 关键类 / 函数：
  - `ShotSpec`
  - `ShotPlan`
- 上游调用方：
  - `plan_shots`
- 下游影响对象：
  - `generate_copy`
  - `generate_layout`
  - `shot_prompt_refiner`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/phase1-contract.md`
  - `docs/contracts/tea_gift_box_phase1_example.json`
  - `tests/unit/test_plan_shots_prompt_constraints.py`

#### `src/domain/shot_prompt_specs.py`
- 功能说明：
  - 单张结构化 prompt spec contract，对应 `shot_prompt_specs.json`。
  - 明确建模 `product_lock / layout_constraints / render_constraints / copy_intent`。
  - `RenderConstraintSpec` 现在额外建模 `product_lock_level / editable_region_strategy`，用于表达 shot 级锁定强度和可编辑区域策略。
- 关键类 / 函数：
  - `ShotPromptSpec`
  - `ShotPromptSpecPlan`
  - `ProductLockSpec`
  - `LayoutConstraintSpec`
  - `RenderConstraintSpec`
  - `CopyIntentSpec`
- 上游调用方：
  - `shot_prompt_refiner`
- 下游影响对象：
  - `build_prompts`
  - `render_images`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/contracts/shot_prompt_specs.schema.json`
  - `docs/contracts/shot_prompt_specs.json`
  - `tests/unit/test_visual_director_architecture.py`

#### `src/domain/image_prompt_plan.py`
- 功能说明：
  - 旧链路兼容 prompt plan，对应 `image_prompt_plan.json`。
  - 现在作为结构化 spec 到渲染链路的兼容桥。
- 关键类 / 函数：
  - `ImagePrompt`
  - `ImagePromptPlan`
- 上游调用方：
  - `build_prompts`
- 下游影响对象：
  - `render_images`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/contracts/*`

#### `src/domain/qc_report.py`
- 功能说明：
  - QC 报告 contract，对应 `qc_report.json / qc_report_preview.json`。
  - 保留 `checks` 明细列表，同时新增 `shot_completeness_check / product_consistency_check / shot_type_match_check` 根字段。
- 关键类 / 函数：
  - `QCCheck`
  - `QCCheckSummary`
  - `QCReport`
- 上游调用方：
  - `run_qc`
- 下游影响对象：
  - `finalize`
  - UI 结果页
  - 导出与人工复核
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/qc-policy.md`
  - `docs/workflow.md`
  - QC 相关测试

### workflow 节点

#### `src/workflows/graph.py`
- 功能说明：
  - 定义整个 workflow 的节点顺序与依赖注入。
- 关键类 / 函数：
  - `build_workflow()`
- 上游调用方：
  - UI 任务执行入口
- 下游影响对象：
  - 全部节点
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/architecture.md`
  - `tests/unit` 中涉及 workflow 顺序的测试

#### `src/workflows/state.py`
- 功能说明：
  - 定义 workflow state、依赖容器和统一日志辅助函数。
  - 当前集中声明四类主链路 contract 的 state 字段和 artifact 文件名。
- 关键类 / 函数：
  - `WorkflowState`
  - `WorkflowDependencies`
  - `CORE_CONTRACT_ARTIFACTS`
  - `build_connected_contract_summary()`
- 上游调用方：
  - 所有节点
- 下游影响对象：
  - 调试日志和 UI 结果页
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/codebase-file-map.md`
  - 相关 state/调试测试

#### `src/workflows/nodes/analyze_product.py`
- 功能说明：
  - 生成 `product_analysis.json`，并把 `product_analysis / product_lock` 同时接入 state。
  - 当前还会把参考图选择结果归一化为 `asset_completeness_mode`，供茶叶模板双重分流使用。
  - 当前会优先提取包装真实文字锚点；provider 为空时，再从 `visual_identity.must_preserve / locked_elements` 中做轻量 fallback。
  - 节点日志会新增 `extracted_text_anchors / text_anchor_source / text_anchor_count`。
- 关键类 / 函数：
  - `analyze_product()`
- 上游调用方：
  - `graph.py`
- 下游影响对象：
  - `style_director`
  - `plan_shots`
  - `shot_prompt_refiner`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/phase1-contract.md`
  - 对应单元测试

#### `src/workflows/nodes/style_director.py`
- 功能说明：
  - 生成整组视觉风格架构 `style_architecture.json`。
- 关键类 / 函数：
  - `style_director()`
- 上游调用方：
  - `graph.py`
- 下游影响对象：
  - `plan_shots`
  - `shot_prompt_refiner`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/contracts/style_architecture.*`
  - `tests/unit/test_visual_director_architecture.py`

#### `src/workflows/nodes/plan_shots.py`
- 功能说明：
  - 生成 `shot_plan.json`。
  - 茶叶类 Phase 1 当前按 `package_template_family + asset_completeness_mode` 双重分流固定五图模板，模型只补图位细节。
- 关键类 / 函数：
  - `plan_shots()`
- 上游调用方：
  - `graph.py`
- 下游影响对象：
  - `generate_copy`
  - `generate_layout`
  - `shot_prompt_refiner`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/phase1-contract.md`
  - `tests/unit/test_plan_shots_prompt_constraints.py`

#### `src/workflows/nodes/generate_copy.py`
- 功能说明：
  - 生成 `copy_plan.json`。
  - 把模型或 mock 输出归一化为适合 1440x1440 中文贴图的短版文案。
  - 会在进入 `overlay_text` 前收短超长文案、清理散文化句式，并做品牌锚点校验。
- 关键类 / 函数：
  - `generate_copy()`
  - `_build_copy_generation_prompt()`
  - `_normalize_copy_plan_for_overlay()`
  - `_validate_brand_anchor()`
- 上游调用方：
  - `graph.py`
- 下游影响对象：
  - `generate_layout`
  - `overlay_text`
  - `copy_plan.json`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/phase1-contract.md`
  - `src/prompts/base/generate_copy.md`
  - `tests/unit/test_generate_copy.py`

#### `src/workflows/nodes/shot_prompt_refiner.py`
- 功能说明：
  - 基于 `product_analysis + style_architecture + shot_plan + layout_plan` 生成 `shot_prompt_specs.json`。
  - 固化单张图的 8 层 prompt、product lock、布局约束、渲染约束和 copy intent。
  - 先构建 `ShotExecutionProfile`，再把 `primary_subject / secondary_subject / shot_differentiation_summary / banned_fallback_pattern` 和 shot-specific negative constraints 注入 spec 与日志。
- 关键类 / 函数：
  - `shot_prompt_refiner()`
  - `_build_base_spec()`
  - `_build_shot_execution_profile()`
  - `_merge_spec_plan_with_defaults()`
- 上游调用方：
  - `graph.py`
- 下游影响对象：
  - `build_prompts`
  - `render_images`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/contracts/shot_prompt_specs.schema.json`
  - `docs/contracts/shot_prompt_specs.json`
  - `src/prompts/shot_prompt_refiner.md`
  - `tests/unit/test_visual_director_architecture.py`

#### `src/workflows/nodes/build_prompts.py`
- 功能说明：
  - 把 `shot_prompt_specs` 映射成兼容旧链路的 `ImagePromptPlan`。
  - 当前还会把 `editable_regions` 收敛成 shot-aware 的稳定标签，避免后续 `render_images` 经常拿到空数组。
- 关键类 / 函数：
  - `build_prompts()`
  - `_build_image_prompt()`
- 上游调用方：
  - `shot_prompt_refiner`
- 下游影响对象：
  - `render_images`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/contracts/shot_prompt_specs.*`
  - `tests/unit/test_build_prompts_per_shot.py`

#### `src/workflows/nodes/render_images.py`
- 功能说明：
  - 根据兼容 prompt plan 执行实际图片生成。
  - `image_edit` 模式下优先基于 `product_lock + style_architecture + shot_prompt_specs` 组装最终执行 prompt。
  - 如果缺少任一关键 contract，则回退到旧的 `edit_instruction / prompt`。
  - 现在会把 `product_lock_level / editable_region_strategy` 一起写进最终执行 prompt，避免不同 shot_type 在 provider 侧退化成同类 hero packshot。
  - 当前会把执行 prompt 重排成“shot objective -> differentiation -> subject hierarchy -> editable regions -> product lock”顺序，并把锁定规则整理为 `must_preserve_visuals / must_preserve_texts / must_not_change` 三组。
  - 当前日志会额外输出 `primary_subject / secondary_subject / allowed_scene_change_level / forbidden_regression_pattern / editable_regions_final`。
  - 当前还会把 `text_anchor_source / text_anchor_status` 带入 `prompt_contract` 调试日志，便于判断文字锚点强弱。
- 关键类 / 函数：
  - `render_images()`
- 上游调用方：
  - `build_prompts`
- 下游影响对象：
  - `overlay_text`
  - 调试日志
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/providers.md`
  - `docs/phase1-contract.md`
  - 渲染相关测试

#### `src/workflows/nodes/finalize.py`
- 功能说明：
  - 生成 ZIP 导出，汇总核心 contract 文件的存在性和固定路径。
- 关键类 / 函数：
  - `finalize()`
- 上游调用方：
  - `run_qc`
- 下游影响对象：
  - UI 结果页
  - bundle 导出
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/codebase-file-map.md`
  - 结果展示和导出测试

#### `src/workflows/nodes/run_qc.py`
- 功能说明：
  - 执行任务级 QC，并把结果落盘到 `qc_report.json` 或 `qc_report_preview.json`。
  - 当前除工程检查外，还负责茶叶 Phase 1 的五图完整性、商品一致性、图位匹配度，以及文字安全区和文案可读性检查。
- 关键类 / 函数：
  - `run_qc()`
- 上游调用方：
  - `overlay_text`
- 下游影响对象：
  - `finalize`
  - UI 结果页
  - 导出链路
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/qc-policy.md`
  - `docs/workflow.md`
  - `tests/unit/test_qc_and_exports.py`

### services

#### `src/services/qc/task_qc.py`
- 功能说明：
  - 承载任务级轻量 QC 规则函数。
  - 当前集中实现文字可读性、文字安全区、布局风险、五图完整性、商品一致性和图位匹配度检查。
  - `product_consistency_check` 会优先消费 `must_preserve_texts`，并避免把视觉结构描述误判成文字锚点。
- 关键类 / 函数：
  - `build_shot_completeness_check()`
  - `build_product_consistency_check()`
  - `build_shot_type_match_check()`
  - 其他文字/布局检查函数
- 上游调用方：
  - `run_qc`
- 下游影响对象：
  - `qc_report`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/qc-policy.md`
  - `docs/workflow.md`
  - `tests/unit/test_qc_and_exports.py`

#### `src/services/planning/layout_generator.py`
- 功能说明：
  - 基于安全区打分结果生成 `layout_plan.json` 中的文字块区域。
  - 当前会优先放宽 title / subtitle 的横向占位，避免把中文标题挤成窄列。
- 关键类 / 函数：
  - `build_mock_layout_plan()`
  - `_build_blocks_for_zone()`
- 上游调用方：
  - `generate_layout`
- 下游影响对象：
  - `overlay_text`
  - `run_qc`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - 文字渲染相关测试

#### `src/services/assets/reference_selector.py`
- 功能说明：
  - 统一选择主参考图和细节参考图。
  - 当前还负责解析 `asset_completeness_mode`，供 `analyze_product / plan_shots / render_images` 共用。
- 关键类 / 函数：
  - `ReferenceSelection`
  - `select_reference_bundle()`
- 上游调用方：
  - `analyze_product`
  - `render_images`
- 下游影响对象：
  - `product_analysis.asset_completeness_mode`
  - 参考图选择日志
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/phase1-contract.md`
  - `tests/unit/test_reference_selector.py`

#### `src/services/fallbacks/copy_fallback.py`
- 功能说明：
  - 承载 `generate_copy` 的 shot-aware fallback 文案规则。
  - provider 缺失、品牌锚点非法或文案被判定不适合贴图时，输出短版 `title/subtitle`。
- 关键类 / 函数：
  - `CopyPlanMergeResult`
  - `build_default_copy_item_for_shot()`
  - `merge_copy_plan_with_shots()`
- 上游调用方：
  - `generate_copy`
  - `copy_generator.py`
- 下游影响对象：
  - `copy_plan.json`
  - 文案归一化日志
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/phase1-contract.md`
  - `tests/unit/test_generate_copy.py`

#### `src/services/planning/copy_generator.py`
- 功能说明：
  - mock 模式下生成 `CopyPlan`。
  - 当前复用 fallback 规则，保证 mock 输出也符合短版贴图文案约束。
- 关键类 / 函数：
  - `build_mock_copy_plan()`
- 上游调用方：
  - `generate_copy`
- 下游影响对象：
  - `copy_plan.json`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `tests/unit/test_generate_copy.py`

#### `src/services/storage/task_loader.py`
- 功能说明：
  - 从任务目录回读 JSON 和图片路径，恢复 result_view 所需 state。
  - 当前会把 `product_analysis.json` 同时恢复为 `product_analysis` 和 `product_lock`。
  - 也会在存在时恢复 `final_text_regions.json / preview_text_regions.json`，避免结果回放时丢失真实文字区域。
- 关键类 / 函数：
  - `load_task_context()`
- 上游调用方：
  - UI 结果页和任务回放链路
- 下游影响对象：
  - `home.py`
  - `result_view.py`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/codebase-file-map.md`

### providers

#### `src/providers/router.py`
- 功能说明：
  - 统一解析文本、视觉、图片 provider 的实现和模型选择。
- 关键类 / 函数：
  - provider 解析与依赖构建相关函数
- 上游调用方：
  - `graph.py`
  - 依赖装配逻辑
- 下游影响对象：
  - 所有节点中的 provider 调用
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/providers.md`
  - 相关环境变量文档

### ui

#### `src/ui/pages/home.py`
- 功能说明：
  - Streamlit 首页，负责创建任务、执行 workflow、合并运行态调试信息。
  - 当前会把主链路 contract 接通摘要合并进 debug 信息。
- 关键类 / 函数：
  - `_merge_runtime_debug_info()`
  - `_append_observability_summaries()`
- 上游调用方：
  - `streamlit_app.py`
- 下游影响对象：
  - `result_view.py`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - UI 调试文档
  - `tests/unit/test_ui_debug_observability.py`

#### `src/ui/pages/result_view.py`
- 功能说明：
  - 结果页，负责展示预览图、成品图、artifact 路径和调试摘要。
- 关键类 / 函数：
  - `render_result_view()` 及相关展示函数
- 上游调用方：
  - `home.py`
- 下游影响对象：
  - 用户调试体验
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - UI 调试文档

#### `src/workflows/nodes/overlay_text.py`
- 功能说明：
  - 执行 Pillow 中文后贴字并生成预览图。
  - 当前会把每个 shot 的实际文本渲染块摘要、字号使用情况和字体来源信息回写到 `text_render_reports`，并落盘到 `final_text_regions.json / preview_text_regions.json`，供 `run_qc` 读取。
- 关键类 / 函数：
  - `overlay_text()`
- 上游调用方：
  - `render_images`
- 下游影响对象：
  - `run_qc`
  - UI 预览与结果图
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/qc-policy.md`
  - 文字渲染相关测试

#### `src/services/rendering/text_renderer.py`
- 功能说明：
  - 承载 Pillow 中文后贴字和自适应文字样式。
  - 当前会回传每个文本块的实际渲染区域、密度、最小字号命中情况和溢出标记，供文字层 QC 使用。
  - 同时会返回字体来源、fallback 状态，并生成中文渲染测试图 metadata sidecar。
- 关键类 / 函数：
  - `TextRenderer`
  - `PlacedTextBlock`
  - `TextRenderReport`
- 上游调用方：
  - `overlay_text`
- 下游影响对象：
  - `run_qc`
  - 文字渲染日志
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/qc-policy.md`
  - `tests/unit/test_text_renderer.py`

#### `src/services/rendering/font_utils.py`
- 功能说明：
  - 负责解析项目字体与系统中文字体候选，并加载可追踪的真实字体文件。
  - 不允许静默回退到不适合中文的默认字体。
- 关键类 / 函数：
  - `LoadedFont`
  - `load_font()`
- 上游调用方：
  - `TextRenderer`
- 下游影响对象：
  - 中文字体稳定性
  - 文字渲染日志
  - `text_render_test.meta.json`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `tests/unit/test_text_renderer.py`

### prompts

#### `src/prompts/style_director.md`
- 功能说明：
  - 约束模型输出整组视觉风格 JSON，而不是单张 prompt。
- 上游调用方：
  - `style_director`
- 下游影响对象：
  - planning provider 的 structured output
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/contracts/style_architecture.*`
  - `docs/workflow.md`

#### `src/prompts/shot_prompt_refiner.md`
- 功能说明：
  - real 模式下约束模型输出结构化 `ShotPromptSpecPlan`。
  - 当前要求模型输出偏“执行说明”而不是“描述性文案”，并为关键 shot_type 加排他规则。
- 上游调用方：
  - `shot_prompt_refiner`
- 下游影响对象：
  - planning provider 的 structured output
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/contracts/shot_prompt_specs.*`

#### `src/prompts/base/generate_copy.md`
- 功能说明：
  - real 模式下约束模型输出结构化 `CopyPlan`。
  - 当前明确限制文案长度、品牌锚点、散文化语气和 shot_type copy 风格。
- 上游调用方：
  - `generate_copy`
- 下游影响对象：
  - planning provider 的 structured output
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/phase1-contract.md`

### tests

#### `tests/unit/test_visual_director_architecture.py`
- 功能说明：
  - 验证 `style_director`、`shot_prompt_refiner`、结构化 spec 落盘、contract 接线和 workflow 顺序。
  - 当前还覆盖茶叶 tin can 模板下不同 shot_type 的排他规则和 render constraint 分层。
- 关键类 / 函数：
  - 茶叶类固定五图和结构化导演链路相关测试
- 上游调用方：
  - `pytest`
- 下游影响对象：
  - 结构化视觉导演架构回归安全
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/contracts/shot_prompt_specs.*`

#### `tests/unit/test_ui_debug_observability.py`
- 功能说明：
  - 验证缓存和真实生成链路调试信息，以及核心 contract 是否可见。
- 关键类 / 函数：
  - UI 调试摘要相关测试
- 上游调用方：
  - `pytest`
- 下游影响对象：
  - `home.py`
  - `result_view.py`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - UI 调试相关文档

#### `tests/unit/test_qc_and_exports.py`
- 功能说明：
  - 验证 QC 报告字段、茶叶 Phase 1 图像层合同检查、真实文本区域回写/回读，以及 `finalize` 导出行为。
- 关键类 / 函数：
  - QC 与导出相关回归测试
- 上游调用方：
  - `pytest`
- 下游影响对象：
  - `run_qc`
  - `finalize`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/qc-policy.md`
  - `docs/workflow.md`

#### `tests/unit/test_generate_copy.py`
- 功能说明：
  - 验证 `generate_copy` 的长度收短、品牌锚点校验、mock 输出约束和归一化日志字段。
- 关键类 / 函数：
  - 文案归一化与日志相关单元测试
- 上游调用方：
  - `pytest`
- 下游影响对象：
  - `generate_copy`
  - `copy_fallback.py`
  - `copy_generator.py`
- 是否属于核心链路：
  - 是
- 修改该文件时通常需要同步更新：
  - `docs/workflow.md`
  - `docs/codebase-file-map.md`

## 核心主链路文件
主链路从：

`ingest_assets -> analyze_product -> style_director -> plan_shots -> generate_copy -> generate_layout -> shot_prompt_refiner -> build_prompts -> render_images -> overlay_text -> run_qc -> finalize`

关键文件及职责：
- `src/workflows/nodes/analyze_product.py`
  - 生成商品锁定分析，并把 `product_lock` 接入 state。
  - 当前还负责把包装文字锚点归一化为后续 render/QC 可消费的稳定字段。
- `src/workflows/nodes/style_director.py`
  - 生成整组统一视觉架构。
- `src/workflows/nodes/plan_shots.py`
  - 输出茶叶类固定五图模板。
- `src/workflows/nodes/generate_copy.py`
  - 输出短版贴图文案并做程序级文案归一化。
- `src/workflows/nodes/generate_layout.py`
  - 生成每张图的布局和 `text_safe_zone`。
- `src/workflows/nodes/shot_prompt_refiner.py`
  - 产出结构化单张 spec。
- `src/workflows/nodes/build_prompts.py`
  - 兼容映射到旧 prompt plan。
- `src/workflows/nodes/render_images.py`
  - 执行图片生成。
- `src/workflows/nodes/overlay_text.py`
  - Pillow 后贴字。
- `src/workflows/nodes/run_qc.py`
  - 轻量商业可用性和工程 QC。
- `src/workflows/nodes/finalize.py`
  - 导出和 artifact 路径汇总。

## 建议阅读顺序
面向第一次阅读仓库的 Java 开发者，建议按这个顺序：

1. `docs/java-developer-reading-guide.md`
2. `docs/workflow.md`
3. `src/workflows/graph.py`
4. `src/workflows/state.py`
5. `src/domain/product_analysis.py`
6. `src/domain/style_architecture.py`
7. `src/domain/shot_plan.py`
8. `src/domain/shot_prompt_specs.py`
9. `src/workflows/nodes/style_director.py`
10. `src/workflows/nodes/plan_shots.py`
11. `src/workflows/nodes/generate_copy.py`
12. `src/workflows/nodes/shot_prompt_refiner.py`
13. `src/workflows/nodes/build_prompts.py`
14. `src/workflows/nodes/render_images.py`
15. `tests/unit/test_visual_director_architecture.py`

## 本次补充：generate_copy 短版贴图文案约束
- `src/workflows/nodes/generate_copy.py`
  - 现在会在 provider/mock 输出后做统一 copy normalization，限制标题、副标题长度并拦截品牌漂移。
  - 节点日志新增 `original_length / normalized_length / copy_shortened / brand_anchor_valid`。
- `src/services/fallbacks/copy_fallback.py`
  - fallback 改为 shot-aware 短版贴图文案，不再输出冗长 bullets 或 CTA。
- `src/services/planning/copy_generator.py`
  - mock 模式复用 fallback，保证测试与本地运行时的 copy 也符合后贴字约束。
- `src/prompts/base/generate_copy.md`
  - prompt 改成“可直接贴图”的执行约束，按 `shot_type` 区分 copy 风格。
- `tests/unit/test_generate_copy.py`
  - 覆盖长度阈值、品牌锚点校验和归一化日志。

## 本次补充：analyze_product 文字锚点提取
- `src/domain/product_analysis.py`
  - `ProductAnalysis` 新增 `text_anchor_status / text_anchor_source / text_anchor_notes`，显式标记包装文字锚点的可靠性和来源。
- `src/workflows/nodes/analyze_product.py`
  - provider 会优先提取品牌名、产品名、香型/口味、净含量和清晰英文副标。
  - provider 空返回时，会从 `visual_identity.must_preserve / locked_elements` 中筛出短文本锚点。
  - 节点日志新增 `extracted_text_anchors / text_anchor_source / text_anchor_count`。
- `src/services/qc/task_qc.py`
  - `product_consistency_check` 优先使用 `must_preserve_texts` 作为 OCR 对比锚点。
  - `details` 里会新增 `text_anchor_source / text_anchor_status / text_anchor_count`。
- `src/workflows/nodes/render_images.py`
  - `prompt_contract` 调试日志现在会带出 `text_anchor_source / text_anchor_status`。
- `tests/unit/test_analyze_product_real_mode.py`
  - 覆盖 provider 空返回时的 fallback 文字锚点提取，以及弱证据日志。

## 待补全文档范围
当前优先覆盖了主链路和结构化导演相关文件。以下范围后续建议继续补齐：
- `src/providers/llm/*.py`
- `src/providers/vision/*.py`
- `src/ui/components/*.py`
- `src/services/prompting/*.py`
## 本次补充：QC 证据充分度
- `src/services/qc/task_qc.py`
  - `build_product_consistency_check()` 现在执行“有证据才能通过”的轻量规则。
  - 修改该文件时，通常还要同步更新：
    - `docs/qc-policy.md`
    - `docs/workflow.md`
    - `tests/unit/test_qc_and_exports.py`
- `src/domain/qc_report.py`
  - `QCCheck / QCCheckSummary` 新增 `evidence_completeness`，用于区分 `full / partial / missing`。
- `src/workflows/nodes/run_qc.py`
  - `product_consistency_summary` 日志会明确打印 `evidence_completeness`，便于区分“规则失败”和“证据不足”。
## 本次补充：茶叶模板按包装族分流
- `src/domain/product_analysis.py`
  - `ProductAnalysis` 新增 `package_template_family / asset_completeness_mode`，用于把茶叶商品分流到更合适的五图模板。
- `src/services/analysis/product_analyzer.py`
  - mock 分析现在会根据商品名和素材情况补 `package_type / material / package_template_family / asset_completeness_mode`。
- `src/services/assets/reference_selector.py`
  - 现在除主图/细节图选择外，还会统一输出 `asset_completeness_mode`。
- `src/services/planning/tea_shot_planner.py`
  - 不再只有礼盒模板，也不再只按包型分流。
  - 当前至少维护：
    - `tea_gift_box`
    - `tea_tin_can`
    - `tea_pouch`
  - 其中 `tea_tin_can` 会继续区分：
    - `packshot_only`
    - `packshot_plus_detail`
  - 修改该文件时，通常还要同步更新：
    - `docs/phase1-contract.md`
    - `docs/workflow.md`
    - `tests/unit/test_plan_shots_prompt_constraints.py`
- `src/workflows/nodes/plan_shots.py`
  - 现在会把 `package_template_family / asset_completeness_mode / selected_main_asset_id / selected_detail_asset_id / chosen_template_name` 写入日志，便于定位当前模板命中原因。
## 本次补充：style_director 与 render_images contract 清理
- `src/domain/style_architecture.py`
  - `StyleArchitecture` 新增 `main_light_direction`，用于避免只靠 `lighting_strategy` 推断主光方向。
- `src/workflows/nodes/style_director.py`
  - 现在会在程序层补齐 `main_light_direction / color_strategy / background_strategy / lens_strategy`。
  - 修改该文件时，通常还要同步更新：
    - `docs/workflow.md`
    - `docs/phase1-contract.md`
    - `docs/contracts/style_architecture.*`
- `src/workflows/nodes/render_images.py`
  - `image_edit` prompt 组装现在会优先显式展开结构化 product lock。
  - 调试日志中的 `keep_subject_rules / editable_regions` 会先清洗，避免 tuple 字符串污染。

## 本次补充：QC 更接近看结果图
- `src/domain/qc_report.py`
  - `QCReport` 根级摘要新增 `visual_shot_diversity_check`，用于承接任务级组图多样性预警。
- `src/workflows/nodes/run_qc.py`
  - `run_qc()` 现在会额外构建 `visual_shot_diversity_check`。
  - `shot_type_match_check` 会拿到 hero 参考图路径，用于轻量“是否退化成 hero”比对。
  - 节点日志新增：
    - `text_readability_summary`
    - `product_consistency_summary`
    - `shot_type_match_summary`
    - `visual_shot_diversity_summary`
- `src/services/qc/task_qc.py`
  - `build_text_readability_check()`
    - 现在直接消费 `used_font_size / merged_text_region`
    - 加入商用最小可读字号阈值和文本区域占比阈值
  - `build_product_consistency_check()`
    - 现在显式区分 `visual_consistency / text_anchor_consistency / evidence_completeness`
  - `build_shot_type_match_check()`
    - 现在不再只看 metadata，也会做轻量图像规则
  - `build_visual_shot_diversity_check()`
    - 新增五图趋同预警
  - 当前核心阈值：
    - `title >= 40`
    - `subtitle >= 24`
    - `bullets >= 22`
    - `cta >= 22`
    - `merged_text_region_ratio < 0.012` 预警
    - `merged_text_region_ratio < 0.006` 失败
- `tests/unit/test_qc_and_exports.py`
  - 覆盖真实字号低于阈值、五图过度趋同、`shot_type_match_check` 消费图像信号而不只是 prompt metadata 的回归用例。
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
