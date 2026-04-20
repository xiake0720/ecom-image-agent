# ecom-image-agent

## 项目定位
`ecom-image-agent` 是一个电商图片生产工作台仓库，当前采用：
- 后端：FastAPI
- 前端：React + TypeScript + Vite
- 生成引擎：LangGraph + provider/router + 本地文件落盘

当前目标是：
- 本地可运行
- 主链路可观测
- 任务可追溯
- 文档与实现一致

当前状态是“一期可上线候选”。正式发布前必须完成 `docs/security-checklist.md` 和 `docs/release-checklist.md`。

## 当前正式边界
一期前端保留页面：
- `/login`
- `/register`
- `/main-images`
- `/detail-pages`
- `/tasks`

一期外页面已从前端路由层隐藏，但代码保留：
- `/dashboard`
- `/templates`
- `/preview`
- `/settings`
- `/assets-library`

范围冻结事实见 `docs/v1-scope-freeze.md`。

## 当前正式架构
- 后端入口：`backend/main.py`
- 前端入口：`frontend/src/main.tsx`
- 主图工作流：`backend/engine/workflows/graph.py`
- 详情图工作流：`backend/engine/workflows/detail_graph.py`
- 数据库迁移：`alembic/`
- 任务索引：`storage/tasks/index.json`
- 任务产物：`outputs/tasks/{task_id}/`
- 部署入口：`docker-compose.dev.yml` / `docker-compose.prod.yml`
- 监控入口：`/metrics` + Prometheus/Grafana 模板

当前后端是双存储结构：
- 用户认证与任务元数据镜像：PostgreSQL
- 主图/详情图任务执行真源：本地文件系统 + JSON
- 文件对象存储：可选启用腾讯云 COS，未启用时保留本地兼容模式
- 异步任务执行：可选启用 Celery + Redis，未启用时保留进程内队列 fallback

## 目录结构
```text
backend/
  api/                     # FastAPI 路由层
  api/v1/                  # 版本化 API（当前已接入 auth + tasks）
  core/                    # 配置、异常、middleware、安全工具
  db/                      # SQLAlchemy Async 基础设施与 models
  repositories/            # JSON 仓储与数据库仓储
  schemas/                 # Pydantic schema
  services/                # 后端业务编排层
  workers/                 # Celery app 与异步任务入口
  engine/                  # 主图/详情图 workflow、provider、渲染、存储
  templates/               # 旧模板体系资源（已冻结）
alembic/                   # 数据库迁移
docker-compose.dev.yml     # 本地 PostgreSQL / Redis 依赖
docker-compose.prod.yml    # 一期生产 compose 模板
Dockerfile.backend         # 后端镜像构建
deploy/                    # Nginx / Prometheus / Grafana 配置
docs/                      # 项目事实文档
frontend/
  Dockerfile               # 前端静态站点镜像构建
  src/auth/                # 前端登录态 Provider 与路由守卫
  src/config/              # 前端范围开关与配置
  src/hooks/               # 前端复用 hooks
  src/pages/               # 页面容器
  src/components/          # 复用 UI 组件
  src/services/            # API 调用层
  src/types/               # 前端 contract
storage/tasks/             # JSON 任务索引
outputs/tasks/             # 任务产物
```

## 本地启动
### 1. 安装依赖
```bash
python -m pip install -e .[dev]
```

### 2. 配置环境变量
```bash
cp .env.example .env
```

### 3. 初始化数据库
确保本机 PostgreSQL 已创建目标数据库，然后执行任一命令：
```bash
alembic upgrade head
```

```bash
python scripts/migrate.py
```

### 4. 启动本地依赖（可选）
如果要使用 PostgreSQL 和 Redis 容器：
```bash
docker compose -f docker-compose.dev.yml up -d postgres redis
```

### 5. 启动后端
```bash
python -m uvicorn backend.main:app --reload --port 8000
```

### 6. 启动 Celery Worker（启用 Celery 时）
Windows 本地建议：
```bash
celery -A backend.workers.celery_app:celery_app worker -l info -P solo
```

Linux / macOS：
```bash
celery -A backend.workers.celery_app:celery_app worker -l info
```

### 7. 启动前端
```bash
cd frontend
npm install
npm run dev
```

默认地址：
- 后端：`http://127.0.0.1:8000`
- 前端：`http://127.0.0.1:5173`
- Liveness：`http://127.0.0.1:8000/api/health/live`
- Readiness：`http://127.0.0.1:8000/api/health/ready`
- Metrics：`http://127.0.0.1:8000/metrics`

### 8. 创建初始账号（可选）
当前没有角色/权限模型，脚本创建的是普通 active 用户，用于首轮冒烟测试：
```bash
python scripts/create_admin.py --email admin@example.com --nickname Admin
```

## Docker 启动
### 本地基础依赖
```bash
docker compose -f docker-compose.dev.yml up -d postgres redis
```

### 生产模板
先从 `.env.example` 生成 `.env` 并替换所有 `change-me-*` 密钥，再执行：
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

带监控组件：
```bash
docker compose -f docker-compose.prod.yml --profile monitoring up -d --build
```

生产部署说明见 `docs/deployment.md`。

## 环境变量
### FastAPI / 认证 / 数据库（`ECOM_`）
定义位置：`backend/core/config.py`
- `ECOM_API_PREFIX`
- `ECOM_API_V1_PREFIX`
- `ECOM_CORS_ORIGINS`（本地默认包含 `http://localhost:5173` 和 `http://127.0.0.1:5173`，用于携带 refresh cookie）
- `ECOM_MAX_REQUEST_BODY_SIZE_BYTES`
- `ECOM_SECURITY_HEADERS_ENABLED`
- `ECOM_SECURITY_HSTS_ENABLED`
- `ECOM_SECURITY_HSTS_MAX_AGE_SECONDS`
- `ECOM_RATE_LIMIT_ENABLED`
- `ECOM_RATE_LIMIT_LOGIN_REQUESTS`
- `ECOM_RATE_LIMIT_LOGIN_WINDOW_SECONDS`
- `ECOM_RATE_LIMIT_TASK_CREATE_REQUESTS`
- `ECOM_RATE_LIMIT_TASK_CREATE_WINDOW_SECONDS`
- `ECOM_RATE_LIMIT_UPLOAD_PRESIGN_REQUESTS`
- `ECOM_RATE_LIMIT_UPLOAD_PRESIGN_WINDOW_SECONDS`
- `ECOM_METRICS_ENABLED`
- `ECOM_READINESS_CHECK_REDIS`
- `ECOM_DATABASE_URL`
- `ECOM_DATABASE_ECHO`
- `ECOM_COS_ENABLED`
- `ECOM_COS_SECRET_ID`
- `ECOM_COS_SECRET_KEY`
- `ECOM_COS_REGION`
- `ECOM_COS_BUCKET`
- `ECOM_COS_PUBLIC_HOST`
- `ECOM_COS_SIGN_EXPIRE_SECONDS`
- `ECOM_COS_MAX_IMAGE_SIZE_BYTES`
- `ECOM_COS_ALLOWED_IMAGE_MIME_TYPES`
- `ECOM_CELERY_ENABLED`
- `ECOM_REDIS_URL`
- `ECOM_CELERY_BROKER_URL`
- `ECOM_CELERY_RESULT_BACKEND`
- `ECOM_CELERY_TASK_ALWAYS_EAGER`
- `ECOM_CELERY_TASK_SERIALIZER`
- `ECOM_CELERY_ACCEPT_CONTENT`
- `ECOM_CELERY_RESULT_SERIALIZER`
- `ECOM_CELERY_TASK_TIME_LIMIT_SECONDS`
- `ECOM_CELERY_TASK_SOFT_TIME_LIMIT_SECONDS`
- `ECOM_CELERY_MAX_RETRIES`
- `ECOM_CELERY_RETRY_COUNTDOWN_SECONDS`
- `ECOM_AUTH_JWT_SECRET_KEY`
- `ECOM_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`
- `ECOM_AUTH_REFRESH_TOKEN_EXPIRE_DAYS`
- `ECOM_AUTH_REFRESH_COOKIE_NAME`
- `ECOM_AUTH_REFRESH_COOKIE_SECURE`
- `ECOM_AUTH_REFRESH_COOKIE_SAMESITE`
- `ECOM_AUTH_REFRESH_COOKIE_PATH`
- `ECOM_AUTH_TOKEN_HASH_SECRET`
- `ECOM_COMPAT_TASK_USER_EMAIL`
- `ECOM_COMPAT_TASK_USER_NICKNAME`

### 生成引擎 / provider（`ECOM_IMAGE_AGENT_`）
定义位置：`backend/engine/core/config.py`
- `ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE`
- `ECOM_IMAGE_AGENT_IMAGE_PROVIDER_MODE`
- `ECOM_IMAGE_AGENT_TASKS_DIR`
- `ECOM_IMAGE_AGENT_CACHE_DIR`
- `ECOM_IMAGE_AGENT_EXPORTS_DIR`
- `ECOM_IMAGE_AGENT_RUNAPI_API_KEY`
- `ECOM_IMAGE_AGENT_RUNAPI_TEXT_API_KEY`
- `ECOM_IMAGE_AGENT_GOOGLE_API_KEY`
- `ECOM_IMAGE_AGENT_BANANA2_MODEL`

## 当前正式 API
### v1 认证 API
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

### v1 任务 API
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/tasks/{task_id}/runtime`
- `GET /api/v1/tasks/{task_id}/results`

### v1 文件 API
- `POST /api/v1/storage/presign`
- `GET /api/v1/files/{file_id}/download-url`

### v1 图片编辑 API
- `POST /api/v1/results/{result_id}/edits`
- `GET /api/v1/results/{result_id}/edits`

### 生成与旧任务 API
- `GET /api/health`
- `GET /api/health/live`
- `GET /api/health/ready`
- `GET /metrics`
- `POST /api/image/generate-main`
- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `GET /api/tasks/{task_id}/runtime`
- `GET /api/tasks/{task_id}/files/{file_name}`
- `POST /api/detail/jobs`
- `POST /api/detail/jobs/plan`
- `GET /api/detail/jobs/{task_id}`
- `GET /api/detail/jobs/{task_id}/runtime`
- `GET /api/detail/jobs/{task_id}/files/{file_name}`

详细字段见 `docs/api.md`。

## 当前状态说明
- 后端真实注册/登录/refresh/logout/me 已完成。
- v1 历史任务接口已完成，支持分页、筛选和按用户隔离。
- 主图/详情图任务当前采用“旧链路继续跑 + 数据库镜像写入”的兼容方案。
- 腾讯云 COS 预签名上传、签名下载和兼容写入已完成；本地开发默认仍走本地文件。
- Celery + Redis 任务执行框架已完成；默认关闭，开启后主图/详情图任务提交到 Celery worker。
- 单张图片局部标记后二次生成已接入 v1：支持矩形选区、编辑指令、`image_edit` 任务、编辑历史和派生结果版本。
- 前端 `/login` 和 `/register` 已接入新认证 API，工作台路由已受登录态保护。
- 前端历史任务页已切到 `/api/v1/tasks*`，支持分页、筛选、runtime 摘要和结果摘要查看。
- 前端已提供 COS 直传 service，但主图 / 详情图页面仍使用旧 multipart 提交流程，完整直传切换待后续“先建任务 / 再直传 / 再触发生成”改造。
- 当前图片编辑默认使用 `full_image_constrained_regeneration` fallback；原生 inpainting provider 和 brush/mask 留待后续。
- 登录、任务创建、上传签名已接入基础限流；任务创建、下载签名、图片编辑已补审计。
- 已提供 Nginx 反向代理、生产 compose、Prometheus scrape 配置和 Grafana dashboard 模板。

## 验证
本轮阶段 8 收尾验证结果：
```bash
python -m pytest
# 31 passed

cd frontend
npm run build
# built successfully
```

补充校验：
- `python -m compileall backend`
- `/api/health/live`、`/api/health/ready`、`/metrics` 均可由 TestClient 访问。
- YAML/JSON 配置已做语法校验。

当前环境没有 Docker CLI，容器构建与 `docker compose config` 需在部署机验证。

## 文档索引
- `docs/v1-scope-freeze.md`
- `docs/task-migration-plan.md`
- `docs/cos-integration.md`
- `docs/celery-task-architecture.md`
- `docs/image-edit-v1.md`
- `docs/frontend-v1-pages.md`
- `docs/deployment.md`
- `docs/security-checklist.md`
- `docs/release-checklist.md`
- `docs/phase8-final-report.md`
- `docs/architecture.md`
- `docs/api.md`
- `docs/database-schema-v1.md`
- `docs/storage.md`
- `docs/frontend-workbench.md`
- `docs/codebase-file-map.md`
- `docs/development-rules.md`

## 协作规范
仓库级执行规范见 `AGENTS.md`。
