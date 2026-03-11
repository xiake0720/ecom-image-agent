"""收尾与导出节点。

该节点位于 workflow 末尾，负责：
- 根据质检结果更新任务状态
- 回写 `task.json`
- 打包最终图片目录为 ZIP
- 为 UI 下载链路提供导出路径
"""

from __future__ import annotations

from pathlib import Path

from src.domain.task import TaskStatus
from src.services.storage.zip_export import export_task_zip
from src.workflows.state import WorkflowDependencies, WorkflowState


def finalize(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """汇总任务产物并生成导出 ZIP。"""
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
