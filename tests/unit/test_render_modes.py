from __future__ import annotations

from pathlib import Path

from src.domain.asset import Asset, AssetType
from src.core.config import ResolvedModelSelection
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
                ImagePrompt(shot_id="shot-01", shot_type="hero", prompt="a", output_size="1440x1440"),
                ImagePrompt(shot_id="shot-02", shot_type="detail", prompt="b", output_size="1440x1440"),
                ImagePrompt(shot_id="shot-03", shot_type="detail", prompt="c", output_size="1440x1440"),
            ]
        ),
        "logs": [],
        "render_mode": "preview",
        "render_max_reference_images": 2,
    }

    result = render_images(state, deps)

    assert result["render_variant"] == "preview"
    assert isinstance(result["generation_result"], GenerationResult)
    assert len(result["generation_result"].images) == 2
    assert all(image.width == 1024 and image.height == 1024 for image in result["generation_result"].images)
    assert any("render_mode=preview" in log for log in result["logs"])
    assert image_provider.reference_asset_ids == ["asset-01", "asset-02"]
    assert any("asset-01" in log and "asset-02" in log for log in result["logs"])


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
                ImagePrompt(shot_id="shot-01", shot_type="hero", prompt="a", output_size="1440x1440"),
                ImagePrompt(shot_id="shot-02", shot_type="detail", prompt="b", output_size="1440x1440"),
                ImagePrompt(shot_id="shot-03", shot_type="detail", prompt="c", output_size="1440x1440"),
            ]
        ),
        "logs": [],
        "render_mode": "final",
        "render_max_reference_images": 1,
    }

    result = render_images(state, deps)

    assert result["render_variant"] == "final"
    assert len(result["generation_result"].images) == 3
    assert all(image.width == 1440 and image.height == 1440 for image in result["generation_result"].images)
    assert image_provider.reference_asset_ids == ["asset-01"]
