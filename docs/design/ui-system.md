# UI 系统规范（AI 电商图片生成平台）

> 适用范围：当前仓库前端（React）所有页面，优先覆盖“主图生成工作台”。
> 
> 目标：统一视觉语言、降低页面风格漂移、支持后续组件化与高效迭代。

## 1. 设计原则

- **专业克制**：避免花哨动效和高饱和拼色，优先可读性与任务效率。
- **任务导向**：所有视觉强调服务于“上传 → 配置 → 生成 → 查看结果”。
- **一致优先**：同类元素（卡片、标签、按钮、表单）在全站只保留一套主规则。
- **可实现性**：所有规则可映射到 React + CSS Variables（或 Tailwind token）实现。

---

## 2. 颜色系统（Light Theme）

> 主色方向：蓝紫强调 + 浅灰蓝背景 + 白卡片。

### 2.1 语义色板（Design Tokens）

```css
:root {
  /* Brand */
  --color-brand-50: #EEF2FF;
  --color-brand-100: #E0E7FF;
  --color-brand-500: #6366F1;   /* 主强调色 */
  --color-brand-600: #5B5FEF;
  --color-brand-700: #4F46E5;

  /* Accent */
  --color-accent-500: #8B5CF6;  /* 紫色辅助强调，用于渐变尾色/次级强调 */

  /* Neutral */
  --color-bg-page: #F3F7FF;      /* 页面浅灰蓝背景 */
  --color-bg-elevated: #FFFFFF;  /* 卡片背景 */
  --color-bg-subtle: #F8FAFF;    /* 弱分区底色 */
  --color-border: #E6EAF2;
  --color-border-strong: #D8DFEA;

  /* Text */
  --color-text-primary: #0F172A;
  --color-text-secondary: #334155;
  --color-text-tertiary: #64748B;
  --color-text-disabled: #94A3B8;

  /* State */
  --color-success-bg: #DCFCE7;
  --color-success-text: #166534;
  --color-warning-bg: #FEF3C7;
  --color-warning-text: #92400E;
  --color-error-bg: #FEE2E2;
  --color-error-text: #991B1B;
  --color-info-bg: #DBEAFE;
  --color-info-text: #1E3A8A;
}
```

### 2.2 色彩使用比例

- 页面背景/容器：**70%**（`--color-bg-page` / `--color-bg-elevated`）
- 文本与边框：**20%**（中性灰蓝）
- 强调色与状态色：**10%**（按钮、进度、选中态、标签）

### 2.3 对比度要求

- 正文文字对背景对比度 ≥ 4.5:1。
- 小号辅助文字（12px）必须使用 `--color-text-secondary` 及以上对比度。
- 禁止仅靠颜色区分状态，需同时提供文字/图标。

---

## 3. 字体与层级

## 3.1 字体家族

- 中文优先：`"PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif`
- 英文/数字可混排：`"Plus Jakarta Sans"`（可选）

## 3.2 字号层级

- H1 页面主标题：`28 / 36`，`700`
- H2 模块标题：`22 / 30`，`600`
- H3 卡片标题：`18 / 26`，`600`
- Body 主体：`14 / 22`，`400~500`
- Caption 辅助：`12 / 18`，`400`
- Label 表单标签：`13 / 20`，`500`

> 规则：同一页面字号层级不超过 5 档；避免 11px 以下文本。

---

## 4. 间距系统（8pt Grid）

- 基础单位：`4px`
- 推荐序列：`4 / 8 / 12 / 16 / 24 / 32 / 40 / 48`

### 4.1 间距建议

- 页面主容器内边距：`24~32px`
- 卡片内边距：`20~24px`
- 表单项垂直间距：`12~16px`
- 区块之间：`24px`
- 强分组之间：`32px`

---

## 5. 圆角规范

- 页面级卡片：`16px`
- 上传框、参数面板、结果卡：`14~16px`
- 输入框/下拉/按钮：`10~12px`
- 标签（pill）：`999px`

> 统一策略：大容器大圆角，小控件小圆角；禁止同屏出现过多不规则圆角值。

---

## 6. 阴影规范

- 卡片默认阴影：`0 4px 16px rgba(15, 23, 42, 0.06)`
- 悬浮强化：`0 8px 24px rgba(15, 23, 42, 0.10)`
- 顶部导航轻浮层：`0 2px 10px rgba(15, 23, 42, 0.06)`

> 禁止重阴影、黑色大面积投影；保持“轻、薄、透”。

---

## 7. 动效与交互反馈

- 动效时长：`150~220ms`
- 缓动：`ease-out`
- Hover：优先颜色/边框/阴影微变，不做位移跳动
- Focus：必须有 2px 可见焦点环（品牌浅色）
- 禁止全局高频闪烁、弹跳、旋转等干扰动效

---

## 8. React 实现建议（Token 化）

- 建议在 `frontend/src/styles/tokens.css` 维护 CSS Variables。
- 组件仅引用语义 token，不直接硬编码 hex。
- 统一状态命名：`default / hover / active / disabled / loading / success / warning / error`。
- 保留深色模式扩展位，但本阶段只落地浅色主题。

---

## 9. 可访问性基线

- 所有输入控件需有可见 `label`。
- 图片缩略图需有 `alt`（如“生成结果图 1”）。
- 状态标签需文本明确（完成/队列中/失败），不可仅图标。
- 键盘可达：Tab 顺序符合“左侧操作流 → 右侧结果流”。
