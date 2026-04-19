# 前端工作台说明

## 1. 一期可见页面
- 主图工作台：[ `frontend/src/pages/MainImagePage.tsx` ](/D:/python/ecom-image-agent/frontend/src/pages/MainImagePage.tsx)
- 详情图工作台：[ `frontend/src/pages/DetailPageGeneratorPage.tsx` ](/D:/python/ecom-image-agent/frontend/src/pages/DetailPageGeneratorPage.tsx)
- 历史任务页：[ `frontend/src/pages/TasksPage.tsx` ](/D:/python/ecom-image-agent/frontend/src/pages/TasksPage.tsx)
- 登录页：[ `frontend/src/pages/LoginPage.tsx` ](/D:/python/ecom-image-agent/frontend/src/pages/LoginPage.tsx)
- 注册页：[ `frontend/src/pages/RegisterPage.tsx` ](/D:/python/ecom-image-agent/frontend/src/pages/RegisterPage.tsx)

统一壳层组件：
- [ `frontend/src/components/layout/PageShell.tsx` ](/D:/python/ecom-image-agent/frontend/src/components/layout/PageShell.tsx)
- [ `frontend/src/components/layout/AppTopBar.tsx` ](/D:/python/ecom-image-agent/frontend/src/components/layout/AppTopBar.tsx)
- [ `frontend/src/config/v1Scope.ts` ](/D:/python/ecom-image-agent/frontend/src/config/v1Scope.ts)

## 2. 一期隐藏页面
以下页面代码保留，但当前前端不再开放入口：
- [ `frontend/src/pages/DashboardPage.tsx` ](/D:/python/ecom-image-agent/frontend/src/pages/DashboardPage.tsx)
- [ `frontend/src/pages/TemplatesPage.tsx` ](/D:/python/ecom-image-agent/frontend/src/pages/TemplatesPage.tsx)
- [ `frontend/src/pages/PreviewPage.tsx` ](/D:/python/ecom-image-agent/frontend/src/pages/PreviewPage.tsx)
- [ `frontend/src/pages/SettingsPage.tsx` ](/D:/python/ecom-image-agent/frontend/src/pages/SettingsPage.tsx)
- [ `frontend/src/pages/AssetsLibraryPage.tsx` ](/D:/python/ecom-image-agent/frontend/src/pages/AssetsLibraryPage.tsx)

直接访问这些隐藏路由时，前端统一重定向到 `/main-images`。

## 3. 主图工作台
### 3.1 路由
- `/main-images`

### 3.2 主要职责
- 上传白底商品图、参考图、背景参考图
- 提交主图任务
- 轮询 `GET /api/tasks/{task_id}/runtime`
- 展示进度、QC 摘要、结果卡片和下载入口
- 从当前任务跳转到详情图工作台

## 4. 详情图工作台
### 4.1 路由
- `/detail-pages`

### 4.2 入口方式
- 常规进入：`/detail-pages`
- 从主图工作台导入主图任务：`/detail-pages?main_task_id={task_id}`
- 从历史任务页回看详情图任务：`/detail-pages?task_id={task_id}`

### 4.3 主要职责
- 上传详情图素材
- 选择主图任务结果作为输入
- 提交规划任务或完整详情图任务
- 轮询 `GET /api/detail/jobs/{task_id}/runtime`
- 展示 plan/copy/prompt/result/runtime/QC
- 预览与下载单张结果图、ZIP

## 5. 历史任务页
### 5.1 路由
- `/tasks`

### 5.2 当前支持的任务类型
- `main_image`
  - 打开主图工作台回看 runtime 和结果图。
- `detail_page`
  - 打开详情图工作台回看 runtime 和结果图。
- `image_edit`
  - 展示图片编辑任务 runtime 和结果摘要。
  - 源结果图的编辑入口位于结果卡片内。

### 5.3 当前数据源
- 任务列表：`GET /api/v1/tasks`
- runtime 摘要：`GET /api/v1/tasks/{task_id}/runtime`
- 结果摘要：`GET /api/v1/tasks/{task_id}/results`
- 结果下载：`GET /api/v1/files/{file_id}/download-url`
- 创建图片编辑：`POST /api/v1/results/{result_id}/edits`
- 图片编辑历史：`GET /api/v1/results/{result_id}/edits`

历史任务页支持分页、`task_type` 筛选和 `status` 筛选，所有数据按当前登录用户隔离。

### 5.4 单图编辑入口
- 支持在图片结果卡片中展开“局部编辑”面板。
- 当前实现矩形选区，坐标以 `ratio` 写入后端。
- 支持编辑指令输入和示例指令快捷填充。
- 编辑历史会展示任务状态、执行模式和派生版本预览。

## 6. 认证页面边界
- `/login` 和 `/register` 已接入后端真实认证 API：
  - `POST /api/v1/auth/register`
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/refresh`
  - `POST /api/v1/auth/logout`
  - `GET /api/v1/auth/me`
- access token 保存在前端 `localStorage`
- refresh token 由后端写入 HttpOnly cookie
- `frontend/src/services/http.ts` 统一注入 Bearer token 并启用 `withCredentials`
- `/main-images`、`/detail-pages`、`/tasks` 已受登录态保护

## 7. 当前未交付能力
以下能力仍未交付：
- 画笔 / mask 涂抹
- 图层系统
- 原生 inpainting provider 适配
- COS-only 源图的 worker 侧自动拉取

## 8. 样式文件
- 主图页样式：[ `frontend/src/pages/MainImagePage.css` ](/D:/python/ecom-image-agent/frontend/src/pages/MainImagePage.css)
- 详情图页样式：[ `frontend/src/pages/DetailPageGeneratorPage.css` ](/D:/python/ecom-image-agent/frontend/src/pages/DetailPageGeneratorPage.css)
- 任务页样式：[ `frontend/src/pages/TasksPage.css` ](/D:/python/ecom-image-agent/frontend/src/pages/TasksPage.css)
- 全站壳层样式：[ `frontend/src/styles/console.css` ](/D:/python/ecom-image-agent/frontend/src/styles/console.css)

## 9. COS 直传接入状态
- 已新增 `frontend/src/services/storageApi.ts`：
  - `createStoragePresign`
  - `uploadFileToPresignedUrl`
  - `fetchFileDownloadUrl`
  - `calculateFileSha256`
- 当前主图 / 详情图页面仍默认走原 multipart 提交流程。
- 完整页面级切换需要后续把生成流程改成“先建任务 / 再直传素材 / 再触发生成”；阶段 5 已完成登录态、受保护路由和任务恢复。

## 10. 阶段 5 文档
阶段 5 前端真实化细节见：
- `docs/frontend-v1-pages.md`
