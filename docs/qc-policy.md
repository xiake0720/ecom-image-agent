# QC 策略说明

## 1. 文档目的
当前 QC 目标不是做 AI 审美打分，而是：
- 兜住明显工程错误
- 暴露基础商业可用性风险
- 给人工复核提供足够明确的调试信息

## 2. QC 结果语义
每个检查项都有：
- `status`
  - `passed`
  - `warning`
  - `failed`
- `details`
  - 用于调试，不能只返回布尔值
- `related_shot_id`
  - 指向相关图位；任务级检查使用 `task`

总规则：
- 只要存在 `failed`，整体 `passed = false`
- 只要存在 `warning` 或 `failed`，整体 `review_required = true`

## 3. 当前检查项

### 3.1 工程类检查
- 输出尺寸是否正确
- 任务目录是否完整
- 结果图是否存在
- 导出 ZIP 是否存在

### 3.2 文字可读性检查
#### `text_background_contrast`
- 目标：
  - 判断文字区域背景是否与文字形成足够对比
- 当前策略：
  - 基于文字区域裁切背景的亮度范围、亮度波动做轻量评分

#### `text_area_complexity`
- 目标：
  - 判断文字区域纹理是否过于复杂
- 当前策略：
  - 基于局部边缘密度和灰度波动做规则判断

#### `text_safe_zone_check`
- 目标：
  - 判断实际文字区域是否明显压到主体高权重区域
- 当前策略：
  - 优先读取 `overlay_text` 回写的实际文本区域
  - 如果 state 没带上真实区域，则继续从 `final_text_regions.json / preview_text_regions.json` 恢复
  - 若没有实际渲染区域，则回退到 `layout_plan` 的 block 区域
  - 结合主体近似区域的重叠率和中心距离做 `warning / failed`
  - `details` 会明确记录：
    - `actual_render_region=yes/no`
    - `region_source=actual/fallback`

#### `text_readability_check`
- 目标：
  - 判断贴字后的文字区域是否具备基本可读性
- 当前策略：
  - 汇总文字区域背景对比度
  - 汇总背景复杂度
  - 汇总文字过密程度
  - 记录是否已经压到最小可读字号
  - 带出本次文字渲染使用的字体来源和 fallback 状态
  - 若 `overlay_text` 提供了 `overflow_detected`，直接按 `failed` 处理
  - 检查标题和副标题是否具备基本层级

当前最小可读字号约束：
- `title >= 40`
- `subtitle >= 24`
- `bullets >= 22`
- `cta >= 22`

如果文字在最小字号下仍然放不下：
- `overlay_text` 不会继续缩小
- 对应 block 会写出 `min_font_size_hit=true`
- 同时写出 `overflow_detected=true`
- `text_readability_check` 会把它视为失败风险

### 3.3 布局风险检查
#### `safe_zone_overlap_risk`
- 目标：
  - 判断当前文字块是否离主体中心高权重区域过近
- 当前策略：
  - 用近似主体区域和文字区域的重叠率、中心距离做风险评估

### 3.4 茶叶 Phase 1 图像层合同检查
#### `shot_completeness_check`
- 目标：
  - 检查茶叶 Phase 1 固定五图是否完整
- 规则：
  - `final` 必须是 5 张，缺图直接 `failed`
  - `preview` 可放宽，但会明确标成 `warning`
  - `details` 中会记录：
    - `render_variant`
    - `image_count`
    - `missing_shots`
    - `unexpected_shots`
    - `duplicate_shots`

#### `product_consistency_check`
- 目标：
  - 检查商品锚点是否还在，避免图生图结果跑偏
- 当前轻量策略：
  - `image_edit` 是否真的拿到了 `reference_assets`
  - 期望/实际 `generation_mode` 是否一致
  - OCR 是否还能读到关键品牌字样
  - 优先使用 `product_analysis.must_preserve_texts` 作为文字对比锚点
  - 当 `must_preserve_texts` 为空时，才对 `visual_identity.must_preserve / locked_elements` 做严格过滤 fallback
  - 主色锚点是否仍能在图片里检测到
  - 中心区域是否存在基本主体信号
- 典型触发：
  - `generation_mode=image_edit` 但没有参考图
  - 品牌字样没检出
  - 主色明显消失
  - 画面中心过于空或主体信号过弱

#### `shot_type_match_check`
- 目标：
  - 检查每张图是否仍符合固定图位类型
- 当前策略：
  - 先做 rule-based / metadata-based 检查，不引入重型 CV
  - 结合 `shot_plan + shot_prompt_specs` 的字段做最小约束判断
- 当前最小规则：
  - `hero_brand`
    - 应有 package / hero / brand 锚点
  - `carry_action`
    - 应有 hand / carry / gifting 锚点
  - `open_box_structure`
    - 应有 open / structure / inner layout 锚点
  - `dry_leaf_detail`
    - 应有 dry leaf / texture / detail 锚点
  - `tea_soup_experience`
    - 应有 tea soup / brewed / cup / vessel 锚点

## 4. `qc_report` 当前根字段
除了保留原有 `checks` 明细列表，当前还新增三类根级别字段：
- `shot_completeness_check`
- `product_consistency_check`
- `shot_type_match_check`
- `text_safe_zone_check`
- `text_readability_check`

这些字段是按检查类型归并后的摘要列表。每项至少包含：
- `status`
- `details`
- `related_shot_id`

## 5. 当前依赖字段
QC 会综合以下信息：
- `product_analysis`
- `shot_plan`
- `shot_prompt_specs`
- `layout_plan`
- `text_render_reports`
- `final_text_regions.json / preview_text_regions.json`
- `image_prompt_plan`
- `render_generation_mode`
- `render_reference_asset_ids`
- `generation_result`
- 结果图片本身

因此只要这些字段变化，通常都需要同步回看 QC 规则是否仍然成立。

## 6. preview / final 行为
- preview 和 final 都会执行 QC
- preview 的 QC 目标是快速暴露风险，不要求和 final 一样严格
- final 更适合做导出前复核
- 茶叶 Phase 1 固定五图完整性在 final 是硬约束，在 preview 是提示性约束

## 7. 典型排查方式

### final 图数不对
先看：
1. `shot_completeness_check`
2. `generation_result.images`
3. `shot_plan.json`

### image_edit 结果像是没保留原商品
先看：
1. `product_consistency_check`
2. `render_generation_mode`
3. `render_reference_asset_ids`
4. `product_analysis.json`
5. `shot_prompt_specs.json`

### 图位看起来不对
先看：
1. `shot_type_match_check`
2. `shot_plan.json`
3. `shot_prompt_specs.json`

### 文字压主体或看不清
先看：
1. `text_safe_zone_check`
2. `text_readability_check`
3. `layout_plan.json`
4. `overlay_text` 日志
5. `text_render_reports`
6. `final_text_regions.json / preview_text_regions.json`

额外关注这些字段：
- `font_source`
- `fallback_used`
- `requested_font_size / used_font_size`
- `min_font_size_hit`
- `overflow_detected`

## 8. 修改 QC 时必须同步更新的内容
只要改变以下任一项，就必须同步更新本文档：
- 检查项名称
- `passed / warning / failed` 判定逻辑
- `review_required` 汇总逻辑
- preview/final 的 QC 行为
- `details` 结构
- `qc_report` 根字段
## Product Consistency Evidence
- `product_consistency_check` 现在执行“有证据才能通过”的规则。
- 当前会检查的关键证据：
  - `brand_text_targets`
  - `text_anchor_source`
  - `text_anchor_status`
  - `text_anchor_count`
  - OCR 有效文本
  - `primary_color_detected`
  - `reference_asset_ids`（在 `image_edit` 期望或实际路径下）
- 如果关键证据缺失，不允许直接 `passed`：
  - 部分缺失：`warning`
  - 多项同时缺失，或 `image_edit` 关键参考图也缺失：通常 `failed`
- `details` 和汇总摘要会新增：
  - `evidence_completeness=full|partial|missing`
  - `evidence_issues`
  - `decision_reason`
## Tea Template Completeness
- `shot_completeness_check` 对茶叶 Phase 1 不再只写死礼盒模板。
- 它会优先依据当前 `product_analysis.package_template_family`、`product_analysis.asset_completeness_mode` / `shot_plan` 判断当前应该完整存在的五图集合。
- 这意味着：
  - 礼盒仍检查 `carry_action / open_box_structure`
  - 金属罐会区分 `packshot_only / packshot_plus_detail`
  - 袋装继续检查各自模板下的五图完整性

## 9. 本次补充：结果图证据优先

当前 QC 的目标是“更接近看结果图”，不是只看 prompt 和 metadata 是否自洽。

### `text_readability_check`
- 当前会优先读取真实渲染后的：
  - `used_font_size`
  - `min_font_size_hit`
  - `overflow_detected`
  - `merged_text_region`
- 商用最小可读字号阈值固定为：
  - `title >= 40`
  - `subtitle >= 24`
  - `bullets >= 22`
  - `cta >= 22`
- 判定规则：
  - 小于阈值但未严重越界：`warning`
  - 小于阈值的 `80%`：`failed`
  - `merged_text_region_ratio < 0.012`：`warning`
  - `merged_text_region_ratio < 0.006`：`failed`
  - `overflow_detected=true`：直接 `failed`
- `details` 当前会显式写出：
  - `used_font_sizes`
  - `font_size_source`
  - `merged_text_region_ratio`
  - `region_ratio_source`
  - `min_readable_thresholds`

### `shot_type_match_check`
- 当前不再只看 `shot_plan + shot_prompt_specs`
- 仍保留 metadata 规则，但新增轻量图像规则：
  - `package_detail`
    - 不能与 hero 图高度同构
    - 需要有细节纹理增强信号
  - `dry_leaf_detail`
    - 需要有明显非包装前景纹理主体信号
  - `tea_soup_experience`
    - 需要有茶汤/液体/杯具类视觉信号
  - `lifestyle_or_brewing_context / package_in_brewing_context`
    - 需要有外围 props 或 scene context 信号
- `details` 会区分：
  - `metadata_warnings`
  - `visual_warnings`
  - `visual_metrics`

### `product_consistency_check`
- 当前明确拆成三层判断：
  - `visual_consistency`
  - `text_anchor_consistency`
  - `evidence_completeness`
- 当 `must_preserve_texts` 存在但 OCR 读不到时：
  - `text_anchor_consistency=ocr_missing`
  - `evidence_completeness` 不能记为 `full`
- 仍会优先消费 `product_analysis.must_preserve_texts`
- 只有 provider 没给出可靠文字锚点时，才回退到 `visual_identity.must_preserve / locked_elements`

### `visual_shot_diversity_check`
- 当前为任务级新增检查
- 适用范围：茶叶 Phase 1 且结果图数量足够时
- 轻量比较以下信号：
  - 主体布局相似度
  - 中心构图相似度
  - 颜色分布相似度
- 如果多张图过于接近 hero packshot，会给出 `warning`
- `details` 会指出：
  - `similar_pairs`
  - `hero_like_shots`
  - `hero_shot_id`
