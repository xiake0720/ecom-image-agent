# 腾讯云 COS 接入说明

## 1. 当前目标
阶段 3 的目标是为一期上线补齐私有桶文件能力：
- 后端生成预签名上传 URL，前端不接触 Secret。
- 浏览器可用预签名 URL 直传图片。
- 下载前必须经过后端用户归属校验，再返回签名 URL。
- `task_assets` 和 `task_results` 继续保存文件元数据。
- 保留本地文件兼容模式，避免破坏现有主图 / 详情图生成链路。

## 2. 配置项
定义位置：`backend/core/config.py`

环境变量：
- `ECOM_COS_ENABLED`
- `ECOM_COS_SECRET_ID`
- `ECOM_COS_SECRET_KEY`
- `ECOM_COS_REGION`
- `ECOM_COS_BUCKET`
- `ECOM_COS_PUBLIC_HOST`
- `ECOM_COS_SIGN_EXPIRE_SECONDS`
- `ECOM_COS_MAX_IMAGE_SIZE_BYTES`
- `ECOM_COS_ALLOWED_IMAGE_MIME_TYPES`

默认行为：
- `ECOM_COS_ENABLED=false` 时，旧本地上传、生成、预览、下载链路保持不变。
- 只有 `ECOM_COS_ENABLED=true` 且 Secret、Region、Bucket 配置完整时，才会启用真实 COS 签名和上传。

## 3. Key 规范
统一 COS 对象 key：

```text
users/{user_id}/tasks/{task_id}/{kind}/{filename}
```

说明：
- `user_id` 和 `task_id` 使用 UUID hex。
- `kind` 当前常用值：
  - `inputs`
  - `results`
- `filename` 会做路径穿越清理。
- 旧本地模式下，`cos_key` 仍保存任务目录相对路径。

## 4. 后端 API
### 4.1 `POST /api/v1/storage/presign`
用途：为当前用户的某个任务生成图片直传 URL。

要求：
- 必须携带 `Authorization: Bearer <access_token>`。
- `task_id` 必须属于当前登录用户。
- 当前只支持图片 MIME。

请求示例：
```json
{
  "task_id": "f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0",
  "kind": "inputs",
  "file_name": "white.png",
  "mime_type": "image/png",
  "size_bytes": 1024,
  "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "role": "white_bg",
  "sort_order": 0
}
```

响应摘要：
- `file_id`：预写入的 `task_assets.id`
- `cos_key`
- `upload_url`
- `method`
- `headers`
- `expires_in`

前端直传时必须使用响应中的 `headers`，否则签名可能不匹配。

### 4.2 `GET /api/v1/files/{file_id}/download-url`
用途：校验文件所有权后返回下载 URL。

查找顺序：
1. `task_assets`
2. `task_results`

行为：
- 当前用户无权访问时返回 404。
- COS 模式下返回私有桶签名 URL。
- 本地兼容模式下返回旧文件接口 URL。

## 5. 兼容写入
主图和详情图仍通过旧 workflow 生成本地文件。

当 COS 启用时：
- 创建任务时，上传素材会同步上传到 COS，`task_assets.cos_key` 保存 COS key。
- 任务运行完成后，结果图会同步上传到 COS，`task_results.cos_key` 保存 COS key。
- `task_results.render_meta.local_relative_path` 会保留本地相对路径，方便本地兼容预览。

当 COS 未启用时：
- `task_assets.cos_key` 和 `task_results.cos_key` 继续保存本地任务目录相对路径。
- 旧 `/api/tasks/{task_id}/files/{file_name}` 与 `/api/detail/jobs/{task_id}/files/{file_name}` 继续可用。

## 6. 前端接入
新增 service：
- `frontend/src/services/storageApi.ts`

能力：
- `createStoragePresign(...)`
- `uploadFileToPresignedUrl(...)`
- `fetchFileDownloadUrl(...)`
- `calculateFileSha256(...)`

当前页面仍保留原 multipart 提交流程。完整页面级切换需要阶段 5 登录态、受保护路由和任务恢复一起完成，否则新建任务前无法稳定获得后端 `task_id`。

## 7. 安全约束
- Secret 只存在后端配置，不下发前端。
- 下载必须先查数据库并校验 `user_id`。
- 上传前校验：
  - MIME 白名单
  - 文件大小限制
  - SHA256 格式
  - 文件名路径穿越
- COS 私有桶通过签名 URL 临时授权访问。

## 8. 当前限制
- 只实现图片上传。
- 未引入 COS STS 临时密钥，当前使用后端持久密钥生成短期预签名 URL。
- 前端页面尚未完全切到 COS 直传流程。
- 未实现上传完成确认接口，`task_assets` 在 presign 阶段即预写入。
- COS 上传失败时，启用 COS 的兼容写入会抛出错误，需要上线环境保证 COS 配置正确。
