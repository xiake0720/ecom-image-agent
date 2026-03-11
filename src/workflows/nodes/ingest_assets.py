from __future__ import annotations

from PIL import Image

from src.domain.asset import Asset
from src.workflows.state import WorkflowDependencies, WorkflowState


def ingest_assets(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    assets: list[Asset] = []
    for asset in state.get("assets", []):
        try:
            with Image.open(asset.local_path) as image:
                assets.append(asset.model_copy(update={"width": image.width, "height": image.height}))
        except OSError:
            assets.append(asset)
    return {"assets": assets, "logs": [*state.get("logs", []), f"Ingested {len(assets)} assets."]}

