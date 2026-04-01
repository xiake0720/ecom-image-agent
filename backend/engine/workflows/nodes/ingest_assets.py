"""素材接收节点。

职责：
- 校验上传素材是否存在
- 回填宽高信息
- 输出最小素材摘要，供后续主链复用
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from backend.engine.domain.asset import Asset
from backend.engine.workflows.state import WorkflowDependencies, WorkflowState


def ingest_assets(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """接收素材并补齐基础尺寸信息。"""

    assets: list[Asset] = []
    uploaded_files: list[str] = []
    for asset in state.get("assets", []):
        asset_path = Path(asset.local_path)
        if not asset_path.exists():
            raise RuntimeError(f"missing asset: {asset.filename}")
        try:
            with Image.open(asset_path) as image:
                assets.append(asset.model_copy(update={"width": image.width, "height": image.height}))
        except OSError:
            assets.append(asset)
        uploaded_files.append(asset.filename)

    if not assets:
        raise RuntimeError("no assets uploaded")

    return {
        "assets": assets,
        "uploaded_files": uploaded_files,
        "logs": [
            *state.get("logs", []),
            f"[ingest_assets] asset_count={len(assets)} files={uploaded_files}",
        ],
    }
