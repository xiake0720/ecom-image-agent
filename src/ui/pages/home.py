"""首页与任务执行入口。

该模块位于 `src/ui/pages/`，负责：
- 渲染 Streamlit 首页
- 收集上传和表单参数
- 触发 workflow 执行
- 将任务结果写入 session_state

这里不直接实现 provider 细节，只负责 UI 到 workflow 的最小衔接。
"""

from __future__ import annotations

import logging
from pathlib import Path

import streamlit as st

from src.core.config import get_settings
from src.core.constants import DEFAULT_CATEGORY
from src.core.logging import (
    attach_task_file_handler,
    detach_task_file_handler,
    initialize_logging,
    log_context,
)
from src.core.paths import ensure_task_dirs
from src.domain.task import Task, TaskStatus
from src.services.storage.local_storage import LocalStorageService
from src.ui.components.upload_panel import render_upload_panel
from src.ui.pages.result_view import render_result_view
from src.ui.pages.task_form import render_task_form
from src.ui.state import ensure_ui_state
from src.workflows.graph import build_workflow
from src.workflows.state import WorkflowExecutionError, format_workflow_log

DEBUG_JSON_FILENAMES = [
    "task.json",
    "product_analysis.json",
    "shot_plan.json",
    "copy_plan.json",
    "layout_plan.json",
    "image_prompt_plan.json",
    "qc_report.json",
]
logger = logging.getLogger(__name__)


def render_home_page() -> None:
    """渲染首页并处理用户交互。"""
    settings = get_settings()
    text_selection = settings.resolve_text_model_selection()
    vision_selection = settings.resolve_vision_model_selection()
    initialize_logging(settings)
    st.set_page_config(page_title="ecom-image-agent", layout="wide")
    ensure_ui_state()
    logger.info(
        "首页渲染完成，当前文本模式=%s，视觉模式=%s，图片模式=%s，默认规划模型=%s，默认视觉模型=%s",
        settings.text_provider_mode,
        settings.vision_provider_mode,
        settings.image_provider_mode,
        text_selection.model_id,
        vision_selection.model_id,
    )

    st.title("ecom-image-agent")
    st.caption("本地运行的电商自动生图 MVP，当前优先支持茶叶品类。")

    left, right = st.columns([1, 1])

    with left:
        st.subheader("任务参数")
        uploads = render_upload_panel()
        form_data = render_task_form()
        submitted = st.button("开始生成", type="primary", use_container_width=True)

        if submitted:
            if not uploads:
                logger.warning("页面提交失败：未上传任何图片")
                st.session_state["task_error"] = "请至少上传 1 张图片。"
            else:
                try:
                    st.session_state["task_error"] = None
                    st.session_state["task_state"] = _run_task(form_data, uploads)
                except WorkflowExecutionError as exc:
                    logger.exception("任务执行失败：%s", exc)
                    st.session_state["task_error"] = str(exc)
                    st.session_state["task_state"] = getattr(exc, "task_state", None)
                except Exception as exc:
                    logger.exception("页面层捕获到未包装异常：%s", exc)
                    st.session_state["task_error"] = str(exc)

        if st.session_state.get("task_error"):
            st.error(st.session_state["task_error"])

    with right:
        render_result_view(st.session_state.get("task_state"))


def _run_task(form_data: dict[str, object], uploads) -> dict:
    """执行一次任务并返回可供 UI 展示的状态。

    失败时异常会继续向上抛给页面层显示，避免 silent failure。
    """
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
            with log_context(node_name="streamlit_entry"):
                logger.info("任务开始执行，准备创建任务目录、写入 task.json 并保存上传素材")
                if task_log_path:
                    logger.info("任务文件日志已启用，日志路径=%s", task_log_path)
                else:
                    logger.info("任务文件日志已关闭，本次仅输出控制台日志和页面日志")

            storage.save_task_manifest(task)
            uploads_payload = [(upload.name, upload.getvalue()) for upload in uploads]
            assets = storage.save_uploads(task_id, uploads_payload)
            debug_info = _build_debug_info(task, settings, task_log_path)
            upload_names = ", ".join(upload.name for upload in uploads)
            initial_logs = [
                format_workflow_log(
                    task_id=task_id,
                    node_name="streamlit_entry",
                    event="start",
                    detail="页面已提交，开始创建任务并保存输入素材",
                ),
                format_workflow_log(
                    task_id=task_id,
                    node_name="streamlit_entry",
                    event="config",
                    detail=(
                        f"text_provider_mode={settings.text_provider_mode}, "
                        f"vision_provider_mode={settings.vision_provider_mode}, "
                        f"image_provider_mode={settings.image_provider_mode}, "
                        f"text_model={settings.resolve_text_model_selection().model_id}, "
                        f"vision_model={settings.resolve_vision_model_selection().model_id}, "
                        f"log_level={settings.log_level.upper()}"
                    ),
                ),
                format_workflow_log(
                    task_id=task_id,
                    node_name="streamlit_entry",
                    event="paths",
                    output_hint=task.task_dir,
                    detail="任务目录已创建",
                ),
                format_workflow_log(
                    task_id=task_id,
                    node_name="streamlit_entry",
                    event="uploads",
                    detail=f"已保存上传素材：{upload_names}",
                ),
                format_workflow_log(
                    task_id=task_id,
                    node_name="langgraph_invoke",
                    event="start",
                    detail="开始调用 LangGraph 工作流",
                ),
            ]

            with log_context(node_name="streamlit_entry"):
                logger.info(
                    "任务初始化完成，task_id=%s，输出目录=%s，上传文件=%s",
                    task_id,
                    task.task_dir,
                    upload_names,
                )

            workflow = build_workflow()
            initial_state = {
                "task": task,
                "assets": assets,
                "logs": initial_logs,
            }
            try:
                with log_context(node_name="langgraph_invoke"):
                    logger.info("工作流开始执行")
                    state = workflow.invoke(initial_state)
            except WorkflowExecutionError as exc:
                with log_context(node_name="langgraph_invoke"):
                    logger.exception("工作流执行失败：%s", exc)
                partial_state = {
                    "task": task.model_dump(mode="json"),
                    "logs": [
                        *exc.logs,
                        format_workflow_log(
                            task_id=task_id,
                            node_name="langgraph_invoke",
                            event="error",
                            detail=f"工作流执行失败：{exc}",
                            level="ERROR",
                        ),
                    ],
                    "debug": debug_info,
                    "generation_result": {"images": []},
                }
                exc.task_state = partial_state
                raise
            except Exception as exc:
                with log_context(node_name="langgraph_invoke"):
                    logger.exception("工作流调用失败：%s", exc)
                failure_logs = [
                    *initial_logs,
                    format_workflow_log(
                        task_id=task_id,
                        node_name="langgraph_invoke",
                        event="error",
                        detail=f"工作流调用失败：{exc}",
                        level="ERROR",
                    ),
                ]
                workflow_error = WorkflowExecutionError(
                    f"workflow invoke failed for task {task_id}: {exc}",
                    logs=failure_logs,
                    task_id=task_id,
                    node_name="langgraph_invoke",
                )
                workflow_error.task_state = {
                    "task": task.model_dump(mode="json"),
                    "logs": failure_logs,
                    "debug": debug_info,
                    "generation_result": {"images": []},
                }
                raise workflow_error from exc

            state["task"] = state["task"].model_dump(mode="json")
            state["generation_result"] = state["generation_result"].model_dump(mode="json")
            if "qc_report" in state:
                state["qc_report"] = state["qc_report"].model_dump(mode="json")
            sample_path = Path(task_dirs["previews"]) / "text_render_test.png"
            from src.services.rendering.text_renderer import TextRenderer

            # 额外保留一张文本渲染样图，方便快速验证后贴字链路是否可用。
            with log_context(node_name="streamlit_entry"):
                TextRenderer().render_test_image(str(sample_path))
                logger.info("文本渲染测试样图已生成，路径=%s", sample_path)

            state["logs"].extend(
                [
                    format_workflow_log(
                        task_id=task_id,
                        node_name="streamlit_entry",
                        event="artifact",
                        output_hint=str(sample_path),
                        detail="已生成文本渲染测试样图",
                    ),
                    format_workflow_log(
                        task_id=task_id,
                        node_name="langgraph_invoke",
                        event="finish",
                        detail="工作流执行完成，结果已归一化到页面状态",
                    ),
                ]
            )
            with log_context(node_name="langgraph_invoke"):
                logger.info("工作流整体执行完成")
            with log_context(node_name="streamlit_entry"):
                logger.info("任务执行完成，task_id=%s，任务目录=%s", task_id, task.task_dir)

            state["debug"] = debug_info
            return state
    finally:
        detach_task_file_handler(task_id)


def _build_debug_info(task: Task, settings, task_log_path: Path | None) -> dict[str, object]:
    """构建结果页调试区需要的静态信息。"""
    task_dir = Path(task.task_dir)
    return {
        **settings.build_debug_summary(),
        "task_id": task.task_id,
        "task_dir": str(task_dir),
        "workflow_log_path": str(task_log_path) if task_log_path else "-",
        "artifact_paths": {
            filename: str(task_dir / filename)
            for filename in DEBUG_JSON_FILENAMES
        },
    }
