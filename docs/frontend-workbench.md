# 前端工作台说明

## 1. 页面总览
- 主图工作台：[`frontend/src/pages/MainImagePage.tsx`](/D:/python/ecom-image-agent/frontend/src/pages/MainImagePage.tsx)
- 详情图工作台：[`frontend/src/pages/DetailPageGeneratorPage.tsx`](/D:/python/ecom-image-agent/frontend/src/pages/DetailPageGeneratorPage.tsx)

两页都接入：
- [`PageShell`](/D:/python/ecom-image-agent/frontend/src/components/layout/PageShell.tsx)
- [`PageHeader`](/D:/python/ecom-image-agent/frontend/src/components/common/PageHeader.tsx)
- [`SectionCard`](/D:/python/ecom-image-agent/frontend/src/components/common/SectionCard.tsx)

## 2. 主图工作台

### 2.1 路由
- `/main-images`

### 2.2 主要职责
- 上传白底图、参考图、背景图
- 提交主图任务
- 轮询主图 runtime
- 展示进度、QC 摘要、结果卡片
- 结果预览与下载

### 2.3 主图数据流
1. 页面调用 `submitMainImageTask`
2. 后端返回 `task_id`
3. 页面轮询 `fetchTaskRuntime(task_id)`
4. runtime 返回进度、队列、QC、结果 URL
5. 页面展示真实任务状态与结果图

## 3. 详情图工作台

### 3.1 路由
- `/detail-pages`

### 3.2 当前正式布局
详情图页已重构为三栏工作台：
- 左栏：输入与素材控制
- 中栏：主图导入预览、规划预览、文案预览、Prompt 摘要、结果图区
- 右栏：状态、进度、QC、错误、ZIP 下载

### 3.3 组件拆分
- [`DetailTaskSourcePicker`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailTaskSourcePicker.tsx)
- [`DetailMainResultGallery`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailMainResultGallery.tsx)
- [`DetailAssetUploader`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailAssetUploader.tsx)
- [`DetailProductForm`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailProductForm.tsx)
- [`DetailGoalForm`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailGoalForm.tsx)
- [`DetailPlanPreview`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailPlanPreview.tsx)
- [`DetailCopyPreview`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailCopyPreview.tsx)
- [`DetailPromptPreview`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailPromptPreview.tsx)
- [`DetailResultGallery`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailResultGallery.tsx)
- [`DetailRuntimeSidebar`](/D:/python/ecom-image-agent/frontend/src/components/detail/DetailRuntimeSidebar.tsx)

### 3.4 输入区能力
- 选择主图任务来源
- 自动读取主图任务 completed 结果
- 主图结果图卡多选
- 包装图、茶干图、茶汤图、叶底图、场景参考图、背景参考图上传
- 商品信息、参数、冲泡建议录入
- 目标屏数选择，当前支持 `8-12`
- 卖点、风格补充、额外要求录入

### 3.5 中栏能力
- 主图导入图卡预览
- 规划预览（按单屏卡片展示）
- 文案预览
- Prompt 摘要预览
- 结果图预览
- 单张下载
- 错误横幅

### 3.6 右栏能力
- 任务状态芯片
- 进度条
- 当前阶段
- 已生成 / 计划数量
- QC 问题列表
- 真实错误信息
- ZIP 下载入口

### 3.7 运行状态
页面显式支持：
- `loading`
- `error`
- `empty`
- `success`
- `selected`
- `generating`
- `completed`
- `failed`

具体表现：
- 主图图卡有选中态
- 按钮有 loading 文案
- runtime 侧栏显示状态 badge
- 中栏展示错误横幅
- 结果图区按单页状态区分 `queued/running/completed/failed`

### 3.8 详情图数据流
1. 页面通过 [`frontend/src/services/detailPageApi.ts`](/D:/python/ecom-image-agent/frontend/src/services/detailPageApi.ts) 提交：
   - `POST /api/detail/jobs/plan`
   - `POST /api/detail/jobs`
2. 成功后保存 `task_id`
3. 页面轮询 `GET /api/detail/jobs/{task_id}/runtime`
4. runtime 返回：
   - `plan`
   - `copy_blocks`
   - `prompt_plan`
   - `qc_summary`
   - `images`
   - `export_zip_url`
   - `error_message`
5. 页面按真实 runtime 更新中栏与右栏

### 3.9 主图来源导入规则
- 如果 URL 自带 `main_task_id`，页面会自动读取该主图任务
- 页面默认选中第一张 completed 结果
- 主图结果以图卡展示，不再用 checkbox 列表

## 4. 样式文件
- 主图页样式：[`frontend/src/pages/MainImagePage.css`](/D:/python/ecom-image-agent/frontend/src/pages/MainImagePage.css)
- 详情图页样式：[`frontend/src/pages/DetailPageGeneratorPage.css`](/D:/python/ecom-image-agent/frontend/src/pages/DetailPageGeneratorPage.css)
- 全站壳层样式：[`frontend/src/styles/console.css`](/D:/python/ecom-image-agent/frontend/src/styles/console.css)

## 5. 详情图页面当前设计原则
- 保留现有工作台视觉语言，不另起一套站点壳层
- 强化图卡选中态、hover/focus 与错误提示
- 把 plan/copy/prompt/result 明确拆段展示
- 右栏只做导演控制台，不做前端拼图或本地合成详情图
> 2026-04 update:
> - Detail page visuals are aligned with the main workbench theme.
> - Imported main-image cards, generated result cards, and preview modal use a `3:4` display ratio.
