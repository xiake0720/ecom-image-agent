"""收尾与导出节点。

文件位置：
- `src/workflows/nodes/finalize.py`

职责：
- 根据 QC 结果更新任务状态
- 导出最终图片 ZIP 与完整任务包 ZIP
- 回写最终任务清单
"""

from __future__ import annotations

from pathlib import Path

from src.domain.task import TaskStatus
from src.services.storage.zip_export import export_full_task_bundle, export_task_zip
from src.workflows.state import CORE_CONTRACT_ARTIFACTS, WorkflowDependencies, WorkflowState


def finalize(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """汇总任务状态并导出结果。"""

    task = state["task"]
    qc_report = state.get("qc_report_v2") or state.get("qc_report")
    if qc_report is None:
        raise RuntimeError("finalize requires qc_report_v2")

    task_dir = Path(task.task_dir)
    final_dir = task_dir / "final"
    task_status = TaskStatus.COMPLETED if qc_report.passed and not qc_report.review_required else TaskStatus.REVIEW_REQUIRED
    updated_task = task.model_copy(update={"status": task_status, "progress_percent": 100, "current_step": "finalize"})
    deps.storage.save_task_manifest(updated_task)

    final_images_zip_path = export_task_zip(deps.storage, task.task_id, final_dir, suffix="final_images")
    full_task_bundle_zip_path = export_full_task_bundle(deps.storage, task.task_id, task_dir)
    artifact_paths = {name: task_dir / path for name, path in CORE_CONTRACT_ARTIFACTS.items()}
    return {
        "task": updated_task,
        "export_zip_path": str(final_images_zip_path),
        "full_task_bundle_zip_path": str(full_task_bundle_zip_path),
        "logs": [
            *state.get("logs", []),
            f"[finalize] task_status={updated_task.status.value}",
            f"[finalize] final_images_zip={final_images_zip_path}",
            f"[finalize] full_task_bundle_zip={full_task_bundle_zip_path}",
        ],
        "artifact_paths": artifact_paths,
    }
