from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.core.constants import DEFAULT_CATEGORY
from src.core.paths import ensure_task_dirs
from src.domain.task import Task, TaskStatus
from src.services.storage.local_storage import LocalStorageService
from src.ui.components.upload_panel import render_upload_panel
from src.ui.pages.result_view import render_result_view
from src.ui.pages.task_form import render_task_form
from src.ui.state import ensure_ui_state
from src.workflows.graph import build_workflow


def render_home_page() -> None:
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
                except Exception as exc:
                    st.session_state["task_error"] = str(exc)

        if st.session_state.get("task_error"):
            st.error(st.session_state["task_error"])

    with right:
        render_result_view(st.session_state.get("task_state"))


def _run_task(form_data: dict[str, object], uploads) -> dict:
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

    workflow = build_workflow()
    state = workflow.invoke({"task": task, "assets": assets, "logs": [f"Created task {task_id}."]})

    state["task"] = state["task"].model_dump(mode="json")
    state["generation_result"] = state["generation_result"].model_dump(mode="json")
    if "qc_report" in state:
        state["qc_report"] = state["qc_report"].model_dump(mode="json")
    sample_path = Path(task_dirs["previews"]) / "text_render_test.png"
    from src.services.rendering.text_renderer import TextRenderer

    TextRenderer().render_test_image(str(sample_path))
    state["logs"].append(f"Saved text render sample to {sample_path}.")
    return state

