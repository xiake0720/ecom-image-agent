# Architecture

## 目标
当前仓库是单体 Streamlit 应用，围绕 v2 电商图主链做最小可运行实现，重点是：

- 本地可运行
- 链路清晰
- 结构化落盘
- 易于回放和排查

## 分层

### `src/ui/`
- 只负责页面、交互和结果展示
- 当前页面只保留上传、必要参数、执行、进度、最终结果

### `src/workflows/`
- 只负责主链状态和节点编排
- `graph.py` 固定为单链路执行器

### `src/domain/`
- 只保留当前主链需要的 contract：
  - `asset`
  - `task`
  - `director_output`
  - `prompt_plan_v2`
  - `generation_result`
  - `qc_report`
  - `image_prompt_plan`（仅供 render fallback 兼容）

### `src/providers/`
- 只保留当前主链实际可用的文本与图片 provider

### `src/services/`
- 只保留素材选择、Pillow 后贴字、本地存储与 ZIP 导出等通用能力

## 当前执行模式
- 唯一 UI 入口：`streamlit_app.py`
- 唯一 workflow：v2 固定主链
- 唯一存储介质：本地文件系统

## 设计取舍
- overlay fallback 保留，但内聚到 `render_images`
- QC 仅保留最小闭环，不再做旧链路复杂审查
- 不再暴露 debug 页面、链路图和中间 JSON
