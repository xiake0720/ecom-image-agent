"""首页与任务执行入口。

该模块位于 `src/ui/pages/`，负责：
- 渲染 Streamlit 首页
- 收集上传和表单参数
- 触发 workflow 执行
- 将任务结果写入 session_state

这里不直接实现 provider 细节，只负责 UI 到 workflow 的最小衔接。
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.core.config import get_settings
from src.core.constants import DEFAULT_CATEGORY
from src.core.paths import ensure_task_dirs
from src.domain.task import Task, TaskStatus
from src.services.storage.local_storage import LocalStorageService
from src.ui.components.upload_panel import render_upload_panel
from src.ui.pages.result_view import render_result_view
from src.ui.pages.task_form import render_task_form
from src.ui.state import ensure_ui_state
from src.workflows.graph import build_workflow
from src.workflows.state import WorkflowExecutionError

DEBUG_JSON_FILENAMES = [
    "task.json",
    "product_analysis.json",
    "shot_plan.json",
    "copy_plan.json",
    "layout_plan.json",
    "image_prompt_plan.json",
    "qc_report.json",
]


def render_home_page() -> None:
    """渲染首页并处理用户交互。"""
    st.set_page_config(page_title="ecom-image-agent", layout="wide")
    ensure_ui_state()

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
                st.session_state["task_error"] = "请至少上传 1 张图片。"
            else:
                try:
                    st.session_state["task_error"] = None
                    st.session_state["task_state"] = _run_task(form_data, uploads)
                except WorkflowExecutionError as exc:
                    st.session_state["task_error"] = str(exc)
                    st.session_state["task_state"] = getattr(exc, "task_state", None)
                except Exception as exc:
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
    storage = LocalStorageService()
    task_id = storage.create_task_id()
    task_dirs = ensure_task_dirs(task_id)
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
    storage.save_task_manifest(task)
    uploads_payload = [(upload.name, upload.getvalue()) for upload in uploads]
    assets = storage.save_uploads(task_id, uploads_payload)
    debug_info = _build_debug_info(task, settings)
    initial_logs = [
        f"[INFO] | task_id={task_id} | node=streamlit_entry | event=start | detail=streamlit_app.py -> render_home_page -> _run_task",
        (
            f"[INFO] | task_id={task_id} | node=streamlit_entry | event=config | "
            f"detail=text_provider_mode={settings.text_provider_mode}, "
            f"vision_provider_mode={settings.vision_provider_mode}, "
            f"image_provider_mode={settings.image_provider_mode}"
        ),
        f"[INFO] | task_id={task_id} | node=streamlit_entry | event=paths | output={task.task_dir} | detail=task artifacts root",
        f"[INFO] | task_id={task_id} | node=streamlit_entry | event=uploads | detail={', '.join(upload.name for upload in uploads)}",
        f"[INFO] | task_id={task_id} | node=langgraph_invoke | event=start | detail=build_workflow().invoke(...)",
    ]

    workflow = build_workflow()
    initial_state = {
        "task": task,
        "assets": assets,
        "logs": initial_logs,
    }
    try:
        state = workflow.invoke(initial_state)
    except WorkflowExecutionError as exc:
        partial_state = {
            "task": task.model_dump(mode="json"),
            "logs": [
                *exc.logs,
                f"[ERROR] | task_id={task_id} | node=langgraph_invoke | event=error | detail={exc}",
            ],
            "debug": debug_info,
            "generation_result": {"images": []},
        }
        exc.task_state = partial_state
        raise
    except Exception as exc:
        failure_logs = [
            *initial_logs,
            f"[ERROR] | task_id={task_id} | node=langgraph_invoke | event=error | detail={exc}",
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
    TextRenderer().render_test_image(str(sample_path))
    state["logs"].extend(
        [
            f"[INFO] | task_id={task_id} | node=streamlit_entry | event=artifact | output={sample_path} | detail=text render sample",
            f"[INFO] | task_id={task_id} | node=langgraph_invoke | event=finish | detail=workflow completed and UI state normalized",
        ]
    )
    state["debug"] = debug_info
    return state


def _build_debug_info(task: Task, settings) -> dict[str, object]:
    """构建结果页调试区需要的静态信息。"""
    task_dir = Path(task.task_dir)
    return {
        **settings.build_debug_summary(),
        "task_id": task.task_id,
        "task_dir": str(task_dir),
        "artifact_paths": {
            filename: str(task_dir / filename)
            for filename in DEBUG_JSON_FILENAMES
        },
    }
