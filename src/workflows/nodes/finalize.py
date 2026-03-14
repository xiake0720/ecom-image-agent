"""收尾与导出节点。

文件位置：
- `src/workflows/nodes/finalize.py`

核心职责：
- 在工作流末尾汇总任务状态并生成导出 ZIP。
- 把主链路核心 contract 文件的存在性和固定路径写入 state，便于 UI 与调试读取。
- 输出最终调试日志，帮助定位本次任务究竟接通了哪些结构化产物。

节点前后关系：
- 上游节点：`run_qc`
- 下游节点：workflow 结束
"""

from __future__ import annotations

from pathlib import Path

from src.domain.task import TaskStatus
from src.services.storage.zip_export import export_full_task_bundle, export_task_zip
from src.workflows.state import CORE_CONTRACT_ARTIFACTS, WorkflowDependencies, WorkflowState, build_connected_contract_summary


def finalize(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """汇总任务产物并生成导出 ZIP。

    参数：
    - state：当前 workflow state，要求已经包含 QC 结果和任务目录信息。
    - deps：依赖容器，主要使用本地存储服务和 ZIP 导出服务。

    返回：
    - dict：写回任务状态、导出 ZIP 路径、核心 contract 的 artifact 路径以及调试日志。

    关键副作用：
    - 回写 `task.json` 状态。
    - 生成预览 ZIP、成品 ZIP 或完整任务包 ZIP。
    - 记录 `product_analysis / style_architecture / shot_plan / shot_prompt_specs` 的路径与存在性。
    """
    render_variant = str(state.get("render_variant") or "final")
    logs = [*state.get("logs", []), f"[finalize] start render_variant={render_variant}"]
    task = state["task"]
    task_dir = Path(task.task_dir)

    contract_summary = build_connected_contract_summary(state)
    artifact_presence = _build_contract_artifact_presence(task_dir)
    artifact_paths = _build_contract_artifact_paths(task_dir)
    logs.extend(
        [
            f"[finalize] connected_contract_files={contract_summary['connected_contract_files']}",
            f"[finalize] style_architecture_connected={str(contract_summary['style_architecture_connected']).lower()}",
            f"[finalize] shot_prompt_specs_available_for_render={str(contract_summary['shot_prompt_specs_available_for_render']).lower()}",
            f"[finalize] contract_artifact_presence={artifact_presence}",
        ]
    )

    # 预览模式只导出当前预览结果，任务保持 RUNNING，方便用户继续进入 final。
    if render_variant == "preview":
        task = task.model_copy(update={"status": TaskStatus.RUNNING})
        deps.storage.save_task_manifest(task)
        final_dir = task_dir / "final_preview"
        preview_zip_path = export_task_zip(deps.storage, task.task_id, final_dir, suffix="preview_images")
        return {
            "task": task,
            "preview_export_zip_path": str(preview_zip_path),
            "artifact_paths": artifact_paths,
            "logs": [
                *logs,
                "[finalize] current mode is preview, task keeps RUNNING",
                f"[finalize] preview zip path={preview_zip_path}",
            ],
        }

    # final 模式会根据 QC 结果决定任务状态，并导出成品与完整任务包。
    task = task.model_copy(update={"status": TaskStatus.COMPLETED if state["qc_report"].passed else TaskStatus.REVIEW_REQUIRED})
    deps.storage.save_task_manifest(task)
    final_dir = task_dir / "final"
    final_images_zip_path = export_task_zip(deps.storage, task.task_id, final_dir, suffix="final_images")
    full_task_bundle_zip_path = export_full_task_bundle(deps.storage, task.task_id, task_dir)
    return {
        "task": task,
        "export_zip_path": str(final_images_zip_path),
        "full_task_bundle_zip_path": str(full_task_bundle_zip_path),
        "artifact_paths": artifact_paths,
        "logs": [
            *logs,
            f"[finalize] task_status={task.status.value}",
            f"[finalize] final_images_zip={final_images_zip_path}",
            f"[finalize] full_task_bundle_zip={full_task_bundle_zip_path}",
        ],
    }


def _build_contract_artifact_presence(task_dir: Path) -> dict[str, bool]:
    """检查主链路核心 contract 文件是否已稳定落盘。"""
    return {
        filename: (task_dir / filename).exists()
        for filename in CORE_CONTRACT_ARTIFACTS.values()
    }


def _build_contract_artifact_paths(task_dir: Path) -> dict[str, Path]:
    """返回核心 contract 文件在任务目录中的固定路径。"""
    return {
        contract_name: task_dir / filename
        for contract_name, filename in CORE_CONTRACT_ARTIFACTS.items()
    }
