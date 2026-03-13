from __future__ import annotations

from pathlib import Path

from src.core.config import ResolvedModelSelection
from src.core.paths import get_task_dir
from src.domain.asset import Asset, AssetType
from src.domain.product_analysis import (
    MaterialGuess,
    PackagingStructure,
    ProductAnalysis,
    VisualConstraints,
    VisualIdentity,
)
from src.domain.task import Task
from src.services.storage.local_storage import LocalStorageService
from src.workflows.nodes.analyze_product import analyze_product
from src.workflows.state import WorkflowDependencies


class FakeVisionProvider:
    def __init__(self) -> None:
        self.called = False
        self.asset_ids: list[str] = []

    def generate_structured_from_assets(self, prompt: str, response_model, *, assets, system_prompt=None):
        self.called = True
        self.asset_ids = [asset.asset_id for asset in assets]
        assert "SKU 级视觉分析" in prompt
        return response_model(
            category="tea",
            subcategory="单丛茶",
            product_type="round tea can",
            product_form="packaged_tea",
            packaging_structure=PackagingStructure(
                primary_container="round_metal_can",
                has_outer_box="no",
                has_visible_lid="yes",
                container_count="1",
            ),
            visual_identity=VisualIdentity(
                dominant_colors=["墨绿", "金色"],
                label_position="front_center",
                label_ratio="medium",
                style_impression=["东方雅致", "高级"],
                must_preserve=["圆罐轮廓", "正面标签区", "金色主标题区域"],
            ),
            material_guess=MaterialGuess(container_material="metal", label_material="paper"),
            visual_constraints=VisualConstraints(
                recommended_style_direction=["保留东方雅致气质", "延续深绿与金色关系"],
                avoid=["不要改成透明袋装", "不要重设计标签版式"],
            ),
            visual_style_keywords=["东方雅致", "深绿金色", "金属茶罐"],
            recommended_focuses=["包装主体", "正面标签区", "盖子结构"],
            source_asset_ids=self.asset_ids,
        )


class DummyRenderer:
    pass


class DummyOCRService:
    pass


def test_analyze_product_real_mode_uses_selected_reference_assets_only(tmp_path: Path) -> None:
    task_dir = tmp_path / "task-001"
    task_dir.mkdir(parents=True, exist_ok=True)
    vision_provider = FakeVisionProvider()
    deps = WorkflowDependencies(
        storage=LocalStorageService(),
        planning_provider=object(),
        vision_analysis_provider=vision_provider,
        image_generation_provider=object(),
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(),
        text_provider_mode="real",
        vision_provider_mode="real",
        image_provider_mode="mock",
        planning_provider_name="FakePlanningProvider",
        vision_provider_name="FakeVisionProvider",
        image_provider_name="FakeImageProvider",
        planning_model_selection=ResolvedModelSelection("planning", "qwen", "qwen/qwen3.5-122b-a10b", "Qwen3.5", "test"),
        vision_model_selection=ResolvedModelSelection("vision", "qwen", "qwen/qwen3.5-122b-a10b", "Qwen3.5", "test"),
    )
    task = Task(
        task_id="task-001",
        brand_name="品牌A",
        product_name="产品A",
        platform="taobao",
        output_size="1440x1440",
        shot_count=1,
        copy_tone="专业自然",
        task_dir=str(task_dir),
    )
    state = {
        "task": task,
        "assets": [
            Asset(asset_id="asset-01", filename="main.png", local_path=str(Path("main.png")), asset_type=AssetType.PRODUCT),
            Asset(asset_id="asset-02", filename="detail.png", local_path=str(Path("detail.png")), asset_type=AssetType.DETAIL),
            Asset(asset_id="asset-03", filename="other.png", local_path=str(Path("other.png")), asset_type=AssetType.OTHER),
        ],
        "logs": [],
        "analyze_max_reference_images": 2,
    }

    result = analyze_product(state, deps)

    assert vision_provider.called is True
    assert vision_provider.asset_ids == ["asset-01", "asset-02"]
    assert result["product_analysis"].source_asset_ids == ["asset-01", "asset-02"]
    assert any("asset-01" in log and "asset-02" in log for log in result["logs"])
    assert (get_task_dir(task.task_id) / "product_analysis.json").exists()
