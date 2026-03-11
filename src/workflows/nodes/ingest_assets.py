"""素材接收节点。

该节点负责：
- 读取上传素材
- 补齐素材宽高
- 把素材整理为后续节点可消费的结构化资产列表

它不调用任何真实 provider，只处理本地文件信息。
"""

from __future__ import annotations

from PIL import Image

from src.domain.asset import Asset
from src.workflows.state import WorkflowDependencies, WorkflowState


def ingest_assets(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """接收素材并补齐基础尺寸信息。"""
    assets: list[Asset] = []
    for asset in state.get("assets", []):
        try:
            with Image.open(asset.local_path) as image:
                assets.append(asset.model_copy(update={"width": image.width, "height": image.height}))
        except OSError:
            assets.append(asset)
    filenames = ", ".join(asset.filename for asset in assets)
    return {
        "assets": assets,
        "logs": [
            *state.get("logs", []),
            f"[ingest_assets] count={len(assets)}, files={filenames}.",
        ],
    }
