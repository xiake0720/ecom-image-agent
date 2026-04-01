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
