from __future__ import annotations

from pathlib import Path

from src.core.config import ResolvedModelSelection
from src.domain.asset import Asset, AssetType
from src.domain.generation_result import GenerationResult
from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from src.domain.product_analysis import (
    MaterialGuess,
    PackagingStructure,
    ProductAnalysis,
    VisualConstraints,
    VisualIdentity,
)
from src.domain.task import Task
from src.services.assets.reference_selector import select_reference_bundle
from src.services.storage.local_storage import LocalStorageService
from src.workflows.nodes.analyze_product import analyze_product
from src.workflows.nodes.render_images import render_images
from src.workflows.state import WorkflowDependencies


class FakeVisionProvider:
    def __init__(self) -> None:
        self.asset_ids: list[str] = []

    def generate_structured_from_assets(self, prompt: str, response_model, *, assets, system_prompt=None):
        self.asset_ids = [asset.asset_id for asset in assets]
        return response_model(
            category="tea",
            subcategory="oolong",
            product_type="tea can",
            product_form="packaged_tea",
            packaging_structure=PackagingStructure(
                primary_container="round_metal_can",
                has_outer_box="no",
                has_visible_lid="yes",
                container_count="1",
            ),
            visual_identity=VisualIdentity(
                dominant_colors=["green", "gold"],
                label_position="front_center",
                label_ratio="medium",
                style_impression=["premium"],
                must_preserve=["package body", "label position"],
            ),
            material_guess=MaterialGuess(container_material="metal", label_material="paper"),
            visual_constraints=VisualConstraints(
                recommended_style_direction=["premium"],
                avoid=["deformed package"],
            ),
            source_asset_ids=self.asset_ids,
        )


class FakeImageProvider:
    def __init__(self) -> None:
        self.reference_asset_ids: list[str] = []

    def generate_images(self, plan, *, output_dir, reference_assets=None):
        self.reference_asset_ids = [asset.asset_id for asset in (reference_assets or [])]
        output_dir.mkdir(parents=True, exist_ok=True)
        return GenerationResult.model_validate({"images": []})


class DummyRenderer:
    pass


class DummyOCRService:
    pass


def test_reference_selector_picks_main_before_detail_and_other() -> None:
    assets = [
        Asset(asset_id="asset-detail", filename="label_detail.png", local_path="label_detail.png", asset_type=AssetType.DETAIL),
        Asset(asset_id="asset-main", filename="hero_front_packshot.png", local_path="hero_front_packshot.png", asset_type=AssetType.PRODUCT),
        Asset(asset_id="asset-other", filename="scene_other.png", local_path="scene_other.png", asset_type=AssetType.OTHER),
    ]

    selection = select_reference_bundle(assets, max_images=2)

    assert selection.selected_main_asset_id == "asset-main"
    assert selection.selected_detail_asset_id == "asset-detail"
<<<<<<< HEAD
    assert selection.selected_asset_ids == ["asset-main", "asset-detail"]


=======
    assert selection.asset_completeness_mode == "packshot_plus_detail"
    assert selection.selected_asset_ids == ["asset-main", "asset-detail"]


def test_reference_selector_marks_packshot_only_when_detail_asset_missing() -> None:
    assets = [
        Asset(asset_id="asset-main", filename="hero_front_packshot.png", local_path="hero_front_packshot.png", asset_type=AssetType.PRODUCT),
        Asset(asset_id="asset-other", filename="scene_other.png", local_path="scene_other.png", asset_type=AssetType.OTHER),
    ]

    selection = select_reference_bundle(assets, max_images=2)

    assert selection.selected_main_asset_id == "asset-main"
    assert selection.selected_detail_asset_id is None
    assert selection.asset_completeness_mode == "packshot_only"


>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
def test_analyze_and_render_share_consistent_selection_strategy(tmp_path: Path) -> None:
    task = Task(
        task_id="task-reference-consistency",
        brand_name="品牌A",
        product_name="产品A",
        platform="taobao",
        output_size="1440x1440",
        shot_count=1,
        copy_tone="专业自然",
        task_dir=str(tmp_path / "task-reference-consistency"),
    )
    assets = [
        Asset(asset_id="asset-main", filename="hero_front_packshot.png", local_path=str(tmp_path / "hero_front_packshot.png"), asset_type=AssetType.PRODUCT),
        Asset(asset_id="asset-detail", filename="label_detail.png", local_path=str(tmp_path / "label_detail.png"), asset_type=AssetType.DETAIL),
        Asset(asset_id="asset-other", filename="scene_other.png", local_path=str(tmp_path / "scene_other.png"), asset_type=AssetType.OTHER),
    ]
    vision_provider = FakeVisionProvider()
    image_provider = FakeImageProvider()
    deps = WorkflowDependencies(
        storage=LocalStorageService(),
        planning_provider=object(),
        vision_analysis_provider=vision_provider,
        image_generation_provider=image_provider,
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(),
        text_provider_mode="mock",
        vision_provider_mode="real",
        image_provider_mode="mock",
        planning_model_selection=ResolvedModelSelection("planning", "mock", "mock", "mock", "test"),
        vision_model_selection=ResolvedModelSelection("vision", "mock", "mock", "mock", "test"),
        image_model_selection=ResolvedModelSelection("image", "mock", "mock", "mock", "test"),
    )
    analyze_state = {
        "task": task,
        "assets": assets,
        "logs": [],
        "analyze_max_reference_images": 2,
    }
    analyze_result = analyze_product(analyze_state, deps)

    render_state = {
        "task": task,
        "assets": assets,
        "logs": [],
        "render_mode": "final",
        "image_prompt_plan": ImagePromptPlan(
            prompts=[
                ImagePrompt(shot_id="shot-01", shot_type="hero", prompt="demo", output_size="1440x1440"),
            ]
        ),
    }
    render_result = render_images(render_state, deps)

    assert analyze_result["analyze_selected_main_asset_id"] == "asset-main"
    assert analyze_result["analyze_selected_detail_asset_id"] == "asset-detail"
<<<<<<< HEAD
=======
    assert analyze_result["analyze_asset_completeness_mode"] == "packshot_plus_detail"
    assert analyze_result["product_analysis"].asset_completeness_mode == "packshot_plus_detail"
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    assert analyze_result["analyze_reference_asset_ids"] == ["asset-main", "asset-detail"]
    assert render_result["render_selected_main_asset_id"] == "asset-main"
    assert render_result["render_selected_detail_asset_id"] == "asset-detail"
    assert render_result["render_reference_asset_ids"] == ["asset-main", "asset-detail"]
