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
- `detail_page_v2`
  - 打开详情图工作台回看 runtime 和结果图。
- `detail_page`
  - 标记为 deprecated，只展示历史索引，不再作为一期正式入口。

## 6. 认证页面边界
- `/login` 和 `/register` 仍是前端壳层页面。
- 后端真实认证 API 已存在：
  - `POST /api/v1/auth/register`
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/refresh`
  - `POST /api/v1/auth/logout`
  - `GET /api/v1/auth/me`
- 当前前端尚未把表单、token 存储、路由守卫和退出流程接到这套 API。
- 对外口径应描述为：后端账号体系已具备最小骨架，前端登录态接入尚未完成。

## 7. 当前未交付能力
一期目标中，“单张图片局部标记后二次生成”仍未在前端形成正式页面和正式协议：
- 没有正式页面路由
- 没有正式 API service
- 没有任务回看/继续编辑链路

该能力不应对外宣称已可用。

## 8. 样式文件
- 主图页样式：[ `frontend/src/pages/MainImagePage.css` ](/D:/python/ecom-image-agent/frontend/src/pages/MainImagePage.css)
- 详情图页样式：[ `frontend/src/pages/DetailPageGeneratorPage.css` ](/D:/python/ecom-image-agent/frontend/src/pages/DetailPageGeneratorPage.css)
- 任务页样式：[ `frontend/src/pages/TasksPage.css` ](/D:/python/ecom-image-agent/frontend/src/pages/TasksPage.css)
- 全站壳层样式：[ `frontend/src/styles/console.css` ](/D:/python/ecom-image-agent/frontend/src/styles/console.css)
