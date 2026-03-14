from __future__ import annotations

import json
from pathlib import Path

from src.core.paths import get_task_dir
from src.domain.asset import Asset, AssetType
from src.domain.copy_plan import CopyPlan
from src.domain.image_prompt_plan import ImagePromptPlan
from src.domain.layout_plan import LayoutPlan
from src.domain.product_analysis import ProductAnalysis
from src.domain.qc_report import QCReport
from src.domain.shot_prompt_specs import ShotPromptSpecPlan
from src.domain.shot_plan import ShotPlan
from src.domain.style_architecture import StyleArchitecture
from src.domain.task import Task


def load_task_context(task_id: str) -> dict[str, object]:
    """从任务目录恢复可继续运行的 workflow 上下文。

    关键点：
    - 这里恢复的不只是落盘 JSON，本质上是在把这些 JSON 重新接回 workflow state
    - `product_lock` 当前与 `product_analysis` 使用同一份结构化对象，便于后续节点统一读取
    """
    task_dir = get_task_dir(task_id)
    product_analysis = ProductAnalysis.model_validate_json((task_dir / "product_analysis.json").read_text(encoding="utf-8"))
    task = Task.model_validate_json((task_dir / "task.json").read_text(encoding="utf-8"))
    state: dict[str, object] = {
        "task": task,
        "assets": _load_assets(task_dir),
        "product_analysis": product_analysis,
        "product_lock": product_analysis,
        "style_architecture": StyleArchitecture.model_validate_json((task_dir / "style_architecture.json").read_text(encoding="utf-8")),
        "shot_plan": ShotPlan.model_validate_json((task_dir / "shot_plan.json").read_text(encoding="utf-8")),
        "copy_plan": CopyPlan.model_validate_json((task_dir / "copy_plan.json").read_text(encoding="utf-8")),
        "layout_plan": LayoutPlan.model_validate_json((task_dir / "layout_plan.json").read_text(encoding="utf-8")),
        "shot_prompt_specs": ShotPromptSpecPlan.model_validate_json((task_dir / "shot_prompt_specs.json").read_text(encoding="utf-8")),
        "image_prompt_plan": ImagePromptPlan.model_validate_json((task_dir / "image_prompt_plan.json").read_text(encoding="utf-8")),
    }
    qc_preview_path = task_dir / "qc_report_preview.json"
    if qc_preview_path.exists():
        state["preview_qc_report"] = QCReport.model_validate_json(qc_preview_path.read_text(encoding="utf-8"))
    qc_path = task_dir / "qc_report.json"
    if qc_path.exists():
        state["qc_report"] = QCReport.model_validate_json(qc_path.read_text(encoding="utf-8"))
    for filename in ("final_text_regions.json", "preview_text_regions.json"):
        text_regions_path = task_dir / filename
        if not text_regions_path.exists():
            continue
        payload = json.loads(text_regions_path.read_text(encoding="utf-8"))
        state["text_render_reports"] = {
            str(item.get("shot_id")): item
            for item in payload.get("shots", [])
            if item.get("shot_id")
        }
        break
    return state


def _load_assets(task_dir: Path) -> list[Asset]:
    inputs_dir = task_dir / "inputs"
    assets: list[Asset] = []
    for index, path in enumerate(sorted(inputs_dir.iterdir()), start=1):
        if not path.is_file():
            continue
        assets.append(
            Asset(
                asset_id=f"asset-{index:02d}",
                filename=path.name,
                local_path=str(path),
                asset_type=AssetType.PRODUCT if index == 1 else AssetType.DETAIL,
            )
        )
    return assets
