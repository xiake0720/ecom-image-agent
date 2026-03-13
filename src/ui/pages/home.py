"""首页与任务执行入口。"""

from __future__ import annotations

import logging
from pathlib import Path

import streamlit as st

from src.core.config import get_settings
from src.core.constants import DEFAULT_CATEGORY
from src.core.logging import (
    attach_task_file_handler,
    detach_task_file_handler,
    get_task_log_path,
    initialize_logging,
    log_context,
)
from src.core.paths import ensure_task_dirs
from src.domain.generation_result import GenerationResult
from src.domain.qc_report import QCReport
from src.domain.task import Task, TaskStatus
from src.providers.router import build_capability_bindings
from src.services.storage.local_storage import LocalStorageService
from src.services.storage.task_loader import load_task_context
from src.ui.components.upload_panel import render_upload_panel
from src.ui.pages.result_view import render_result_view
from src.ui.pages.task_form import render_task_form
from src.ui.state import ensure_ui_state
from src.workflows.graph import build_workflow, run_render_stage_only
from src.workflows.state import WorkflowExecutionError, format_workflow_log

DEBUG_JSON_FILENAMES = [
    "task.json",
    "product_analysis.json",
    "shot_plan.json",
    "copy_plan.json",
    "layout_plan.json",
    "image_prompt_plan.json",
    "qc_report.json",
    "qc_report_preview.json",
]
logger = logging.getLogger(__name__)


def render_home_page() -> None:
    settings = get_settings()
    bindings = build_capability_bindings(settings)
    initialize_logging(settings)
    st.set_page_config(page_title="ecom-image-agent", layout="wide")
    ensure_ui_state()

    st.title("ecom-image-agent")
    st.caption("本地运行的电商图片生成工具，支持预览优先与正式成品两阶段生成。")
    _render_runtime_controls(settings, bindings)

    left, right = st.columns([1, 1])
    with left:
        st.subheader("任务参数")
        uploads = render_upload_panel()
        form_data = render_task_form()
        action_col1, action_col2 = st.columns(2)
        preview_submitted = action_col1.button("先生成预览", use_container_width=True)
        final_submitted = action_col2.button("生成正式成品", type="primary", use_container_width=True)

        if preview_submitted:
            if not uploads:
                st.session_state["task_error"] = "请至少上传 1 张图片。"
            else:
                _submit_task(lambda: _run_task(form_data, uploads, forced_render_mode="preview"))

        if final_submitted:
            if _has_resumable_preview_state(st.session_state.get("task_state")):
                _submit_task(lambda: _continue_final_from_existing_task(st.session_state.get("task_state")))
            elif uploads:
                _submit_task(lambda: _run_task(form_data, uploads, forced_render_mode="full_auto"))
            else:
                st.session_state["task_error"] = "请先上传图片，或先生成预览后再生成正式成品。"

        if st.session_state.get("task_error"):
            st.error(st.session_state["task_error"])

    with right:
        render_result_view(st.session_state.get("task_state"))


def _submit_task(runner) -> None:
    try:
        st.session_state["task_error"] = None
        st.session_state["task_state"] = runner()
    except WorkflowExecutionError as exc:
        logger.exception("任务执行失败：%s", exc)
        st.session_state["task_error"] = str(exc)
        st.session_state["task_state"] = getattr(exc, "task_state", None)
    except Exception as exc:
        logger.exception("页面层捕获到未包装异常：%s", exc)
        st.session_state["task_error"] = str(exc)


def _run_task(form_data: dict[str, object], uploads, *, forced_render_mode: str) -> dict:
    settings = get_settings()
    initialize_logging(settings)
    storage = LocalStorageService()
    task_id = storage.create_task_id()
    task_dirs = ensure_task_dirs(task_id)
    task_log_path = attach_task_file_handler(task_id, task_dirs["task"], settings=settings)
    task = Task(
        task_id=task_id,
        brand_name=str(form_data["brand_name"]),
        product_name=str(form_data["product_name"]),
        category=DEFAULT_CATEGORY,
        platform=str(form_data["platform"]),
        output_size=str(form_data["output_size"]),
        shot_count=int(form_data["shot_count"]),
        copy_tone=str(form_data["copy_tone"]),
        status=TaskStatus.RUNNING,
        task_dir=str(task_dirs["task"]),
    )
    try:
        with log_context(task_id=task_id):
            storage.save_task_manifest(task)
            uploads_payload = [(upload.name, upload.getvalue()) for upload in uploads]
            assets = storage.save_uploads(task_id, uploads_payload)
            debug_info = _build_debug_info(task, settings, task_log_path)
            initial_logs = [
                format_workflow_log(
                    task_id=task_id,
                    node_name="streamlit_entry",
                    event="start",
                    detail=f"页面已提交，开始创建任务并保存输入素材，render_mode={forced_render_mode}",
                ),
            ]
            workflow = build_workflow()
            initial_state = {
                "task": task,
                "assets": assets,
                "logs": initial_logs,
                "cache_enabled": bool(form_data.get("cache_enabled", settings.enable_node_cache)),
                "ignore_cache": bool(form_data.get("ignore_cache", False)),
                "prompt_build_mode": str(form_data.get("prompt_build_mode", settings.resolve_prompt_build_mode())),
                "render_mode": forced_render_mode,
                "analyze_max_reference_images": int(form_data.get("analyze_max_reference_images", settings.analyze_max_reference_images)),
                "render_max_reference_images": int(form_data.get("render_max_reference_images", settings.render_max_reference_images)),
            }
            state = workflow.invoke(initial_state)
            normalized = _normalize_task_state(state, debug_info)
            return normalized
    finally:
        detach_task_file_handler(task_id)


def _continue_final_from_existing_task(existing_task_state: dict | None) -> dict:
    if not existing_task_state:
        raise RuntimeError("No preview task state available.")
    settings = get_settings()
    task_id = _extract_task_id(existing_task_state)
    if not task_id:
        raise RuntimeError("Cannot resolve task_id from preview task state.")
    task_dir = ensure_task_dirs(task_id)["task"]
    task_log_path = attach_task_file_handler(task_id, task_dir, settings=settings)
    try:
        loaded = load_task_context(task_id)
        task = loaded["task"]
        debug_info = _build_debug_info(task, settings, task_log_path)
        preview_generation_result = _extract_generation_result(existing_task_state.get("preview_generation_result"))
        initial_state = {
            **loaded,
            "logs": [
                *existing_task_state.get("logs", []),
                format_workflow_log(
                    task_id=task_id,
                    node_name="streamlit_entry",
                    event="resume_final",
                    detail="检测到已有预览任务，直接基于现有 image_prompt_plan 继续生成正式成品",
                ),
            ],
            "render_mode": "final",
            "render_variant": "final",
            "preview_generation_result": preview_generation_result,
            "analyze_max_reference_images": int(existing_task_state.get("analyze_max_reference_images", settings.analyze_max_reference_images)),
            "render_max_reference_images": int(existing_task_state.get("render_max_reference_images", settings.render_max_reference_images)),
        }
        state = run_render_stage_only(initial_state)
        normalized = _normalize_task_state(state, debug_info)
        if preview_generation_result is not None:
            normalized["preview_generation_result"] = preview_generation_result.model_dump(mode="json")
        if existing_task_state.get("preview_export_zip_path"):
            normalized["preview_export_zip_path"] = existing_task_state.get("preview_export_zip_path")
        return normalized
    finally:
        detach_task_file_handler(task_id)


def _normalize_task_state(state: dict, debug_info: dict[str, object]) -> dict:
    normalized = dict(state)
    if "task" in normalized and hasattr(normalized["task"], "model_dump"):
        normalized["task"] = normalized["task"].model_dump(mode="json")
    if "generation_result" in normalized and hasattr(normalized["generation_result"], "model_dump"):
        normalized["generation_result"] = normalized["generation_result"].model_dump(mode="json")
    if "preview_generation_result" in normalized and hasattr(normalized["preview_generation_result"], "model_dump"):
        normalized["preview_generation_result"] = normalized["preview_generation_result"].model_dump(mode="json")
    if "qc_report" in normalized and hasattr(normalized["qc_report"], "model_dump"):
        normalized["qc_report"] = normalized["qc_report"].model_dump(mode="json")
    if "preview_qc_report" in normalized and hasattr(normalized["preview_qc_report"], "model_dump"):
        normalized["preview_qc_report"] = normalized["preview_qc_report"].model_dump(mode="json")
    normalized["debug"] = debug_info
    if "analyze_max_reference_images" in state:
        normalized["analyze_max_reference_images"] = state["analyze_max_reference_images"]
    if "render_max_reference_images" in state:
        normalized["render_max_reference_images"] = state["render_max_reference_images"]
    return normalized


def _extract_generation_result(payload) -> GenerationResult | None:
    if not payload:
        return None
    if isinstance(payload, GenerationResult):
        return payload
    return GenerationResult.model_validate(payload)


def _extract_task_id(task_state: dict) -> str | None:
    debug = task_state.get("debug", {})
    if debug.get("task_id"):
        return str(debug["task_id"])
    task = task_state.get("task", {})
    if isinstance(task, dict) and task.get("task_id"):
        return str(task["task_id"])
    return None


def _has_resumable_preview_state(task_state: dict | None) -> bool:
    if not task_state:
        return False
    return bool(task_state.get("preview_generation_result") or task_state.get("render_variant") == "preview" or task_state.get("preview_export_zip_path"))


def _build_debug_info(task: Task, settings, task_log_path: Path | None) -> dict[str, object]:
    bindings = build_capability_bindings(settings)
    task_dir = Path(task.task_dir)
    return {
        **settings.build_debug_summary(),
        "text_provider_impl": bindings.planning_provider_name,
        "vision_provider_impl": bindings.vision_provider_name,
        "image_provider_impl": bindings.image_provider_name,
        "text_provider_status": bindings.planning_provider_status,
        "vision_provider_status": bindings.vision_provider_status,
        "image_provider_status": bindings.image_provider_status,
        "task_id": task.task_id,
        "task_dir": str(task_dir),
        "workflow_log_path": str(task_log_path or get_task_log_path(task_dir)),
        "node_cache_enabled_default": settings.enable_node_cache,
        "prompt_build_mode_default": settings.resolve_prompt_build_mode(),
        "render_mode_default": settings.resolve_render_mode(),
        "analyze_max_reference_images_default": settings.analyze_max_reference_images,
        "render_max_reference_images_default": settings.render_max_reference_images,
        "artifact_paths": {filename: str(task_dir / filename) for filename in DEBUG_JSON_FILENAMES},
    }


def _render_runtime_controls(settings, bindings) -> None:
    with st.expander("当前 Provider 状态", expanded=True):
        action_col, info_col = st.columns([1, 3])
        if action_col.button("重新加载配置 / 重建 Workflow", use_container_width=True):
            st.session_state["_ecom_reload_runtime"] = True
            st.rerun()
        info_col.caption("修改环境变量或 .env 后，可点击此按钮清理缓存并重建 workflow。")

        top_cols = st.columns(5)
        top_cols[0].metric("Budget Mode", settings.resolve_budget_mode())
        top_cols[1].metric("Text Provider", bindings.planning_route.alias)
        top_cols[2].metric("Text Model", bindings.planning_model_selection.model_id)
        top_cols[3].metric("Vision Alias", bindings.vision_route.alias)
        top_cols[4].metric("Image Alias", bindings.image_route.alias)

        mode_cols = st.columns(4)
        mode_cols[0].metric("Prompt Build", settings.resolve_prompt_build_mode())
        mode_cols[1].metric("Render Mode", settings.resolve_render_mode())
        mode_cols[2].metric("Preview Shots", str(settings.preview_shot_count))
        mode_cols[3].metric("Preview Size", settings.preview_output_size)
        ref_cols = st.columns(2)
        ref_cols[0].metric("Analyze Refs", str(settings.analyze_max_reference_images))
        ref_cols[1].metric("Render Refs", str(settings.render_max_reference_images))
        st.caption(f"当前文本实现={bindings.planning_provider_name}，当前文本模型={bindings.planning_model_selection.model_id}")

        st.caption(
            f"节点缓存默认值: {'开启' if settings.enable_node_cache else '关闭'}，缓存目录: {settings.cache_dir}"
        )
