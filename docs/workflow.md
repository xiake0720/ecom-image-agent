# Workflow 说明（当前）

## 主图工作流
后端 `POST /api/image/generate-main` 会调用既有 `backend.engine.workflows.graph.run_workflow` 固定主链：
1. ingest_assets
2. director_v2
3. prompt_refine_v2
4. render_images
5. run_qc
6. finalize

任务目录仍落盘到 `outputs/tasks/{task_id}/`。

## 新增详情页流程
`POST /api/detail/generate` 走独立详情页服务，不干扰主图工作流：
1. 解析平台/风格模板
2. 根据商品数据组装模块数组
3. 落盘 `detail_page_modules.json`
4. 返回预览数据与导出素材清单

## 任务状态
- 主图任务：由既有 workflow 状态推进
- 详情页任务：同步完成后写入 `storage/tasks/index.json`

## 前端主图工作台页面结构（React，第二轮）
- 路由：`/main-images`。
- 默认首页：`/` 自动重定向到 `/main-images`。
- 页面结构固定为三段：
  1. 顶部导航栏（品牌区、一级导航、任务状态/通知/设置）
  2. 左侧操作面板（上传商品图、上传参考图、平台选择、风格选择、参数设置、文案备注、执行按钮）
  3. 右侧任务进度与结果区（顶部进度总览 + 下方三列结果图卡片）
- 本轮仅重构前端布局与样式层，不改变后端主图接口契约，仍使用 multipart 提交 `product_name` 与 `white_bg` 到 `/api/image/generate-main`。
