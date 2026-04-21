# 远程连接服务器 PostgreSQL / Redis 调试文档

## 1. 文档目的

本文档用于说明：**如何在不开放数据库和 Redis 公网端口的前提下，从本地电脑安全连接当前测试服务器上的 PostgreSQL 和 Redis**，用于本地调试。

当前约定：

- 服务器公网 IP：`1.12.37.94`
- 服务器系统：Ubuntu 22.04
- 连接方式：**SSH 隧道**
- PostgreSQL 容器：`app-postgres-1`
- Redis 容器：`app-redis-1`

---

## 2. 为什么采用 SSH 隧道

不建议直接把以下端口暴露到公网：

- PostgreSQL：`5432`
- Redis：`6379`

原因：

1. 安全风险高，容易被扫描和暴力尝试
2. Redis 暴露公网风险尤其大
3. 调试结束后容易忘记关闭
4. 不利于后续正式上线的安全边界管理

**SSH 隧道**的优点：

- 外网仍然只开放 `22` 端口
- PostgreSQL / Redis 只绑定在服务器本机回环地址
- 数据通过 SSH 加密通道传输
- 本地工具可以像连接本地服务一样连接远端数据库

---

## 3. 目标架构

### 3.1 服务器侧

服务器继续运行当前测试环境：

- PostgreSQL
- Redis
- backend
- worker
- frontend
- nginx

另外，为了允许 SSH 隧道访问，给 PostgreSQL 和 Redis 增加**仅服务器本机可访问**的端口映射：

- PostgreSQL：`127.0.0.1:15432 -> 容器 5432`
- Redis：`127.0.0.1:16379 -> 容器 6379`

### 3.2 本地侧

本地通过 SSH 隧道访问：

- `127.0.0.1:15432` → 远端 PostgreSQL
- `127.0.0.1:16379` → 远端 Redis

### 3.3 数据隔离建议

为了避免污染当前正在运行的测试环境数据，建议新建一套**本地调试专用数据库**：

- 数据库名：`ecom_image_agent_localdev`
- 数据库用户：`localdev`

Redis 则建议使用新的 DB index：

- `8`：普通 Redis 调试
- `9`：Celery broker
- `10`：Celery result backend

---

## 4. 服务器侧配置步骤

## 4.1 新建 Compose 覆盖文件

在服务器中执行：

```bash
cd /srv/ecom-image-agent/app
cat > docker-compose.tunnel.yml <<'EOF'
services:
  postgres:
    ports:
      - "127.0.0.1:15432:5432"

  redis:
    ports:
      - "127.0.0.1:16379:6379"
EOF
```

### 说明

这一步不会改原来的 `docker-compose.prod.yml`，只是增加一个覆盖文件。

绑定 `127.0.0.1` 的意义是：

- 服务器自己能访问
- SSH 隧道能访问
- 公网无法直接访问

---

## 4.2 重启 PostgreSQL 和 Redis 使映射生效

```bash
cd /srv/ecom-image-agent/app
docker compose -f docker-compose.prod.yml -f docker-compose.tunnel.yml up -d postgres redis
```

检查状态：

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.tunnel.yml ps
```

---

## 4.3 确认端口已绑定到服务器本机

```bash
ss -lntp | grep -E '15432|16379'
```

理想状态应看到：

- `127.0.0.1:15432`
- `127.0.0.1:16379`

---

## 4.4 创建本地调试专用数据库用户和数据库

进入 PostgreSQL：

```bash
docker exec -it app-postgres-1 psql -U postgres -d postgres
```

执行 SQL：

```sql
CREATE ROLE localdev LOGIN PASSWORD '请替换成你自己的强密码';
CREATE DATABASE ecom_image_agent_localdev OWNER localdev;
GRANT ALL PRIVILEGES ON DATABASE ecom_image_agent_localdev TO localdev;
\q
```

### 说明

这样做的好处：

- 本地调试数据不会直接混进当前测试环境主库
- 即使本地跑迁移，也只影响 `ecom_image_agent_localdev`
- 后续清理测试数据更简单

---

## 4.5 给新数据库执行迁移

```bash
cd /srv/ecom-image-agent/app
docker compose -f docker-compose.prod.yml run --rm \
  -e ECOM_DATABASE_URL=postgresql+asyncpg://localdev:你的强密码@postgres:5432/ecom_image_agent_localdev \
  migrate
```

### 说明

这一步会使用项目现有的 `migrate` 服务，对新数据库执行：

- `alembic upgrade head`

执行完成后，`ecom_image_agent_localdev` 的表结构会与当前项目一致。

---

## 5. 本地建立 SSH 隧道

### 5.1 Windows CMD 正确命令

在 **Windows CMD** 中执行一行命令：

```bat
ssh -N -L 15432:127.0.0.1:15432 -L 16379:127.0.0.1:16379 ubuntu@1.12.37.94
```

> 注意：Ubuntu 镜像的 SSH 用户通常优先尝试 `ubuntu`，而不是 `root`。

### 说明

- `ssh`：通过 SSH 连接服务器
- `-N`：只建立隧道，不执行远程命令
- `-L 15432:127.0.0.1:15432`：把本地 `15432` 转发到服务器本机 `15432`
- `-L 16379:127.0.0.1:16379`：把本地 `16379` 转发到服务器本机 `16379`

### 密码说明

如果提示：

```text
ubuntu@1.12.37.94's password:
```

这里输入的是：

**服务器操作系统 SSH 登录密码**

不是：

- PostgreSQL 密码
- `localdev` 数据库密码
- Redis 密码
- `.env` 里的应用密钥

### 成功后的现象

输入密码后，如果：

- 没有报错
- 没有返回命令提示符
- 窗口停在那里

这是**正常现象**，表示 SSH 隧道已经建立成功。

> 这个窗口必须保持打开。关闭后，隧道会断开。

---

## 5.2 Windows CMD 多行写法（可选）

如果想分行写，在 CMD 中要用 `^`：

```bat
ssh -N ^
  -L 15432:127.0.0.1:15432 ^
  -L 16379:127.0.0.1:16379 ^
  ubuntu@1.12.37.94
```

---

## 5.3 PowerShell 多行写法（可选）

如果使用 PowerShell，则用反引号：

```powershell
ssh -N `
  -L 15432:127.0.0.1:15432 `
  -L 16379:127.0.0.1:16379 `
  ubuntu@1.12.37.94
```

---

## 5.4 验证本地端口是否建立

在新的 CMD 窗口中执行：

```bat
netstat -ano | findstr 15432
netstat -ano | findstr 16379
```

如果能看到相关监听或连接记录，说明隧道已经建立。

---

## 6. 本地数据库连接方式

## 6.1 PostgreSQL 连接参数

无论你使用 DBeaver、Navicat 还是代码连接，参数如下：

- Host：`127.0.0.1`
- Port：`15432`
- Database：`ecom_image_agent_localdev`
- Username：`localdev`
- Password：你创建用户时设置的密码

---

## 6.2 推荐图形工具

优先推荐：

- DBeaver
- Navicat Premium

这样可以避免本地先安装 `psql` 客户端。

### DBeaver / Navicat 配置示例

- 主机：`127.0.0.1`
- 端口：`15432`
- 数据库：`ecom_image_agent_localdev`
- 用户名：`localdev`
- 密码：你的密码

---

## 6.3 若使用连接 URL

如果代码里使用 URL，示例：

```text
postgresql+asyncpg://localdev:你的密码@127.0.0.1:15432/ecom_image_agent_localdev
```

### 注意

如果密码里包含这些字符：

- `@`
- `:`
- `/`
- `#`
- `%`

则必须做 URL 编码。

---

## 7. 本地 Redis 连接方式

## 7.1 Redis 基本连接参数

- Host：`127.0.0.1`
- Port：`16379`

### 推荐工具

- Redis Insight
- Another Redis Desktop Manager

---

## 7.2 Redis DB index 约定

为了避免和当前服务器运行中的测试环境冲突，建议本地调试使用：

- DB 8：普通 Redis 调试
- DB 9：Celery broker
- DB 10：Celery result backend

---

## 8. 本地 `.env.local` 推荐配置

## 8.1 只调接口 / 前端逻辑（推荐）

如果你本地主要调：

- 登录注册
- 历史任务
- 接口逻辑
- 前端交互

建议先关闭本地 Celery：

```env
ECOM_DATABASE_URL=postgresql+asyncpg://localdev:你的强密码@127.0.0.1:15432/ecom_image_agent_localdev
ECOM_REDIS_URL=redis://127.0.0.1:16379/8
ECOM_CELERY_BROKER_URL=redis://127.0.0.1:16379/9
ECOM_CELERY_RESULT_BACKEND=redis://127.0.0.1:16379/10
ECOM_CELERY_ENABLED=false
ECOM_DEBUG=true
```

### 优点

- 不会误发异步任务到远端运行队列
- 更适合先调前端和后端接口
- 风险更小

---

## 8.2 本地也要调 worker 时

如果你要本地完整调试 Celery 链路，可改为：

```env
ECOM_DATABASE_URL=postgresql+asyncpg://localdev:你的强密码@127.0.0.1:15432/ecom_image_agent_localdev
ECOM_REDIS_URL=redis://127.0.0.1:16379/8
ECOM_CELERY_BROKER_URL=redis://127.0.0.1:16379/9
ECOM_CELERY_RESULT_BACKEND=redis://127.0.0.1:16379/10
ECOM_CELERY_ENABLED=true
ECOM_DEBUG=true
```

### 注意

如果本地要跑 worker：

- 本地 worker 必须使用 `9/10`
- 不要与服务器当前运行中的 worker 共用 `0/1`

否则会出现：

- 抢同一队列
- 混用结果后端
- 状态污染

---

## 9. 安全边界要求

必须遵守以下规则：

### 9.1 不要开放公网数据库端口

腾讯云安全组继续只开放：

- `22`
- `80`
- 后续需要时 `443`

不要开放：

- `5432`
- `6379`

---

## 9.2 SSH 隧道不用时关闭

SSH 隧道窗口关闭后：

- 本地 `15432`
- 本地 `16379`

会立即失效。

---

## 9.3 不要本地和服务器共用同一套 Redis DB index

服务器当前测试环境已使用：

- `0`
- `1`

本地请使用：

- `8`
- `9`
- `10`

---

## 9.4 本地不要把 destructive migration 跑到测试主库

本地调试请只连接：

- `ecom_image_agent_localdev`

不要对当前服务器正在运行的测试主库直接跑变更。

---

## 9.5 大改动前先备份

尤其是在以下场景之前：

- 改 Alembic 迁移
- 改认证表结构
- 改任务表结构
- 改 Redis key 设计

至少备份：

- PostgreSQL 数据
- `.env`
- compose 文件

---

## 10. 常见问题排查

## 10.1 SSH 隧道命令输入后“像卡住一样”

这是正常现象。

如果使用的是：

```bat
ssh -N -L ...
```

输入密码后窗口停住，通常表示：

**隧道已经建立成功**

不要关闭这个窗口。

---

## 10.2 Windows CMD 输入密码时不显示字符

这是正常现象。  
输入密码时：

- 不会显示字符
- 不会显示 `*`

直接输完按回车即可。

---

## 10.3 `psql is not recognized ...`

表示本地没有安装 PostgreSQL 客户端工具。

解决方式：

- 直接使用 DBeaver / Navicat
- 或者后续安装 PostgreSQL 客户端

---

## 10.4 SSH 提示 `Could not resolve hostname \`

原因通常是：

- 在 Windows CMD 里用了 Linux 风格的反斜杠续行

解决：

- CMD 里直接一行写完
- 或者使用 `^` 做换行续写

---

## 10.5 连接数据库失败

优先排查顺序：

1. SSH 隧道窗口是否还开着
2. `docker-compose.tunnel.yml` 是否已生效
3. 服务器本机是否监听 `127.0.0.1:15432`
4. `localdev` 用户和 `ecom_image_agent_localdev` 数据库是否已创建
5. 新数据库是否已成功迁移
6. 密码是否正确
7. 数据库连接 URL 中密码是否需要 URL 编码

---

## 10.6 Redis 连接失败

优先排查：

1. SSH 隧道是否还开着
2. Redis 是否监听 `127.0.0.1:16379`
3. 本地工具是否连接到正确端口
4. DB index 是否填错

---

## 11. 推荐的实际使用方式

## 11.1 最稳妥方式

- 服务器：继续跑当前整套测试环境
- 本地：通过 SSH 隧道连接远端 PostgreSQL / Redis
- PostgreSQL：使用 `ecom_image_agent_localdev`
- Redis：使用 `8/9/10`
- 本地优先关闭 Celery，仅调接口和前端

## 11.2 真要调异步链路时

- 本地单独启动 worker
- 使用 Redis `9/10`
- 不要和服务器 worker 混用 `0/1`

---

## 12. 最终命令清单

### 服务器侧

```bash
cd /srv/ecom-image-agent/app
cat > docker-compose.tunnel.yml <<'EOF'
services:
  postgres:
    ports:
      - "127.0.0.1:15432:5432"

  redis:
    ports:
      - "127.0.0.1:16379:6379"
EOF
```

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.tunnel.yml up -d postgres redis
```

```bash
ss -lntp | grep -E '15432|16379'
```

```bash
docker exec -it app-postgres-1 psql -U postgres -d postgres
```

```sql
CREATE ROLE localdev LOGIN PASSWORD '你的强密码';
CREATE DATABASE ecom_image_agent_localdev OWNER localdev;
GRANT ALL PRIVILEGES ON DATABASE ecom_image_agent_localdev TO localdev;
\q
```

```bash
docker compose -f docker-compose.prod.yml run --rm \
  -e ECOM_DATABASE_URL=postgresql+asyncpg://localdev:你的强密码@postgres:5432/ecom_image_agent_localdev \
  migrate
```

### 本地 Windows CMD

```bat
ssh -N -L 15432:127.0.0.1:15432 -L 16379:127.0.0.1:16379 ubuntu@1.12.37.94
```

### 本地 `.env.local`

```env
ECOM_DATABASE_URL=postgresql+asyncpg://localdev:你的强密码@127.0.0.1:15432/ecom_image_agent_localdev
ECOM_REDIS_URL=redis://127.0.0.1:16379/8
ECOM_CELERY_BROKER_URL=redis://127.0.0.1:16379/9
ECOM_CELERY_RESULT_BACKEND=redis://127.0.0.1:16379/10
ECOM_CELERY_ENABLED=false
ECOM_DEBUG=true
```

---

## 13. 总结

这套方案的核心价值是：

- 不需要再单独搭一台开发服务器
- 不需要暴露数据库和 Redis 到公网
- 本地连接方式简单
- 可以和当前测试环境做数据隔离
- 后续正式上线前也容易做统一清理和切换
