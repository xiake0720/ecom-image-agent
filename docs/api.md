# API 文档

## 1. 统一响应结构
除文件流接口外，后端统一返回 envelope：

```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "requestId": "req_xxx"
}
```

错误时：
- `code`：业务错误码
- `message`：可直接展示的错误摘要
- `requestId`：用于日志排查

## 2. API v1 规范
当前正式 v1 模块：
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/tasks/{task_id}/runtime`
- `GET /api/v1/tasks/{task_id}/results`
- `POST /api/v1/storage/presign`
- `GET /api/v1/files/{file_id}/download-url`

v1 任务接口约束：
- 必须携带 `Authorization: Bearer <access_token>`
- 任务查询严格按当前登录用户隔离
- v1 任务接口读取 PostgreSQL 中的任务镜像数据
- runtime 聚合仍会优先复用本地 `task.json` 和任务目录产物

v1 文件接口约束：
- 必须携带 `Authorization: Bearer <access_token>`
- 上传签名只支持图片文件
- 下载 URL 必须先校验 `task_assets` / `task_results` 的 `user_id`
- COS 未启用时，下载 URL 回退旧本地文件接口

生成任务执行约束：
- `ECOM_CELERY_ENABLED=false` 时，主图 / 详情图继续使用旧进程内队列。
- `ECOM_CELERY_ENABLED=true` 时，主图 / 详情图创建本地任务和数据库任务镜像后提交 Celery worker。
- 两种模式均返回原有 `task_id`，旧前端轮询路径保持兼容。

## 3. 认证 API
### 3.1 登录态约定
- Access token：JWT，放在响应体，由前端通过 `Authorization: Bearer <token>` 发送。
- Refresh token：放在 HttpOnly cookie，默认 cookie 名为 `ecom_refresh_token`。
- `POST /api/v1/auth/refresh` 和 `POST /api/v1/auth/logout` 依赖 refresh cookie。
- Refresh token 持久化只保存哈希，不保存明文。
- 前端已统一在 `frontend/src/services/http.ts` 注入 Bearer token，并启用 `withCredentials` 支持 refresh cookie。
- 后端 CORS 已开启 credentials，`ECOM_CORS_ORIGINS` 不能使用 `*` 作为正式跨域登录配置。

### 3.2 `POST /api/v1/auth/register`
用途：注册用户，并立即签发登录态。

请求体：
```json
{
  "email": "user@example.com",
  "password": "StrongPass123",
  "nickname": "测试用户"
}
```

### 3.3 `POST /api/v1/auth/login`
用途：邮箱密码登录。

常见错误：
- `401 / code=4011`：邮箱或密码错误
- `403 / code=4032`：用户状态不可用

### 3.4 `POST /api/v1/auth/refresh`
用途：基于 HttpOnly refresh cookie 轮换登录态。

常见错误：
- `401 / code=4012`：缺少 refresh token
- `401 / code=4013`：refresh token 无效、已撤销或已过期

### 3.5 `POST /api/v1/auth/logout`
用途：撤销当前 refresh token，并清理 cookie。

### 3.6 `GET /api/v1/auth/me`
用途：读取当前 access token 对应的用户信息。

常见错误：
- `401 / code=4014`：缺少 access token
- `401 / code=4010`：token 无效或已过期

## 4. v1 任务 API
### 4.1 枚举约束
`task_type`：
- `main_image`
- `detail_page`
- `image_edit`

`status`：
- `pending`
- `queued`
- `running`
- `succeeded`
- `failed`
- `partial_failed`
- `cancelled`

### 4.2 `GET /api/v1/tasks`
用途：分页查询当前用户的任务历史。

当前前端历史任务页已接入该接口。

查询参数：
- `page`：默认 `1`
- `page_size`：默认 `20`，最大 `100`
- `task_type`：可选
- `status`：可选

返回字段摘要：
- `items[]`
  - `task_id`
  - `task_type`
  - `status`
  - `title`
  - `platform`
  - `current_step`
  - `progress_percent`
  - `result_count`
  - `created_at`
  - `updated_at`
- `page`
- `page_size`
- `total`

### 4.3 `GET /api/v1/tasks/{task_id}`
用途：返回当前用户可访问的单任务详情。

返回字段摘要：
- `task_id`
- `task_type`
- `status`
- `source_task_id`
- `parent_task_id`
- `input_summary`
- `params`
- `runtime_snapshot`
- `result_summary`
- `error_code`
- `error_message`
- `created_at` / `updated_at` / `started_at` / `finished_at`

### 4.4 `GET /api/v1/tasks/{task_id}/runtime`
用途：返回当前用户任务的 runtime 聚合。

返回结构：
- `task`：数据库任务详情摘要
- `runtime`：优先来自旧 runtime 聚合服务；失败时回退 `tasks.runtime_snapshot`
- `events[]`：`task_events` 中的关键状态变化记录

### 4.5 `GET /api/v1/tasks/{task_id}/results`
用途：返回当前用户任务的结果摘要列表。

返回字段摘要：
- `task_id`
- `items[]`
  - `result_id`
  - `result_type`
  - `page_no`
  - `shot_no`
  - `version_no`
  - `status`
  - `cos_key`
  - `mime_type`
  - `size_bytes`
  - `sha256`
  - `width`
  - `height`
  - `file_url`
  - `download_url_api`
  - `created_at`
  - `updated_at`

说明：
- 当前阶段未接入 COS，`cos_key` 实际保存任务目录内的相对路径。
- `file_url` 继续复用旧文件下载接口：
  - 主图：`/api/tasks/{task_id}/files/{file_name}`
  - 详情图：`/api/detail/jobs/{task_id}/files/{file_name}`
- `download_url_api` 指向 `GET /api/v1/files/{file_id}/download-url`，用于需要用户隔离校验的签名下载。

## 5. v1 文件 API
### 5.1 `POST /api/v1/storage/presign`
用途：为当前用户任务生成图片直传 COS 的预签名 URL。

请求体：
```json
{
  "task_id": "task_uuid_or_hex",
  "kind": "inputs",
  "file_name": "white.png",
  "mime_type": "image/png",
  "size_bytes": 1024,
  "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "role": "white_bg",
  "sort_order": 0
}
```

返回字段摘要：
- `file_id`
- `task_id`
- `cos_key`
- `upload_url`
- `method`
- `headers`
- `expires_in`

约束：
- `task_id` 必须属于当前登录用户。
- 当前只允许 `image/png`、`image/jpeg`、`image/webp`，可通过配置调整。
- `headers` 必须由前端原样用于直传请求。

### 5.2 `GET /api/v1/files/{file_id}/download-url`
用途：校验当前用户是否拥有文件，再返回下载 URL。

返回字段摘要：
- `file_id`
- `source_type`：`asset` 或 `result`
- `task_id`
- `cos_key`
- `download_url`
- `expires_in`

说明：
- COS 模式下 `download_url` 是私有桶签名 URL。
- 本地兼容模式下 `download_url` 是旧文件接口 URL。
- 无权访问时返回 404，避免泄漏其他用户文件是否存在。

## 6. 当前正式生成 API
### 6.1 健康检查
- `GET /api/health`

### 6.2 主图生成
- `POST /api/image/generate-main`
  - `Content-Type: multipart/form-data`
  - 文件字段：
    - `white_bg`
    - `detail_files[]`
    - `bg_files[]`
  - 文本字段：
    - `brand_name`
    - `product_name`
    - `category`
    - `platform`
    - `style_type`
    - `style_notes`
    - `shot_count`
    - `aspect_ratio`
    - `image_size`
  - 执行方式：
    - 默认走旧进程内队列
    - `ECOM_CELERY_ENABLED=true` 时提交 `ecom.main_image.run`

### 6.3 详情图 V2
- `POST /api/detail/jobs`
- `POST /api/detail/jobs/plan`
- `GET /api/detail/jobs/{task_id}`
- `GET /api/detail/jobs/{task_id}/runtime`
- `GET /api/detail/jobs/{task_id}/files/{file_name}`

执行方式：
- 默认走旧进程内队列
- `ECOM_CELERY_ENABLED=true` 时提交 `ecom.detail_page.run`
- plan-only 任务会把 `plan_only=true` 传给 worker，只执行到规划 / prompt 阶段

### 6.4 旧任务查询接口
以下接口继续保留，当前前端仍在使用：
- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `GET /api/tasks/{task_id}/runtime`
- `GET /api/tasks/{task_id}/files/{file_name}`

### 6.5 图片编辑 V1
- `POST /api/v1/results/{result_id}/edits`
  - 为当前登录用户拥有的结果图创建 `image_edit` 任务。
  - 请求体包含 `selection_type=rectangle`、归一化矩形选区 `{x,y,width,height,unit}` 和编辑指令。
  - Celery 启用时提交 `ecom.image_edit.run`；本地开发未启用 Celery 时使用同一执行服务的后台线程 fallback。
- `GET /api/v1/results/{result_id}/edits`
  - 返回当前用户对某个结果图的编辑历史。
  - 编辑完成后返回派生 `task_results` 摘要和预览 URL。
- 当前 provider 无原生局部重绘接口时，后端显式记录 `mode=full_image_constrained_regeneration`。
- 两个接口都必须带 Bearer access token，并按当前用户隔离。

## 7. 任务兼容写入说明
- 主图和详情图创建任务时，会同时写入本地 JSON 索引和 PostgreSQL 任务镜像表。
- 运行中状态变化会同步到：
  - `tasks`
  - `task_events`
  - `task_results`
- Celery 启用后，worker 会在开始、重试、最终失败时补充写入 `tasks` 和 `task_events`。
- 旧生成接口允许可选 Bearer token：
  - 带 token 时，任务归属当前登录用户
- 不带 token 时，任务归属禁用的兼容系统用户，这类任务不会出现在普通用户历史列表中
- COS 启用时，兼容层会把输入素材和结果图上传到 COS，并把 `cos_key` 写成统一对象 key。
- COS 未启用时，`cos_key` 保持本地任务目录相对路径。

## 8. 已冻结旧接口
以下接口仍在仓库中，但不属于当前正式入口：
- `POST /api/detail/generate`
- `GET /api/templates/main-images`
- `GET /api/templates/detail-pages`
- `POST /api/templates/detail-pages/preview`
- `GET /api/assets/{file_name}`

## 9. 当前未提供的 API
以下能力还没有正式 API：
- 任务取消 / 任务重试
- 邮箱验证、找回密码、角色权限
- provider 全量 `task_usage_records` 自动落库
- COS 上传完成确认接口

## 10. 错误处理
- 参数校验失败：HTTP `422`
- 鉴权失败：HTTP `401`
- 禁止访问：HTTP `403`
- 资源不存在：HTTP `404`
- 资源冲突：HTTP `409`
- 其他业务错误：HTTP `400`
- 未处理异常：HTTP `500`

统一异常入口：
- `backend/core/exceptions.py`
- `backend/main.py`
