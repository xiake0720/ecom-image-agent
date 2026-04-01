# 架构说明（2026-03 重构后）

## 总体分层
- **frontend/**：React 工作台，负责页面交互、表单、预览、任务列表。
- **backend/**：FastAPI 服务，负责接口编排、统一响应、异常处理、任务记录、模板解析。
- **backend/engine/**：复用既有核心能力（workflow/provider/rendering/storage），由后端 service 调用。
- **backend/legacy/**：保留 Streamlit 调试入口与历史 UI。

## 关键设计
1. **后端分层**
   - `api/`：路由与参数接入
   - `schemas/`：请求响应模型
   - `services/`：主图生成、详情页生成、模板读取
   - `repositories/`：任务索引持久化
   - `core/`：配置、日志、中间件、异常、统一返回
2. **主图生成链路**
   - API 收到 multipart 请求后，交给 `MainImageService`
   - 服务层复用 `backend.engine.workflows.graph.run_workflow`
   - 产物仍落盘到 `outputs/tasks/{task_id}/`
3. **详情页生成链路**
   - API 收到结构化商品数据
   - 读取 `backend/templates/detail_pages/*.json`
   - 生成模块数组、预览数据、导出素材清单

## 扩展点
- 可在 `services/main_image_service.py` 中替换为异步任务队列。
- 可在 `repositories/` 新增 SQLite/PostgreSQL 实现。
- 可在 `templates/detail_pages/` 增加平台/风格/品类模板。
