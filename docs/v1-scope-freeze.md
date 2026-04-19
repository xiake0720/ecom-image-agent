# V1 Scope Freeze

## 1. 冻结结论
- 冻结日期：2026-04-18。
- 一期只保留 5 类能力：注册/登录、主图生成、详情图生成、历史任务记录与查看、单张图片局部标记后二次生成。
- 非一期页面继续从前端路由和导航中隐藏，不删除代码。
- 主图/详情图核心生成逻辑继续保持现状，本轮不改 workflow、不改任务产物落盘结构。

## 2. 一期保留页面
- `/login`
  - 前端已接入后端真实认证 API。
- `/register`
  - 前端已接入后端真实注册 API。
- `/main-images`
  - 正式主图工作台。
- `/detail-pages`
  - 正式详情图工作台。
- `/tasks`
  - 正式历史任务记录页。
  - 当前接入 `/api/v1/tasks*`，支持回看 `main_image` 和 `detail_page`。

## 3. 一期隐藏页面
以下页面保留代码，但一期不再开放入口：
- `/dashboard`
- `/templates`
- `/preview`
- `/settings`
- `/assets-library`

## 4. 一期保留 API
### 4.1 已交付认证 API
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

### 4.2 生成与任务 API
- `GET /api/health`
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

## 5. 一期保留的基础设施
- PostgreSQL + SQLAlchemy Async + Alembic 已接入。
- 已落地表：
  - `users`
  - `refresh_tokens`
  - `audit_logs`
  - `idempotency_keys`
  - `tasks`
  - `task_assets`
  - `task_results`
  - `task_events`
  - `task_usage_records`
- 当前正式接入业务的数据库表：
  - `users`
  - `refresh_tokens`
  - `audit_logs`
  - `idempotency_keys`
- 任务相关数据库表当前已接入兼容双写：
  - `tasks`
  - `task_assets`
  - `task_results`
  - `task_events`
- 阶段 2 任务表仍未替换现有 JSON / 文件任务真链路。

## 6. 废弃或冻结的旧实现
以下内容不删除，但一期视为 `deprecated` 或 `frozen`：
- `backend/api/detail.py`
- `backend/services/detail_page_service.py`
- `backend/api/templates.py`
- `backend/services/template_service.py`
- `backend/templates/detail_pages/tea_tmall_premium_v1.json`
- `backend/templates/detail_pages/tmall_premium.json`
- `backend/templates/detail_pages/pinduoduo_value.json`
- `backend/legacy/**`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/TemplatesPage.tsx`
- `frontend/src/pages/PreviewPage.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/pages/AssetsLibraryPage.tsx`
- `frontend/src/mocks/*.ts`

## 7. 当前缺口与风险点
- 前端登录页、注册页、路由守卫和历史任务页已接入新的认证 / 任务 API。
  - 仍需在真实浏览器和真实 PostgreSQL 环境下做完整联调。
- “单张图片局部标记后二次生成”仍没有正式页面、正式 API 和任务协议。
- 主图/详情图任务主链路仍使用本地文件系统和 `storage/tasks/index.json`。
  - 数据库里的阶段 2 任务表当前是镜像层，不是真实任务源。
- 旧接口和旧页面代码仍在仓库内。
  - 如果后续继续修改这些模块而不同步文档，范围容易再次漂移。
- 当前执行环境未验证真实 PostgreSQL 实例上的 `alembic upgrade head`。
  - 已验证 Alembic 离线 SQL 生成和 SQLite 兼容测试。

## 8. 后续改造顺序
1. 先把“局部标记后二次生成”定义为正式任务类型、正式 API 和正式回看链路。
2. 然后把数据库里的 `tasks`、`task_events`、`task_results` 与现有 JSON 任务链路逐步对齐。
3. 再把主图 / 详情图上传流程切换为“先建任务 / 再直传 COS / 再触发生成”。
4. 等新链路稳定后，再物理清理旧 `detail.py`、旧模板体系和 mock 页面。
