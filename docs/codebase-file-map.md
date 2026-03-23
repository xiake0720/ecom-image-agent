# Codebase File Map

## 核心入口
- `streamlit_app.py`
  - Streamlit 唯一入口
- `src/ui/pages/home.py`
  - 极简首页、任务提交、进度刷新、增量结果展示

## Workflow
- `src/workflows/graph.py`
  - v2 固定主链执行器，负责节点级进度与节点内增量进度转发
- `src/workflows/state.py`
  - workflow state、依赖容器、进度字段
- `src/workflows/nodes/ingest_assets.py`
  - 素材校验
- `src/workflows/nodes/director_v2.py`
  - 图组导演规划
- `src/workflows/nodes/prompt_refine_v2.py`
  - 逐图 prompt 与文案收口
- `src/workflows/nodes/render_images.py`
  - 生图、内部 overlay fallback、按张回传局部结果
- `src/workflows/nodes/run_qc.py`
  - 最小 QC
- `src/workflows/nodes/finalize.py`
  - 状态收尾与导出

## Domain
- `src/domain/task.py`
  - 任务参数与进度字段
- `src/domain/director_output.py`
  - `director_output.json` 对应 contract
- `src/domain/prompt_plan_v2.py`
  - `prompt_plan_v2.json` 对应 contract
- `src/domain/generation_result.py`
  - 生图结果
- `src/domain/qc_report.py`
  - `qc_report.json` 对应 contract
- `src/domain/image_prompt_plan.py`
  - render fallback 兼容型 prompt contract

## Providers
- `src/providers/router.py`
  - v2 主链 provider 绑定
- `src/providers/llm/runapi_openai_text.py`
  - RunAPI 文本调用
- `src/providers/image/runapi_gemini31_image.py`
  - RunAPI Gemini 3.1 图片调用，兼容 `inlineData` 与 `fileData.fileUri` 返回

## Services
- `src/services/assets/reference_selector.py`
  - 参考图选择
- `src/services/rendering/text_renderer.py`
  - Pillow 中文后贴字
- `src/services/storage/local_storage.py`
  - 本地任务目录和 JSON 落盘
- `src/services/storage/zip_export.py`
  - 结果 ZIP 和任务包 ZIP 导出

## UI Components
- `src/ui/components/upload_panel.py`
  - 文件上传区
- `src/ui/pages/task_form.py`
  - 必要参数区
- `src/ui/components/preview_grid.py`
  - 最终图片网格
- `src/ui/components/download_panel.py`
  - 下载按钮
- `src/ui/pages/result_view.py`
  - 已完成图片展示与结果下载入口

## Tests
- `tests/unit/test_config_security.py`
- `tests/unit/test_logging_setup.py`
- `tests/unit/test_reference_selector.py`
- `tests/unit/test_director_v2.py`
- `tests/unit/test_prompt_refine_v2.py`
- `tests/unit/test_render_v2_and_qc.py`
- `tests/unit/test_workflow_progress.py`
