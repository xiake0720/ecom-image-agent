from __future__ import annotations

from pathlib import Path

from src.domain.task import TaskStatus
from src.services.storage.zip_export import export_task_zip
from src.workflows.state import WorkflowDependencies, WorkflowState


def finalize(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    logs = [*state.get("logs", []), "[finalize] start export task artifacts."]
    task = state["task"].model_copy(
        update={
            "status": TaskStatus.COMPLETED if state["qc_report"].passed else TaskStatus.REVIEW_REQUIRED
        }
    )
    deps.storage.save_task_manifest(task)
    final_dir = Path(task.task_dir) / "final"
    zip_path = export_task_zip(deps.storage, task.task_id, final_dir)
    return {
        "task": task,
        "export_zip_path": str(zip_path),
        "logs": [
            *logs,
            f"[finalize] task_status={task.status.value}.",
            f"[finalize] zip_path={zip_path}.",
        ],
    }
