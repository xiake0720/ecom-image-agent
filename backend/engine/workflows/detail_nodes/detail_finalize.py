"""详情图收尾节点。"""

from __future__ import annotations

from pathlib import Path

from backend.engine.domain.task import TaskStatus
from backend.engine.workflows.detail_state import DetailWorkflowDependencies, DetailWorkflowState
from backend.services.detail_render_service import DetailRenderService


def detail_finalize(state: DetailWorkflowState, deps: DetailWorkflowDependencies) -> dict:
    """汇总结、打包 ZIP、写最终 manifest。"""

    task = state["task"]
    qc_summary = state.get("detail_qc_summary")
    render_results = state.get("detail_render_results", [])
    if qc_summary is None:
        raise RuntimeError("detail_finalize requires detail_qc_summary")

    success_count = sum(1 for item in render_results if item.status == "completed")
    if success_count == 0:
        status = TaskStatus.FAILED
        step_label = "详情图任务失败"
        error_message = "本次任务没有成功生成任何详情图，请查看 review/retry_decisions.json。"
    elif qc_summary.passed and not qc_summary.review_required:
        status = TaskStatus.COMPLETED
        step_label = "详情图任务已完成"
        error_message = ""
    else:
        status = TaskStatus.REVIEW_REQUIRED
        step_label = "详情图已生成，待复核"
        error_message = ""

    updated_task = task.model_copy(
        update={
            "status": status,
            "progress_percent": 100,
            "current_step": "detail_finalize",
            "current_step_label": step_label,
            "error_message": error_message,
        }
    )
    deps.storage.save_task_manifest(updated_task)

    task_dir = Path(task.task_dir)
    bundle_path = DetailRenderService().build_bundle(task_dir)
    manifest = {
        "task_id": updated_task.task_id,
        "status": updated_task.status.value,
        "preflight_report_path": "inputs/preflight_report.json",
        "director_brief_path": "plan/director_brief.json",
        "plan_path": "plan/detail_plan.json",
        "copy_path": "plan/detail_copy_plan.json",
        "prompt_path": "plan/detail_prompt_plan.json",
        "render_report_path": "generated/detail_render_report.json",
        "visual_review_path": "review/visual_review.json",
        "retry_decisions_path": "review/retry_decisions.json",
        "qc_report_path": "qc/detail_qc_report.json",
        "bundle_path": str(bundle_path.relative_to(task_dir).as_posix()),
        "completed_page_count": success_count,
        "planned_page_count": len(render_results),
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
