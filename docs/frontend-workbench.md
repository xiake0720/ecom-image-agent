# 前端工作台说明（MainImagePage）

## 1. 页面定位
- 核心页面：`frontend/src/pages/MainImagePage.tsx`
- 路由：`/main-images`
- 角色：主图任务提交、进度观测、结果预览/下载的一站式工作台。

## 2. 页面布局
页面为三段式：
1. 顶部栏：品牌标识、导航占位、任务状态芯片与操作按钮。
2. 左侧参数区：上传与参数配置、任务提交。
3. 右侧结果区：流程进度、运行状态、结果卡片、预览弹层。

## 3. 左侧上传与参数区

### 3.1 上传区
- 白底主图（必填）：`white_bg`
- 商品参考图（可选，多图）：`detail_files`
- 背景参考图（可选，多图）：`bg_files`

### 3.2 参数区
- 品牌名、商品名
- 平台（天猫/京东/拼多多/抖音）
- 类目（当前仅茶叶）
- 风格标签组合（写入 `style_type`）
- 图数 `shot_count`
- 比例 `aspect_ratio`
- 图尺寸 `image_size`
- 风格补充说明 `style_notes`

## 4. 右侧进度与结果区
- 流程阶段条：`ingest_assets -> director_v2 -> prompt_refine_v2 -> render_images -> run_qc -> finalize`
- 进度信息来自 runtime：`progress_percent`、`current_step`、`message`
- 状态补充：队列位置、provider/model、参考图数量、QC 摘要
- 结果卡片来自 `results[]`，支持大图预览与下载。

## 5. 前端数据流
1. 页面调用 `submitMainImageTask` 组装并提交 multipart。
2. 成功后保存 `task_id` 到页面状态与 localStorage。
3. 页面轮询 `fetchTaskRuntime(task_id)` 获取运行时数据。
4. runtime 返回的相对 URL 由 `resolveApiUrl` 解析成可访问地址。
5. 卡片点击触发预览弹层，下载按钮走直接 URL 下载。

## 6. 轮询逻辑
- 轮询间隔：3 秒。
- 任务处于终态（如 completed/failed/review_required）后停止轮询。
- 页面刷新会读取 localStorage 中最近任务并恢复展示。
- 当任务不存在（404 业务错误）时，自动清理 localStorage 中缓存任务 ID。

## 7. 结果预览逻辑
- 仅当卡片存在 `image_url` 时允许预览。
- 预览弹层开启时锁定页面滚动；`Esc` 可关闭。
- 下载文件名优先取 `file_name` 最后一级，缺省回落为 `{card.id}.png`。


## 8. 工作台与全站壳层统一
- 主图页已接入统一壳层 `PageShell` 与统一顶栏 `AppTopBar`，与模板中心、详情页、预览中心、资源库、设置、数据中心保持同一视觉体系。
- 主图页核心上传/提交/轮询/结果逻辑保持不变，仅统一页面外壳与导航结构。

## 9. Mock 页面补充
- 详情长图编辑、模板中心、预览中心、资源库、系统设置、数据中心、登录页均采用 `frontend/src/mocks/` 的 mock 数据驱动，不依赖后端接口。
- 页面路由见 `README.md` 的“当前前端页面路由”。

## 10. 第二轮 UI 精修与响应式规则（2026-04-02）
- 本轮未新增页面，基于既有页面进行比例与节奏精修，保留当前 mock 数据结构与路由。
- 统一断点策略：
  - `<= 1440`：小桌面（压缩容器宽度、减少卡片间距、降低网格列数）
  - `1441 ~ 1920`：标准桌面（默认容器）
  - `1921 ~ 2560`：2K（增大容器宽度、扩展卡片列数）
  - `>= 2561`：大屏扩展（继续放宽容器与网格上限，避免内容缩在中间）
- 全站壳层统一：`frontend/src/styles/console.css`
  - 统一 `console-main` / `app-topbar` 宽度策略（由变量控制而非固定 `max-width`）。
  - 统一页面级 spacing、卡片 padding、控件高度、标题字号基线。
- 页面级精修：`frontend/src/pages/WorkbenchRefine.css`
  - 详情长图编辑页三栏改为“左右栏受控 + 中间自适应扩展”。
  - 预览中心、模板中心、资源库、数据中心、系统设置统一为可复用 grid 规则。
  - 登录页补充大屏背景层次与卡片节奏。
- 主图工作台保持原业务链路（提交、轮询、预览、下载）不变，仅增强 2K/4K 下容器与结果区宽度利用。
