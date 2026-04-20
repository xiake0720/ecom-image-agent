# 部署说明

本文档覆盖一期上线的最小部署方式，目标是能稳定启动基础依赖、后端 API、Celery worker、前端静态站点、Nginx 反向代理和基础监控。

## 运行组件

- `postgres`: 主业务数据库。
- `redis`: Celery broker/result backend。
- `backend`: FastAPI API 服务。
- `worker`: Celery 任务执行进程。
- `frontend`: React/Vite 构建后的静态站点。
- `nginx`: 对外反向代理，统一转发 `/api/`、`/metrics` 和前端页面。
- `prometheus` 与 `grafana`: 可选监控 profile。

## 本地开发依赖

只启动基础依赖：

```bash
docker compose -f docker-compose.dev.yml up -d postgres redis
```

初始化数据库：

```bash
alembic upgrade head
```

启动后端：

```bash
python -m uvicorn backend.main:app --reload
```

启动 worker：

```bash
celery -A backend.workers.celery_app:celery_app worker --loglevel=INFO
```

启动前端：

```bash
cd frontend
npm install
npm run dev
```

## 生产环境

1. 复制 `.env.example` 为 `.env`。
2. 修改所有 `change-me-*`、JWT secret、token hash secret、数据库密码、Grafana 密码。
3. 配置 `ECOM_CORS_ORIGINS` 为真实前端域名。
4. 若启用 COS，配置 `ECOM_COS_ENABLED=true` 与腾讯云 COS secret/bucket/region。
5. 确认 `ECOM_AUTH_REFRESH_COOKIE_SECURE=true`，并只通过 HTTPS 暴露服务。

启动生产服务：

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

启动含监控的生产服务：

```bash
docker compose -f docker-compose.prod.yml --profile monitoring up -d --build
```

生产 compose 会先执行：

```bash
alembic upgrade head
```

迁移成功后再启动 `backend` 和 `worker`。

## 健康检查

- `GET /api/health`: 进程基本健康。
- `GET /api/health/live`: liveness，用于判断进程是否存活。
- `GET /api/health/ready`: readiness，检查数据库；当 `ECOM_CELERY_ENABLED=true` 且 `ECOM_READINESS_CHECK_REDIS=true` 时也检查 Redis。
- `GET /metrics`: Prometheus 文本指标。

## Nginx

基础反向代理配置位于：

```text
deploy/nginx/ecom-image-agent.conf
```

默认能力：

- `/api/` 转发到后端。
- `/metrics` 仅允许内网地址访问。
- `/` 转发到前端静态站点。
- `client_max_body_size 100m`，与 `ECOM_MAX_REQUEST_BODY_SIZE_BYTES` 对齐。
- 注入 `X-Request-ID`、`X-Forwarded-For`、`X-Forwarded-Proto`。
- 添加基础安全响应头。

生产环境建议在外层负载均衡或 Nginx 上终止 HTTPS，并补充真实证书配置。

## 监控

Prometheus 配置：

```text
deploy/prometheus/prometheus.yml
```

Grafana dashboard 模板：

```text
deploy/grafana/dashboards/ecom-image-agent-overview.json
```

首期暴露的指标：

- `ecom_process_uptime_seconds`
- `ecom_http_requests_total`
- `ecom_http_request_duration_seconds_sum`
- `ecom_http_request_duration_seconds_count`
- `ecom_rate_limit_blocked_total`

## 限流配置

- `ECOM_RATE_LIMIT_LOGIN_REQUESTS` / `ECOM_RATE_LIMIT_LOGIN_WINDOW_SECONDS`
- `ECOM_RATE_LIMIT_TASK_CREATE_REQUESTS` / `ECOM_RATE_LIMIT_TASK_CREATE_WINDOW_SECONDS`
- `ECOM_RATE_LIMIT_UPLOAD_PRESIGN_REQUESTS` / `ECOM_RATE_LIMIT_UPLOAD_PRESIGN_WINDOW_SECONDS`

当前限流为进程内实现。多副本部署时每个副本独立计数，一期可上线但不是全局限流；如果后续需要跨副本一致限流，应迁移到 Redis 或网关层。

## 回滚

1. 保留上一个镜像 tag 或 compose 文件版本。
2. 回滚前确认数据库 migration 是否可逆。
3. 若 migration 不可逆，先恢复数据库备份，再回滚应用。
4. 使用 `/api/health/ready` 和 `/metrics` 验证恢复状态。
