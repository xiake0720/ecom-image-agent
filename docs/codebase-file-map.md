# 代码地图（重构后）

## 主要入口
- `backend/main.py`：FastAPI 主入口（正式服务入口）。
- `frontend/src/main.tsx`：React 主入口（`/` 默认重定向到 `/main-images`）。
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
- `frontend/src/pages/MainImagePage.tsx`：主图工作台页面（顶部导航 + 左操作 + 右进度结果），并内置统一上传区组件（商品图/参考图复用）。
- `frontend/src/pages/MainImagePage.css`：主图工作台视觉规范样式实现（大屏自适应容器、左右分栏比例、统一上传区、顶部 action group）。
- `frontend/src/components/Layout.tsx`：路由壳层，`/main-images` 由页面自身接管顶部导航。
- `frontend/src/pages/DetailPageGeneratorPage.tsx`：详情页生成页面
- `frontend/src/pages/TasksPage.tsx`：任务记录页
- `frontend/src/services/http.ts`：统一请求封装
- `frontend/src/hooks/useTasks.ts`：任务查询 hook

## 设计规范文档
- `docs/design/ui-system.md`：全局 UI 视觉基础规范（颜色、字体、间距、圆角、阴影、动效、可访问性）。
- `docs/design/page-layout-rules.md`：页面级布局规则（顶部导航 + 左操作 + 右进度结果）。
- `docs/design/component-rules.md`：核心组件规范（上传卡、标签、参数区、进度区、结果卡、按钮）。
- `docs/design/anti-patterns.md`：禁止事项与常见反模式清单。
