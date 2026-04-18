# 开发协作规则

## 1. 适用范围
本规则适用于仓库内前端、后端与文档协作，并与根目录 `AGENTS.md` 保持一致。

## 2. 代码风格与分层
### 2.1 后端
- route 层只做请求接入、参数校验、调用 service、返回统一响应
- service 层负责业务编排
- schema 先定义再使用
- repository 统一处理 JSON 或数据库读写

### 2.2 前端
- 页面层只做页面编排与状态管理
- API 请求统一进入 `frontend/src/services/`
- 类型定义集中在 `frontend/src/types/`

## 3. 注释要求
- 核心模块、核心函数要有清晰 docstring
- 复杂逻辑注释要解释原因、边界和兼容策略
- 低价值注释不保留

## 4. 文档同步要求（强制）
以下任一变更发生时，必须在同一任务同步文档：
- API 路径 / 参数 / 返回字段变化：更新 `docs/api.md`
- 页面行为 / 轮询逻辑变化：更新 `docs/frontend-workbench.md` 或 `docs/workflow.md`
- 架构或目录职责变化：更新 `docs/architecture.md`、`docs/codebase-file-map.md`、`README.md`
- 存储方案变化：更新 `docs/storage.md`、`docs/database-schema-v1.md`
- 开发规范或环境变量变化：更新 `docs/development-rules.md`、`README.md`、`AGENTS.md`

## 5. 环境变量要求
- 所有新配置必须进入统一配置模块
- `ECOM_` 前缀配置定义在 `backend/core/config.py`
- `ECOM_IMAGE_AGENT_` 前缀配置定义在 `backend/engine/core/config.py`
- 新增配置项必须同步更新：
  - `.env.example`
  - `README.md`
  - 本文档

## 6. 数据与存储约束
- 不把文件二进制存进数据库
- 不把强关系字段偷放进 JSONB
- 兼容迁移阶段允许 JSON / 文件系统 与 PostgreSQL 并行存在
- 对外口径必须明确当前真源，不允许超实现承诺

## 7. 提交前检查项
- 是否改动了 API、schema、状态字段或任务落盘结构？
- 是否改动了页面行为、轮询逻辑、预览 / 下载行为？
- 是否新增了环境变量但未记录默认值和用途？
- 是否同步更新了 `README.md`、`docs/codebase-file-map.md` 和受影响文档？
- 是否验证了最小可运行命令或最小测试？

## 8. 禁止事项
- 禁止“代码已改，文档后补”
- 禁止实验脚本混入正式 API / 页面目录
- 禁止跨层调用导致职责失衡
- 禁止长期保留未说明的 mock、旧实现和过期文档
