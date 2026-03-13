"""收尾与导出节点。"""

from __future__ import annotations

from pathlib import Path

from src.domain.task import TaskStatus
from src.services.storage.zip_export import export_full_task_bundle, export_task_zip
from src.workflows.state import WorkflowDependencies, WorkflowState


def finalize(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """汇总任务产物并生成导出 ZIP。"""
    render_variant = str(state.get("render_variant") or "final")
    logs = [*state.get("logs", []), f"[finalize] 开始收尾并导出任务产物，render_variant={render_variant}。"]
    task = state["task"]
    task_dir = Path(task.task_dir)
    if render_variant == "preview":
        task = task.model_copy(update={"status": TaskStatus.RUNNING})
        deps.storage.save_task_manifest(task)
        final_dir = task_dir / "final_preview"
        preview_zip_path = export_task_zip(deps.storage, task.task_id, final_dir, suffix="preview_images")
        return {
            "task": task,
            "preview_export_zip_path": str(preview_zip_path),
            "logs": [
                *logs,
                "[finalize] 当前为 preview 模式，任务保持 RUNNING。",
                f"[finalize] Preview ZIP 导出路径={preview_zip_path}。",
            ],
        }

    task = task.model_copy(update={"status": TaskStatus.COMPLETED if state["qc_report"].passed else TaskStatus.REVIEW_REQUIRED})
    deps.storage.save_task_manifest(task)
    final_dir = task_dir / "final"
    final_images_zip_path = export_task_zip(deps.storage, task.task_id, final_dir, suffix="final_images")
    full_task_bundle_zip_path = export_full_task_bundle(deps.storage, task.task_id, task_dir)
    return {
        "task": task,
        "export_zip_path": str(final_images_zip_path),
        "full_task_bundle_zip_path": str(full_task_bundle_zip_path),
        "logs": [
            *logs,
            f"[finalize] 任务状态={task.status.value}。",
            f"[finalize] 最终图片 ZIP 路径={final_images_zip_path}。",
            f"[finalize] 完整任务包 ZIP 路径={full_task_bundle_zip_path}。",
        ],
    }
