from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from src.domain.asset import Asset
from src.domain.copy_plan import CopyPlan
from src.domain.generation_result import GenerationResult
from src.domain.image_prompt_plan import ImagePromptPlan
from src.domain.layout_plan import LayoutPlan
from src.domain.product_analysis import ProductAnalysis
from src.domain.qc_report import QCReport
from src.domain.shot_plan import ShotPlan
from src.domain.task import Task


class WorkflowState(TypedDict, total=False):
    task: Task
    assets: list[Asset]
    logs: list[str]
    product_analysis: ProductAnalysis
    shot_plan: ShotPlan
    copy_plan: CopyPlan
    layout_plan: LayoutPlan
    image_prompt_plan: ImagePromptPlan
    generation_result: GenerationResult
    qc_report: QCReport
    export_zip_path: str


@dataclass
class WorkflowDependencies:
    storage: object
    text_provider: object
    image_provider: object
    text_renderer: object
    ocr_service: object
    text_provider_mode: str
    image_provider_mode: str
