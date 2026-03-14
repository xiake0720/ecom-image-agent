from __future__ import annotations

from pathlib import Path

from src.core.config import ResolvedModelSelection
from src.domain.asset import Asset, AssetType
from src.domain.generation_result import GenerationResult
from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from src.domain.task import Task
from src.workflows.nodes.render_images import render_images
from src.workflows.state import WorkflowDependencies


class FakeImageProvider:
    def __init__(self) -> None:
        self.reference_asset_ids: list[str] = []

    def generate_images(self, plan, *, output_dir, reference_assets=None):
        self.reference_asset_ids = [asset.asset_id for asset in (reference_assets or [])]
        output_dir.mkdir(parents=True, exist_ok=True)
        images = []
        for index, prompt in enumerate(plan.prompts, start=1):
            width, height = [int(value) for value in prompt.output_size.split("x", maxsplit=1)]
            path = output_dir / f"{index:02d}_{prompt.shot_id}.png"
            path.write_bytes(b"fake")
            images.append(
                {
                    "shot_id": prompt.shot_id,
                    "image_path": str(path),
                    "preview_path": str(path),
                    "width": width,
                    "height": height,
                    "status": "generated",
                }
            )
        return GenerationResult.model_validate({"images": images})


class DummyRenderer:
    pass


class DummyOCRService:
    pass


def test_render_images_preview_mode_renders_only_preview_subset(tmp_path: Path) -> None:
    task = Task(
        task_id="task-render-preview",
        brand_name="品牌A",
        product_name="产品A",
        platform="taobao",
        output_size="1440x1440",
        shot_count=3,
        copy_tone="专业自然",
        task_dir=str(tmp_path / "task-render-preview"),
    )
    image_provider = FakeImageProvider()
    deps = WorkflowDependencies(
        storage=object(),
        planning_provider=object(),
        vision_analysis_provider=None,
        image_generation_provider=image_provider,
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(),
        text_provider_mode="mock",
        vision_provider_mode="mock",
        image_provider_mode="mock",
        planning_model_selection=ResolvedModelSelection("planning", "mock", "mock", "mock", "test"),
        vision_model_selection=ResolvedModelSelection("vision", "mock", "mock", "mock", "test"),
        image_model_selection=ResolvedModelSelection("image", "mock", "mock", "mock", "test"),
    )
    state = {
        "task": task,
        "assets": [
            Asset(asset_id="asset-01", filename="main.png", local_path=str(tmp_path / "main.png"), asset_type=AssetType.PRODUCT),
            Asset(asset_id="asset-02", filename="detail.png", local_path=str(tmp_path / "detail.png"), asset_type=AssetType.DETAIL),
            Asset(asset_id="asset-03", filename="other.png", local_path=str(tmp_path / "other.png"), asset_type=AssetType.OTHER),
        ],
        "image_prompt_plan": ImagePromptPlan(
            prompts=[
            ImagePrompt(shot_id="shot-01", shot_type="hero", prompt="a", edit_instruction="edit a", keep_subject_rules=["keep pack"], editable_regions=["background"], text_safe_zone="top_right", output_size="1440x1440"),
            ImagePrompt(shot_id="shot-02", shot_type="detail", prompt="b", edit_instruction="edit b", keep_subject_rules=["keep label"], editable_regions=["lighting"], text_safe_zone="top_left", output_size="1440x1440"),
            ImagePrompt(shot_id="shot-03", shot_type="detail", prompt="c", edit_instruction="edit c", keep_subject_rules=["keep structure"], editable_regions=["props"], text_safe_zone="left_center", output_size="1440x1440"),
            ]
        ),
        "logs": [],
        "render_mode": "preview",
    }

    result = render_images(state, deps)

    assert result["render_variant"] == "preview"
    assert result["render_generation_mode"] == "image_edit"
    assert result["render_reference_asset_ids"] == ["asset-01"]
    assert result["render_selected_main_asset_id"] == "asset-01"
    assert result["render_selected_detail_asset_id"] is None
    assert isinstance(result["generation_result"], GenerationResult)
    assert len(result["generation_result"].images) == 2
    assert all(image.width == 1024 and image.height == 1024 for image in result["generation_result"].images)
    assert any("render_mode=preview" in log for log in result["logs"])
    assert any("render_generation_mode=image_edit" in log for log in result["logs"])
    assert any("keep_subject_rules=['keep pack']" in log for log in result["logs"])
    assert any("editable_regions=['background']" in log for log in result["logs"])
    assert any("text_safe_zone=top_right" in log for log in result["logs"])
    assert image_provider.reference_asset_ids == ["asset-01"]
    assert any("selected_main_asset_id=asset-01" in log for log in result["logs"])


def test_render_images_final_mode_renders_all_prompts(tmp_path: Path) -> None:
    task = Task(
        task_id="task-render-final",
        brand_name="品牌A",
        product_name="产品A",
        platform="taobao",
        output_size="1440x1440",
        shot_count=3,
        copy_tone="专业自然",
        task_dir=str(tmp_path / "task-render-final"),
    )
    image_provider = FakeImageProvider()
    deps = WorkflowDependencies(
        storage=object(),
        planning_provider=object(),
        vision_analysis_provider=None,
        image_generation_provider=image_provider,
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(),
        text_provider_mode="mock",
        vision_provider_mode="mock",
        image_provider_mode="mock",
        planning_model_selection=ResolvedModelSelection("planning", "mock", "mock", "mock", "test"),
        vision_model_selection=ResolvedModelSelection("vision", "mock", "mock", "mock", "test"),
        image_model_selection=ResolvedModelSelection("image", "mock", "mock", "mock", "test"),
    )
    state = {
        "task": task,
        "assets": [
            Asset(asset_id="asset-01", filename="main.png", local_path=str(tmp_path / "main.png"), asset_type=AssetType.PRODUCT),
            Asset(asset_id="asset-02", filename="detail.png", local_path=str(tmp_path / "detail.png"), asset_type=AssetType.DETAIL),
        ],
        "image_prompt_plan": ImagePromptPlan(
            prompts=[
            ImagePrompt(shot_id="shot-01", shot_type="hero", prompt="a", edit_instruction="edit a", keep_subject_rules=["keep pack"], editable_regions=["background"], text_safe_zone="top_right", output_size="1440x1440"),
            ImagePrompt(shot_id="shot-02", shot_type="detail", prompt="b", edit_instruction="edit b", keep_subject_rules=["keep label"], editable_regions=["lighting"], text_safe_zone="top_left", output_size="1440x1440"),
            ImagePrompt(shot_id="shot-03", shot_type="detail", prompt="c", edit_instruction="edit c", keep_subject_rules=["keep structure"], editable_regions=["props"], text_safe_zone="left_center", output_size="1440x1440"),
            ]
        ),
        "logs": [],
        "render_mode": "final",
    }

    result = render_images(state, deps)

    assert result["render_variant"] == "final"
    assert result["render_generation_mode"] == "image_edit"
    assert result["render_reference_asset_ids"] == ["asset-01", "asset-02"]
    assert result["render_selected_main_asset_id"] == "asset-01"
    assert result["render_selected_detail_asset_id"] == "asset-02"
    assert len(result["generation_result"].images) == 3
    assert all(image.width == 1440 and image.height == 1440 for image in result["generation_result"].images)
    assert image_provider.reference_asset_ids == ["asset-01", "asset-02"]
