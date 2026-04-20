# 安全检查清单

上线前逐项确认，未通过项必须记录负责人和处理时间。

## 访问控制

- [ ] 主图任务创建 `/api/image/generate-main` 必须带 Bearer access token。
- [ ] 详情图任务创建 `/api/detail/jobs` 与 `/api/detail/jobs/plan` 必须带 Bearer access token。
- [ ] 图片编辑 `/api/v1/results/{result_id}/edits` 必须带 Bearer access token。
- [ ] 任务查询、结果查询、下载签名按当前用户隔离。
- [ ] 生产环境不直接暴露后端容器端口，只暴露 Nginx。

## 认证与 Cookie

- [ ] `ECOM_AUTH_JWT_SECRET_KEY` 已替换为高强度随机值。
- [ ] `ECOM_AUTH_TOKEN_HASH_SECRET` 已替换为高强度随机值。
- [ ] 生产环境 `ECOM_AUTH_REFRESH_COOKIE_SECURE=true`。
- [ ] 生产环境 refresh cookie 的 `SameSite` 与业务域名策略匹配。
- [ ] 禁止将 refresh token 写入 localStorage 或前端日志。

## 限流

- [ ] 登录接口已启用限流。
- [ ] 任务创建接口已启用限流。
- [ ] 上传预签名接口已启用限流。
- [ ] Nginx 或上游网关具备进一步防护能力，避免多副本进程内限流被绕过。
- [ ] 429 响应携带 `Retry-After`。

## 审计

- [ ] 注册、登录、登出写入 `audit_logs`。
- [ ] 创建任务写入 `audit_logs`，包含 `task_id` 与 `task_type`。
- [ ] 下载签名写入 `audit_logs`，包含 `file_id`、`task_id` 与 `source_type`。
- [ ] 发起编辑写入 `audit_logs`，包含 `edit_id` 与 `edit_task_id`。
- [ ] 审计日志包含 `request_id`、IP、user-agent。

## 文件与 COS

- [ ] 只允许图片 MIME 白名单：`image/png`、`image/jpeg`、`image/webp`。
- [ ] 上传大小限制已配置：`ECOM_COS_MAX_IMAGE_SIZE_BYTES`。
- [ ] 请求体大小限制已配置：`ECOM_MAX_REQUEST_BODY_SIZE_BYTES`。
- [ ] COS bucket 默认为私有读写。
- [ ] 后端只签发 URL，不向前端下发 COS secret。
- [ ] 下载签名接口先校验所有权再签发。

## CORS 与响应头

- [ ] `ECOM_CORS_ORIGINS` 只包含生产前端域名。
- [ ] 不使用 `*` 作为生产 CORS origin。
- [ ] `X-Content-Type-Options=nosniff` 已启用。
- [ ] `X-Frame-Options=DENY` 已启用。
- [ ] `Referrer-Policy=no-referrer` 已启用。
- [ ] HTTPS 场景启用 `Strict-Transport-Security`。

## 配置与密钥

- [ ] `.env` 不提交到 Git。
- [ ] `.env.example` 不包含真实密钥。
- [ ] 数据库密码、Grafana 密码、JWT secret、COS secret 不复用。
- [ ] 生产环境 `ECOM_DEBUG=false`。
- [ ] 生产环境日志不输出 access token、refresh token、COS secret。

## 数据与备份

- [ ] PostgreSQL 有定时备份。
- [ ] 备份恢复流程已演练。
- [ ] Alembic migration 已在预发环境执行验证。
- [ ] `audit_logs`、`tasks`、`task_results` 有必要索引。

## 监控与告警

- [ ] `/api/health/ready` 被负载均衡或编排系统使用。
- [ ] `/metrics` 被 Prometheus 抓取。
- [ ] Grafana dashboard 已导入或由 provisioning 自动加载。
- [ ] 5xx 增长、readiness 失败、限流异常增长有告警。
- [ ] worker 任务失败率有人工巡检或告警。
