"""详情图输入接收节点。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from backend.engine.workflows.detail_state import DetailWorkflowDependencies, DetailWorkflowState


def detail_ingest_assets(state: DetailWorkflowState, deps: DetailWorkflowDependencies) -> dict:
    """读取详情图输入，写入 request_payload 与 asset_manifest。"""

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

    deps.storage.save_json_artifact(task.task_id, "inputs/request_payload.json", payload)
    deps.storage.save_json_artifact(task.task_id, "inputs/asset_manifest.json", normalized_assets)
    return {
        "detail_assets": normalized_assets,
        "logs": [
            *state.get("logs", []),
            f"[detail_ingest_assets] asset_count={len(normalized_assets)} roles={[asset.role for asset in normalized_assets]}",
            "[detail_ingest_assets] saved inputs/request_payload.json",
            "[detail_ingest_assets] saved inputs/asset_manifest.json",
        ],
    }


def _read_image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        with Image.open(path) as image:
            return image.size
    except OSError:
        return None, None
