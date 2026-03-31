# 详情页生成设计

## 目标
实现“模板驱动 + 数据驱动”的详情页生成，先输出结构化 JSON，再由前端渲染预览。

## 输入
- 商品信息：标题、副标题、卖点、规格、价格段、平台
- 主图结果：历史主图路径或任务 ID
- 原图/包装图
- 可选文案
- 平台与风格模板选择

## 输出
- `detail_page_modules.json`
- 预览数据（`preview_data`）
- 导出素材清单（`export_assets`）
- 可直接渲染的 `modules[]`

## 默认模块（可插拔）
- 顶部卖点横幅
- 主视觉
- 核心卖点
- 茶汤/茶干/叶底/包装
- 规格参数
- 场景
- 冲泡建议
- 人群推荐
- 品质背书
- 售后/发货

## 平台差异模板
- `backend/templates/detail_pages/tmall_premium.json`
  - 强调品牌感、质感、叙事层次。
- `backend/templates/detail_pages/pinduoduo_value.json`
  - 强调利益点、转化导向、短平快结构。
