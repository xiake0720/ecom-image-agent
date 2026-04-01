# 开发协作规则

## 1. 适用范围
本规则适用于仓库内前端、后端与文档协作，和根目录 `AGENTS.md` 一致。

## 2. 代码风格与分层

### 2.1 后端
- route 层仅做请求接入与响应返回。
- service 层负责业务编排。
- schema 先定义再使用。
- repository 统一处理索引读写。

### 2.2 前端
- 页面层只做页面编排与状态管理。
- API 请求统一进入 `frontend/src/services/`。
- 类型定义集中在 `frontend/src/types/`。

## 3. 注释要求
- 核心模块、核心函数必须有中文 docstring 或注释。
- 复杂逻辑注释要解释原因、边界和上下游，不写空话。

## 4. 文档同步要求（强制）
以下任一变更发生时，必须在同一任务更新文档：
- API 路径/参数/返回字段变化 -> 更新 `docs/api.md`
- 页面交互/流程变化 -> 更新 `docs/frontend-workbench.md` 与 `docs/workflow.md`
- 架构或目录职责变化 -> 更新 `docs/architecture.md`、`docs/codebase-file-map.md`、README
- 存储路径或策略变化 -> 更新 `docs/storage.md`
- 开发规范变化 -> 更新 `AGENTS.md` 与本文件

## 5. 提交前检查项
- 是否存在硬编码测试数据长期残留？
- 是否新增环境变量但未记录默认值和用途？
- 是否改了协议但未同步前端类型与文档？
- 是否更新了 `docs/codebase-file-map.md`？
- 是否验证了最小可运行命令？

## 6. 禁止事项
- 禁止“代码已改，文档后补”。
- 禁止把实验脚本混入正式 API/页面目录。
- 禁止跨层调用（如页面直接拼 multipart 细节、route 直接写文件系统复杂逻辑）。
