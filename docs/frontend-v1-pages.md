# 前端 V1 页面真实化说明

## 1. 当前目标
阶段 5 已把前端从演示壳层推进到最小真实流程：
- 登录 / 注册接入后端 v1 认证 API
- 工作台路由受登录态保护
- 历史任务页接入 `/api/v1/tasks*`
- 主图 / 详情图任务可从历史页恢复
- 非一期页面继续隐藏入口，不删除旧代码

## 2. 认证链路
相关文件：
- `frontend/src/types/auth.ts`
- `frontend/src/services/authApi.ts`
- `frontend/src/services/authToken.ts`
- `frontend/src/auth/AuthProvider.tsx`
- `frontend/src/auth/RouteGuards.tsx`
- `frontend/src/hooks/useAuth.ts`

行为：
- 登录：`POST /api/v1/auth/login`
- 注册：`POST /api/v1/auth/register`
- 恢复登录态：优先 `GET /api/v1/auth/me`，失败后尝试 `POST /api/v1/auth/refresh`
- 登出：`POST /api/v1/auth/logout`
- access token 保存在浏览器 `localStorage`
- refresh token 仍由后端写入 HttpOnly cookie
- `frontend/src/services/http.ts` 统一注入 `Authorization: Bearer <token>` 并启用 `withCredentials`

## 3. 受保护路由
受保护页面：
- `/main-images`
- `/detail-pages`
- `/tasks`

未登录访问上述页面时，会跳转到：
```text
/login?redirect={原路径}
```

已登录访问 `/login` 或 `/register` 时，会重定向到 `/main-images`。

## 4. 历史任务页
相关文件：
- `frontend/src/pages/TasksPage.tsx`
- `frontend/src/pages/TasksPage.css`
- `frontend/src/services/taskApi.ts`
- `frontend/src/types/api.ts`

正式 API：
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}/runtime`
- `GET /api/v1/tasks/{task_id}/results`

页面能力：
- 分页
- `task_type` 筛选
- `status` 筛选
- runtime 摘要查看
- task_events 查看
- task_results 结果摘要查看
- 结果下载通过 `GET /api/v1/files/{file_id}/download-url`

## 5. 任务恢复
恢复规则：
- `main_image`：写入 `main-image-active-task-id`，跳转 `/main-images`
- `detail_page`：跳转 `/detail-pages?task_id={task_id}`
- `image_edit`：保留类型显示，正式恢复入口留给阶段 6

详情图页面的“主图任务来源”已切换到 v1 历史任务接口：
- 读取 `GET /api/v1/tasks?task_type=main_image&page_size=12`
- 选中主图任务后仍复用旧 runtime：`GET /api/tasks/{task_id}/runtime`

这样做的原因是：阶段 5 只做前端真实化和任务恢复，不替换主图 / 详情图原有 runtime 展示结构。

## 6. 非一期页面
以下页面代码继续保留，但路由和导航入口仍隐藏：
- `/dashboard`
- `/templates`
- `/preview`
- `/settings`
- `/assets-library`

## 7. 当前限制
- 主图 / 详情图创建接口仍是旧 multipart 入口，但前端会自动携带 Bearer token，后端会把任务归属当前登录用户。
- COS 直传 service 已存在，但主图 / 详情图页面尚未切换为“先建任务、再直传素材、再触发生成”的完整流程。
- `image_edit` 只是 v1 任务类型之一，页面级编辑能力留到阶段 6。
