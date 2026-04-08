"""详情图输入接收节点。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from backend.core.config import get_settings
from backend.engine.workflows.detail_state import DetailWorkflowDependencies, DetailWorkflowState
from backend.services.detail_planner_service import DetailPlannerService


def detail_ingest_assets(state: DetailWorkflowState, deps: DetailWorkflowDependencies) -> dict:
    """读取详情图输入，写入 request_payload、asset_manifest 和 preflight 报告。"""

    task = state["task"]
    payload = state["detail_payload"]
    normalized_assets = []
    for asset in state.get("detail_assets", []):
        asset_path = Path(task.task_dir) / asset.relative_path
        if not asset_path.exists():
            raise RuntimeError(f"素材不存在：{asset.relative_path}")
        width, height = _read_image_size(asset_path)
        normalized_assets.append(asset.model_copy(update={"width": width, "height": height}))

    if not normalized_assets:
        raise RuntimeError("详情图至少需要一张素材或主图结果")

    planner = DetailPlannerService(template_root=get_settings().template_root)
    preflight_report = planner.build_preflight_report(payload, normalized_assets)
    if not preflight_report.passed:
        raise RuntimeError("详情图输入缺少 packaging 或 main_result，无法建立稳定主锚点")

    deps.storage.save_json_artifact(task.task_id, "inputs/request_payload.json", payload)
    deps.storage.save_json_artifact(task.task_id, "inputs/asset_manifest.json", normalized_assets)
    deps.storage.save_json_artifact(task.task_id, "inputs/preflight_report.json", preflight_report)
    return {
        "detail_assets": normalized_assets,
        "detail_preflight_report": preflight_report,
        "logs": [
            *state.get("logs", []),
            f"[detail_ingest_assets] asset_count={len(normalized_assets)} roles={[asset.role for asset in normalized_assets]}",
            "[detail_ingest_assets] saved inputs/request_payload.json",
            "[detail_ingest_assets] saved inputs/asset_manifest.json",
            "[detail_ingest_assets] saved inputs/preflight_report.json",
        ],
    }


def _read_image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        with Image.open(path) as image:
            return image.size
    except OSError:
        return None, None
