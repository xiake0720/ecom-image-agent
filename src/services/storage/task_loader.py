<<<<<<< HEAD
"""任务目录回放加载器。

文件位置：
- `src/services/storage/task_loader.py`

核心职责：
- 从任务目录恢复可继续运行或可展示的 workflow 上下文
- 同时兼容 v1 和 v2 两套落盘产物
"""

=======
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
from __future__ import annotations

import json
from pathlib import Path

from src.core.paths import get_task_dir
from src.domain.asset import Asset, AssetType
from src.domain.copy_plan import CopyPlan
<<<<<<< HEAD
from src.domain.director_output import DirectorOutput
from src.domain.image_prompt_plan import ImagePromptPlan
from src.domain.layout_plan import LayoutPlan
from src.domain.product_analysis import ProductAnalysis
from src.domain.prompt_plan_v2 import PromptPlanV2
=======
from src.domain.image_prompt_plan import ImagePromptPlan
from src.domain.layout_plan import LayoutPlan
from src.domain.product_analysis import ProductAnalysis
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
from src.domain.qc_report import QCReport
from src.domain.shot_prompt_specs import ShotPromptSpecPlan
from src.domain.shot_plan import ShotPlan
from src.domain.style_architecture import StyleArchitecture
from src.domain.task import Task


def load_task_context(task_id: str) -> dict[str, object]:
<<<<<<< HEAD
    """从任务目录恢复可继续运行的 workflow 上下文。"""
    task_dir = get_task_dir(task_id)
    task = Task.model_validate_json((task_dir / "task.json").read_text(encoding="utf-8"))
    workflow_version = str(task.workflow_version or "v1").strip().lower()
    state: dict[str, object] = {
        "task": task,
        "workflow_version": workflow_version,
        "enable_overlay_fallback": bool(task.enable_overlay_fallback),
        "assets": _load_assets(task_dir),
    }

    product_analysis = _load_optional_json_model(task_dir / "product_analysis.json", ProductAnalysis)
    if product_analysis is not None:
        state["product_analysis"] = product_analysis
        state["product_lock"] = product_analysis

    style_architecture = _load_optional_json_model(task_dir / "style_architecture.json", StyleArchitecture)
    if style_architecture is not None:
        state["style_architecture"] = style_architecture
    shot_plan = _load_optional_json_model(task_dir / "shot_plan.json", ShotPlan)
    if shot_plan is not None:
        state["shot_plan"] = shot_plan
    copy_plan = _load_optional_json_model(task_dir / "copy_plan.json", CopyPlan)
    if copy_plan is not None:
        state["copy_plan"] = copy_plan
    layout_plan = _load_optional_json_model(task_dir / "layout_plan.json", LayoutPlan)
    if layout_plan is not None:
        state["layout_plan"] = layout_plan
    shot_prompt_specs = _load_optional_json_model(task_dir / "shot_prompt_specs.json", ShotPromptSpecPlan)
    if shot_prompt_specs is not None:
        state["shot_prompt_specs"] = shot_prompt_specs
    image_prompt_plan = _load_optional_json_model(task_dir / "image_prompt_plan.json", ImagePromptPlan)
    if image_prompt_plan is not None:
        state["image_prompt_plan"] = image_prompt_plan
    director_output = _load_optional_json_model(task_dir / "director_output.json", DirectorOutput)
    if director_output is not None:
        state["director_output"] = director_output
    prompt_plan_v2 = _load_optional_json_model(task_dir / "prompt_plan_v2.json", PromptPlanV2)
    if prompt_plan_v2 is not None:
        state["prompt_plan_v2"] = prompt_plan_v2

=======
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
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    qc_preview_path = task_dir / "qc_report_preview.json"
    if qc_preview_path.exists():
        state["preview_qc_report"] = QCReport.model_validate_json(qc_preview_path.read_text(encoding="utf-8"))
    qc_path = task_dir / "qc_report.json"
    if qc_path.exists():
<<<<<<< HEAD
        report = QCReport.model_validate_json(qc_path.read_text(encoding="utf-8"))
        state["qc_report"] = report
        if workflow_version == "v2":
            state["qc_report_v2"] = report

=======
        state["qc_report"] = QCReport.model_validate_json(qc_path.read_text(encoding="utf-8"))
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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


<<<<<<< HEAD
def _load_optional_json_model(path: Path, model_type):
    """按文件存在性恢复结构化模型。"""
    if not path.exists():
        return None
    return model_type.model_validate_json(path.read_text(encoding="utf-8"))


def _load_assets(task_dir: Path) -> list[Asset]:
    """从 inputs 目录恢复上传素材列表。"""
=======
def _load_assets(task_dir: Path) -> list[Asset]:
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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
