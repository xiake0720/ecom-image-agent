"""首页与任务执行入口。

文件位置：
- `src/ui/pages/home.py`

职责：
- 组织极简 UI：首页文案、上传区、基础参数区、进度区、结果区
- 把用户高层输入组装成 `Task`
- 启动固定 v2 主工作流
"""

from __future__ import annotations

import logging

import streamlit as st

from backend.engine.core.config import get_settings
from backend.engine.core.constants import DEFAULT_CATEGORY
from backend.engine.core.logging import attach_task_file_handler, detach_task_file_handler, initialize_logging, log_context
from backend.engine.core.paths import ensure_task_dirs
from backend.engine.domain.asset import AssetType
from backend.engine.domain.task import Task, TaskStatus
from backend.engine.services.storage.local_storage import LocalStorageService
from backend.legacy.ui.components.upload_panel import render_upload_panel
from backend.legacy.ui.pages.result_view import render_result_view
from backend.legacy.ui.pages.task_form import render_task_form
from backend.legacy.ui.state import ensure_ui_state
from backend.engine.workflows.graph import run_workflow
from backend.engine.workflows.state import WorkflowExecutionError, WorkflowState, format_workflow_log

logger = logging.getLogger(__name__)


def render_home_page() -> None:
    """渲染首页。"""

    settings = get_settings()
    initialize_logging(settings)
    st.set_page_config(page_title="ecom-image-agent", layout="wide")
    ensure_ui_state()

    st.title("整套电商产品图生成器")
    st.caption(
        "上传产品外包装白底图，选择整体风格方向，可选补充产品参考图和背景风格参考图。"
        "系统会自动规划并生成一套 8 张天猫风格产品图。"
    )

    uploads = render_upload_panel()
    form_data = render_task_form()

    st.subheader("开始生成")
    st.caption("流程：上传图 -> 选择整体风格 -> 自动生成整套图")

    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    result_placeholder = st.empty()
    _render_progress(progress_placeholder, status_placeholder, st.session_state.get("task_state"))

    start_clicked = st.button("生成整套产品图", type="primary", width="stretch")
    if start_clicked:
        _submit_task(
            form_data=form_data,
            uploads=uploads,
            progress_placeholder=progress_placeholder,
            status_placeholder=status_placeholder,
            result_placeholder=result_placeholder,
        )

    if st.session_state.get("task_error"):
        st.error(st.session_state["task_error"])

    if not start_clicked:
        _render_result_section(result_placeholder, st.session_state.get("task_state"))


def _submit_task(
    *,
    form_data: dict[str, object],
    uploads: dict[str, object],
    progress_placeholder,
    status_placeholder,
    result_placeholder,
) -> None:
    """统一处理任务提交与简洁错误提示。"""

    try:
        st.session_state["task_error"] = None
        st.session_state["task_state"] = _run_task(
            form_data=form_data,
            uploads=uploads,
            on_progress=lambda state: _update_progress_ui(
                progress_placeholder,
                status_placeholder,
                result_placeholder,
                state,
            ),
        )
    except WorkflowExecutionError as exc:
        logger.exception("任务执行失败: %s", exc)
        st.session_state["task_state"] = _normalize_task_state(exc.task_state or {})
        st.session_state["task_error"] = str(exc)
        _render_progress(progress_placeholder, status_placeholder, st.session_state["task_state"])
        _render_result_section(result_placeholder, st.session_state["task_state"])
    except Exception as exc:
        logger.exception("页面层捕获到未包装异常: %s", exc)
        st.session_state["task_error"] = "生成失败，请重试或检查素材/配置。"
        _render_result_section(result_placeholder, st.session_state.get("task_state"))


def _run_task(*, form_data: dict[str, object], uploads: dict[str, object], on_progress) -> dict[str, object]:
    """创建任务目录、保存输入并执行固定主链。"""

    white_bg = uploads.get("white_bg")
    product_references = list(uploads.get("product_references") or [])
    background_style_references = list(uploads.get("background_style_references") or [])
    if white_bg is None:
        raise WorkflowExecutionError("素材缺失，请先上传外包装白底图。", logs=[])

    settings = get_settings()
    initialize_logging(settings)
    storage = LocalStorageService()
    task_id = storage.create_task_id()
    task_dirs = ensure_task_dirs(task_id)
    attach_task_file_handler(task_id, task_dirs["task"], settings=settings)
    task = Task(
        task_id=task_id,
        brand_name=str(form_data["brand_name"]),
        product_name=str(form_data["product_name"]),
        category=DEFAULT_CATEGORY,
        platform="tmall",
        shot_count=int(form_data["shot_count"]),
        aspect_ratio=str(form_data["aspect_ratio"]),
        image_size=str(form_data["image_size"]),
        status=TaskStatus.RUNNING,
        task_dir=str(task_dirs["task"]),
        style_type=str(form_data["style_type"]),
        style_notes=str(form_data["style_notes"]),
    )
    try:
        with log_context(task_id=task_id):
            storage.save_task_manifest(task)
            uploads_payload = [
                (white_bg.name, white_bg.getvalue(), AssetType.WHITE_BG),
                *[(upload.name, upload.getvalue(), AssetType.DETAIL) for upload in product_references],
                *[(upload.name, upload.getvalue(), AssetType.BACKGROUND_STYLE) for upload in background_style_references],
            ]
            assets = storage.save_uploads(task_id, uploads_payload)
            initial_state: WorkflowState = {
                "task": task,
                "assets": assets,
                "logs": [
                    format_workflow_log(
                        task_id=task_id,
                        node_name="streamlit_entry",
                        event="start",
                        detail="页面已提交，开始执行 v2 固定主链",
                    )
                ],
                "cache_enabled": bool(settings.enable_node_cache),
                "ignore_cache": False,
            }
            result = run_workflow(initial_state, on_progress=lambda state: on_progress(_normalize_task_state(state)))
            return _normalize_task_state(result)
    finally:
        detach_task_file_handler(task_id)


def _update_progress_ui(progress_placeholder, status_placeholder, result_placeholder, state: dict[str, object]) -> None:
    """更新会话态与前端进度、结果区。"""

    normalized = _normalize_task_state(state)
    st.session_state["task_state"] = normalized
    _render_progress(progress_placeholder, status_placeholder, normalized)
    _render_result_section(result_placeholder, normalized)


def _render_progress(progress_placeholder, status_placeholder, task_state: dict | None) -> None:
    """渲染进度条与当前步骤。"""

    if not task_state:
        progress_placeholder.progress(0, text="等待开始")
        status_placeholder.caption("点击“生成整套产品图”后会显示当前步骤。")
        return

    progress_percent = int(task_state.get("progress_percent", 0))
    step_label = str(task_state.get("current_step_label") or "准备中")
    progress_placeholder.progress(max(0, min(progress_percent, 100)), text=step_label)
    if task_state.get("error_message"):
        status_placeholder.error(str(task_state["error_message"]))
    else:
        status_placeholder.caption(step_label)


def _render_result_section(result_placeholder, task_state: dict | None) -> None:
    """在固定占位容器中刷新结果区，支持生成中增量显示。"""

    with result_placeholder.container():
        render_result_view(task_state)


def _normalize_task_state(state: dict | WorkflowState) -> dict[str, object]:
    """把 workflow 结果归一化为适合 session_state 的结构。"""

    normalized = dict(state or {})
    for field_name in (
        "task",
        "director_output",
        "prompt_plan_v2",
        "generation_result",
        "generation_result_v2",
        "qc_report",
        "qc_report_v2",
    ):
        payload = normalized.get(field_name)
        if hasattr(payload, "model_dump"):
            normalized[field_name] = payload.model_dump(mode="json")
    if "task" in normalized and isinstance(normalized["task"], dict):
        task = normalized["task"]
        normalized["current_step"] = task.get("current_step", normalized.get("current_step", ""))
        normalized["current_step_label"] = task.get("current_step_label", normalized.get("current_step_label", ""))
        normalized["progress_percent"] = task.get("progress_percent", normalized.get("progress_percent", 0))
        normalized["error_message"] = task.get("error_message", normalized.get("error_message", ""))
    return normalized
