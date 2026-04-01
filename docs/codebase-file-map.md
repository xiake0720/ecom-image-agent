# 代码地图（重构后）

## 主要入口
- `backend/main.py`：FastAPI 主入口（正式服务入口）。
- `frontend/src/main.tsx`：React 主入口。
- `backend/legacy/streamlit_app.py`：历史调试入口（已降级）。

## 后端关键文件
- `backend/engine/`：既有 LangGraph 工作流、provider、渲染与存储引擎层。
- `backend/legacy/ui/`：历史 Streamlit UI 页面与组件。
- `backend/api/*.py`：接口路由
- `backend/services/main_image_service.py`：主图生成服务（复用既有 workflow）
- `backend/services/detail_page_service.py`：详情页结构化生成
- `backend/repositories/task_repository.py`：任务索引 JSON 持久化
- `backend/templates/detail_pages/*.json`：平台/风格模板

## 前端关键文件
- `frontend/src/pages/MainImagePage.tsx`：主图提交页面
- `frontend/src/pages/DetailPageGeneratorPage.tsx`：详情页生成页面
- `frontend/src/pages/TasksPage.tsx`：任务记录页
- `frontend/src/services/http.ts`：统一请求封装
- `frontend/src/hooks/useTasks.ts`：任务查询 hook
