# 发布检查清单

本文档用于一期版本上线前的 release gate。

## 代码冻结

- [ ] 确认本次发布只包含一期范围内能力。
- [ ] 非一期入口仍保持隐藏或不可达。
- [ ] 不包含临时调试代码、硬编码密钥、测试账号密码。
- [ ] `git status` 中没有意外文件。

## 测试

- [ ] 后端单元与集成测试通过：`python -m pytest`。
- [ ] 前端类型检查与构建通过：`cd frontend && npm run build`。
- [ ] Alembic migration 可执行：`alembic upgrade head`。
- [ ] 本地依赖可启动：`docker compose -f docker-compose.dev.yml up -d postgres redis`。
- [ ] 关键链路手工验收通过：注册、登录、主图任务、详情图任务、历史任务、下载签名、单图编辑。

## 环境变量

- [ ] 已从 `.env.example` 生成生产 `.env`。
- [ ] `POSTGRES_PASSWORD` 已替换。
- [ ] `GRAFANA_ADMIN_PASSWORD` 已替换。
- [ ] `ECOM_AUTH_JWT_SECRET_KEY` 已替换。
- [ ] `ECOM_AUTH_TOKEN_HASH_SECRET` 已替换。
- [ ] `ECOM_CORS_ORIGINS` 是生产域名白名单。
- [ ] `ECOM_AUTH_REFRESH_COOKIE_SECURE=true`。
- [ ] `ECOM_DEBUG=false`。
- [ ] COS 配置与 bucket 权限已核对。

## 数据库

- [ ] 生产数据库已创建。
- [ ] 数据库备份策略已启用。
- [ ] migration 已在预发环境执行。
- [ ] 发布窗口内可回滚到上一份备份。

## 部署

- [ ] 后端镜像可构建：`docker build -f Dockerfile.backend .`。
- [ ] 前端镜像可构建：`docker build frontend`。
- [ ] 生产 compose 可解析：`docker compose -f docker-compose.prod.yml config`。
- [ ] 首次部署执行：`docker compose -f docker-compose.prod.yml up -d --build`。
- [ ] 含监控部署执行：`docker compose -f docker-compose.prod.yml --profile monitoring up -d --build`。

## 上线后验证

- [ ] `GET /api/health/live` 返回 200。
- [ ] `GET /api/health/ready` 返回 200。
- [ ] `GET /metrics` 有 Prometheus 文本输出。
- [ ] Nginx `/api/` 转发正常。
- [ ] 前端刷新页面不 404。
- [ ] 登录接口错误密码返回 401。
- [ ] 频繁登录触发 429。
- [ ] 创建任务后 `audit_logs` 有 `task.create`。
- [ ] 下载签名后 `audit_logs` 有 `result.download`。
- [ ] 发起编辑后 `audit_logs` 有 `image_edit.create`。

## 回滚准备

- [ ] 保留上一版镜像或 Git tag。
- [ ] 明确 migration 是否可逆。
- [ ] 准备数据库恢复命令。
- [ ] 准备停止 worker 的命令，避免回滚期间继续消费旧任务。
- [ ] 回滚后通过 health、metrics、关键链路验证。

## 发布结论

- [ ] 发布负责人确认。
- [ ] 产品/业务验收确认。
- [ ] 运维或值班负责人确认。
- [ ] 发布窗口和回滚窗口已通知相关人员。
