"""详情图收尾节点。"""

from __future__ import annotations

from pathlib import Path

from backend.engine.domain.task import TaskStatus
from backend.engine.workflows.detail_state import DetailWorkflowDependencies, DetailWorkflowState
from backend.services.detail_render_service import DetailRenderService


def detail_finalize(state: DetailWorkflowState, deps: DetailWorkflowDependencies) -> dict:
    """汇总结果、打包 ZIP、写最终 manifest。"""

    task = state["task"]
    qc_summary = state.get("detail_qc_summary")
    if qc_summary is None:
        raise RuntimeError("detail_finalize requires detail_qc_summary")

    status = TaskStatus.COMPLETED if qc_summary.passed and not qc_summary.review_required else TaskStatus.REVIEW_REQUIRED
    step_label = "详情图任务已完成" if status == TaskStatus.COMPLETED else "详情图已生成，待复核"
    updated_task = task.model_copy(
        update={
            "status": status,
            "progress_percent": 100,
            "current_step": "detail_finalize",
            "current_step_label": step_label,
            "error_message": "",
        }
    )
    deps.storage.save_task_manifest(updated_task)

    task_dir = Path(task.task_dir)
    bundle_path = DetailRenderService().build_bundle(task_dir)
    manifest = {
        "task_id": updated_task.task_id,
        "status": updated_task.status.value,
        "plan_path": "plan/detail_plan.json",
        "copy_path": "plan/detail_copy_plan.json",
        "prompt_path": "plan/detail_prompt_plan.json",
        "render_report_path": "generated/detail_render_report.json",
        "qc_report_path": "qc/detail_qc_report.json",
        "bundle_path": str(bundle_path.relative_to(task_dir).as_posix()),
    }
    deps.storage.save_json_artifact(updated_task.task_id, "detail_manifest.json", manifest)
    return {
        "task": updated_task,
        "logs": [
            *state.get("logs", []),
            f"[detail_finalize] task_status={updated_task.status.value}",
            f"[detail_finalize] bundle={bundle_path}",
            "[detail_finalize] saved detail_manifest.json",
        ],
    }
