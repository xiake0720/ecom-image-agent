
# Ecom Image Agent 单机 Docker 部署文档（基于本次会话整理）

## 1. 文档说明
- 适用对象：首次部署该项目的开发者 / 运维人员
- 部署模式：单台云服务器 + Docker Compose + 腾讯云 COS（可先关闭）
- 当前会话确认环境：Ubuntu 22.04 LTS、Docker 26.1.3、Docker Compose v2.27.1、4 核 / 3.3GiB RAM / 40G 磁盘、4G swap
- 文档范围：整理本次会话中已经验证过的部署步骤、环境配置、启动顺序、排查点与上线建议

## 2. 项目部署结构
生产编排 `docker-compose.prod.yml` 已包含：
- postgres（数据库）
- redis（缓存 / Celery broker）
- migrate（数据库迁移）
- backend（FastAPI）
- worker（Celery）
- frontend（静态前端）
- nginx（统一入口）
- prometheus / grafana（可选监控）

> 结论：不需要在宿主机单独 `apt install postgresql` 或 `apt install redis`。

## 3. 当前服务器环境
- 操作系统：Ubuntu 22.04 LTS
- 内核：5.15.0-176-generic
- Docker：26.1.3
- Docker Compose：v2.27.1
- CPU：4 核
- 内存：3.3GiB
- Swap：4GiB
- 磁盘：40G

## 4. 宿主机初始化步骤

### 4.1 创建 swap
```bash
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
swapon --show
free -h
```

### 4.2 更新系统并安装工具
```bash
apt update
apt upgrade -y
apt install -y git curl wget vim unzip htop ca-certificates
timedatectl set-timezone Asia/Shanghai
date
timedatectl
```

### 4.3 重启系统
```bash
reboot
```

### 4.4 重启后验证
```bash
uname -a
free -h
swapon --show
```

## 5. 目录规划
```bash
mkdir -p /srv/ecom-image-agent/{app,postgres_data,redis_data,logs,backups,nginx/conf.d,nginx/certs}
find /srv/ecom-image-agent -maxdepth 2 -type d | sort
```

目录结构：
```text
/srv/ecom-image-agent
/srv/ecom-image-agent/app
/srv/ecom-image-agent/backups
/srv/ecom-image-agent/logs
/srv/ecom-image-agent/nginx
/srv/ecom-image-agent/nginx/certs
/srv/ecom-image-agent/nginx/conf.d
/srv/ecom-image-agent/postgres_data
/srv/ecom-image-agent/redis_data
```

> 当前 compose 实际使用的是 Docker named volumes，而不是把数据库直接绑定到这些目录。

## 6. 拉取代码
```bash
cd /srv/ecom-image-agent/app
git clone https://github.com/xiake0720/ecom-image-agent.git .
```

关键文件：
```text
docker-compose.dev.yml
docker-compose.prod.yml
.env.example
Dockerfile.backend
frontend/Dockerfile
deploy/nginx/ecom-image-agent.conf
pyproject.toml
```

## 7. 环境变量配置

### 7.1 初始化 .env
```bash
cd /srv/ecom-image-agent/app
cp .env.example .env
vim .env
```

### 7.2 必改项
```env
POSTGRES_PASSWORD=<your_strong_password>
GRAFANA_ADMIN_PASSWORD=<your_grafana_password>

ECOM_AUTH_JWT_SECRET_KEY=<your_jwt_secret>
ECOM_AUTH_TOKEN_HASH_SECRET=<your_refresh_hash_secret>

ECOM_COS_ENABLED=false
ECOM_AUTH_REFRESH_COOKIE_SECURE=false
ECOM_SECURITY_HSTS_ENABLED=false
```

### 7.3 最低可运行配置示例
```env
POSTGRES_DB=ecom_image_agent
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<your_strong_password>

HTTP_PORT=80
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<your_grafana_password>

ECOM_DEBUG=false
ECOM_API_PREFIX=/api
ECOM_API_V1_PREFIX=/api/v1

ECOM_AUTH_JWT_SECRET_KEY=<your_jwt_secret>
ECOM_AUTH_TOKEN_HASH_SECRET=<your_refresh_hash_secret>
ECOM_AUTH_REFRESH_COOKIE_SECURE=false
ECOM_SECURITY_HSTS_ENABLED=false

ECOM_COS_ENABLED=false
```

### 7.4 当前会话对 compose 的额外修改
未启用 HTTPS 前，把 `docker-compose.prod.yml` 中 backend 服务里的：
- `ECOM_AUTH_REFRESH_COOKIE_SECURE: "true"` 改为 `"false"`
- `ECOM_SECURITY_HSTS_ENABLED: "true"` 改为 `"false"`

## 8. Redis 内核参数修复
```bash
sysctl vm.overcommit_memory
echo 'vm.overcommit_memory=1' > /etc/sysctl.d/99-redis.conf
sysctl --system
sysctl vm.overcommit_memory
```

## 9. 实际部署顺序

### 9.1 启动 PostgreSQL 和 Redis
```bash
cd /srv/ecom-image-agent/app
docker compose -f docker-compose.prod.yml up -d postgres redis
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=50 postgres
docker compose -f docker-compose.prod.yml logs --tail=50 redis
```

### 9.2 执行数据库迁移
```bash
docker compose -f docker-compose.prod.yml run --rm migrate
```

> 第一次执行会先构建 backend 镜像，耗时较长属正常现象。

### 9.3 启动 backend
```bash
docker compose -f docker-compose.prod.yml up -d backend
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=100 backend
```

### 9.4 启动 worker
```bash
docker compose -f docker-compose.prod.yml up -d worker
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=100 worker
```

### 9.5 启动 frontend
```bash
docker compose -f docker-compose.prod.yml up -d frontend
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=100 frontend
```

### 9.6 启动 nginx
```bash
docker compose -f docker-compose.prod.yml up -d nginx
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=100 nginx
```

## 10. 健康检查
```bash
curl -I http://127.0.0.1
curl http://127.0.0.1/api/health/live
docker compose -f docker-compose.prod.yml ps
```

预期：
- 首页返回 `HTTP/1.1 200 OK`
- `/api/health/live` 返回 JSON
- `backend / postgres / redis` healthy
- `worker / frontend / nginx` Up

## 11. 端口与安全组建议
- 22：开放（SSH）
- 80：开放（HTTP）
- 443：后续启用 HTTPS 时开放
- 5432：不要开放
- 6379：不要开放
- 8000：不要开放
- 9090 / 3000：建议仅内网或受限开放

## 12. 当前已知联调问题
- 前端页面已打开
- 注册接口返回 `5001`
- `users` 表中该邮箱查询为 0 行，说明事务已回滚
- 问题更偏向业务联调，不属于基础部署失败
- 当前决定：该问题后续在本地调试

## 13. 常用运维命令
```bash
docker compose -f docker-compose.prod.yml ps

docker compose -f docker-compose.prod.yml logs --tail=100 backend
docker compose -f docker-compose.prod.yml logs --tail=100 worker
docker compose -f docker-compose.prod.yml logs --tail=100 frontend
docker compose -f docker-compose.prod.yml logs --tail=100 nginx
docker compose -f docker-compose.prod.yml logs --tail=100 postgres
docker compose -f docker-compose.prod.yml logs --tail=100 redis

docker compose -f docker-compose.prod.yml logs -f --tail=200 backend

docker compose -f docker-compose.prod.yml stop
docker compose -f docker-compose.prod.yml restart backend
docker compose -f docker-compose.prod.yml restart worker

docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml down -v   # 危险，会清空数据库卷
```

## 14. 上线前建议
- 启用 HTTPS 后重新打开 `ECOM_AUTH_REFRESH_COOKIE_SECURE=true`
- 启用 HTTPS 后重新打开 `ECOM_SECURITY_HSTS_ENABLED=true`
- 后续接入腾讯云 COS，再打开 `ECOM_COS_ENABLED=true`
- worker 改为非 root 用户运行
- 按需启用 Prometheus / Grafana
- 定期备份数据库卷、.env、compose 配置
- 正式上线建议升级到至少 4C8G / 80G，最好 8C16G / 100G+

## 15. 本次会话阶段性结论
本次会话中，部署层面已经完成并验证：
- 服务器基础环境 OK
- Docker / Compose OK
- 数据库 / Redis OK
- migrate OK
- backend OK
- worker OK
- frontend OK
- nginx OK
- 本机与公网入口链路 OK

当前后续重点是业务联调，不再是基础部署问题。
