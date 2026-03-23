# QC Policy

## 当前 QC 范围
v2 只保留最小闭环 QC：

- 图数完整性
- 最终图片文件存在且非空
- 是否使用 overlay fallback

## 判定规则

### `shot_completeness_check`
- 期望图数与实际图数一致：`passed`
- 缺图：`failed`

### `render_output_check`
- 图片文件存在且文件大小大于 0：`passed`
- 否则：`failed`

### `overlay_fallback_check`
- 未使用 fallback：`passed`
- 使用 fallback：`warning`

## 结果解释
- 任一 `failed`：`passed=false`
- 存在 `warning` 或 `failed`：`review_required=true`

## 当前不再包含
- OCR 文本可读性打分
- 旧 overlay 节点回写区域解析
- 茶叶模板专属 QC
- 旧品牌锚点与风格锚点审查
