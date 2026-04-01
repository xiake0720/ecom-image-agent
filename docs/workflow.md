# Workflow 说明（当前）

## 主图工作流
后端 `POST /api/image/generate-main` 继续复用既有 `backend.engine.workflows.graph.run_workflow` 固定主链路：
1. `ingest_assets`
2. `director_v2`
3. `prompt_refine_v2`
4. `render_images`
5. `run_qc`
6. `finalize`

任务目录继续落盘到 `outputs/tasks/{task_id}/`。

## 主图接口行为
- `POST /api/image/generate-main` 当前行为：
  1. 生成 `task_id`
  2. 创建任务目录与 `task.json`
  3. 落盘上传素材到 `outputs/tasks/{task_id}/inputs/`
  4. 写入任务索引
  5. 放入进程内主图队列
  6. 单 worker 串行执行 workflow
- 主图提交字段已由前端完整接线：
  - `white_bg`
  - `detail_files`
  - `bg_files`
  - `brand_name`
  - `product_name`
  - `category`
  - `platform`
  - `style_type`
  - `style_notes`
  - `shot_count`
  - `aspect_ratio`
  - `image_size`

## 主图运行时查询
工作台专用运行时接口：
- `GET /api/tasks/{task_id}/runtime`
  - 直接读取 `task.json`、`prompt_plan_v2.json`、`qc_report.json` 与 `outputs/tasks/{task_id}/final/`
  - 返回进度、当前步骤、队列位置、provider/model 摘要、QC 摘要、结果 ZIP 链接和结果图列表
- `GET /api/tasks/{task_id}/files/{file_name}`
  - 访问当前任务输出目录下的真实文件
  - 用于结果图卡片、大图预览和 ZIP 下载

## 前端主图工作台页面（React）
- 默认首页路由：访问 `/` 会重定向到 `/main-images`。
- 页面结构保持三段式：
  1. 顶部导航栏
  2. 左侧操作区
  3. 右侧任务进度与结果区
- 左侧提交区新增背景参考图上传区：
  - 产品参考图通过 `detail_files` 提交
  - 背景参考图通过 `bg_files` 提交
- 前端数据流：
  1. 左侧表单通过 `frontend/src/services/mainImageApi.ts` 提交真实 multipart 数据
  2. 提交成功后保存 `task_id`
  3. 右侧通过 `frontend/src/services/taskApi.ts` 轮询 `/api/tasks/{task_id}/runtime`
  4. 用真实 `progress_percent / current_step / message / qc_summary / results[]` 驱动进度区和结果区
  5. 页面刷新后会从 `localStorage` 恢复最近一次 `task_id` 并继续展示
  6. 任务记录页可把任意历史 `task_id` 写回 `localStorage`，并跳回工作台恢复查看
- 轮询停止条件：
  - `status` 为 `completed`
  - `status` 为 `review_required`
  - `status` 为 `failed`
- 结果区新增导出能力：
  - 下载最终结果 ZIP
  - 下载完整任务包 ZIP
- 结果图卡片和大图预览均不再使用硬编码假图，图片地址全部来自 runtime 接口返回并在前端解析为绝对 URL。

## 任务记录页
- `GET /api/tasks` 返回的摘要已可直接驱动任务记录页：
  - 进度百分比
  - 当前步骤
  - 结果数量
  - provider / model 摘要
  - 产品参考图与背景参考图数量
  - 结果 ZIP 下载入口
- 任务记录页当前支持：
  - 一键打开工作台恢复当前任务
  - 下载已存在的结果 ZIP

## 详情页流程
`POST /api/detail/generate` 继续走独立详情页服务，不干扰主图工作流：
1. 解析平台与风格模板
2. 根据商品数据组装模块数组
3. 落盘 `detail_page_modules.json`
4. 返回预览数据与导出素材清单

## 任务状态
- 主图任务：`created -> running -> completed / review_required / failed`
- 主图队列：同一进程内单 worker 串行执行
- 详情页任务：同步完成后写入任务索引
