from __future__ import annotations

from src.domain.asset import Asset
from src.domain.copy_plan import CopyItem, CopyPlan
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from src.domain.layout_plan import LayoutBlock, LayoutItem, LayoutPlan
from src.domain.product_analysis import (
    MaterialGuess,
    PackagingStructure,
    ProductAnalysis,
    VisualConstraints,
    VisualIdentity,
)
from src.domain.qc_report import QCCheck, QCReport
from src.domain.shot_plan import ShotPlan, ShotSpec
from src.domain.task import Task


def test_domain_models_round_trip() -> None:
    task = Task(
        task_id="task-001",
        brand_name="醒千峰",
        product_name="凤凰单丛",
        platform="taobao",
        output_size="1440x1440",
        shot_count=3,
        copy_tone="专业自然",
        task_dir="outputs/tasks/task-001",
    )
    asset = Asset(asset_id="asset-01", filename="demo.png", local_path="demo.png")
    analysis = ProductAnalysis(
        analysis_scope="sku_level",
        intended_for="all_future_shots",
        category="tea",
        subcategory="绿茶",
        product_type="绿茶",
        product_form="packaged_tea",
        packaging_structure=PackagingStructure(
            primary_container="box",
            has_outer_box="yes",
            has_visible_lid="no",
            container_count="1",
        ),
        visual_identity=VisualIdentity(
            dominant_colors=["绿色", "白色"],
            label_position="front_center",
            label_ratio="medium",
            style_impression=["简洁", "自然"],
            must_preserve=["正面标签区"],
        ),
        material_guess=MaterialGuess(
            container_material="paper_box",
            label_material="matte_paper",
        ),
        visual_constraints=VisualConstraints(
            recommended_style_direction=["延续原始配色"],
            avoid=["不要虚构透明罐体"],
        ),
    )
    shot_plan = ShotPlan(
        shots=[
            ShotSpec(
                shot_id="shot-01",
                title="主图",
                purpose="展示",
                composition_hint="主体居中",
                copy_goal="品牌",
                shot_type="hero",
                goal="突出品牌主视觉",
                focus="包装主体",
                scene_direction="高级棚拍主图场景",
                composition_direction="主体居中，右侧留白",
            )
        ]
    )
    copy_plan = CopyPlan(items=[CopyItem(shot_id="shot-01", title="标题", subtitle="副标题", bullets=["卖点1"])])
    layout_plan = LayoutPlan(
        items=[LayoutItem(shot_id="shot-01", canvas_width=1440, canvas_height=1440, blocks=[LayoutBlock(kind="title", x=0, y=0, width=200, height=80)])]
    )
    prompt_plan = ImagePromptPlan(
        prompts=[
            ImagePrompt(
                shot_id="shot-01",
                shot_type="hero",
                prompt="tea shot",
                negative_prompt=["garbled text", "deformed product"],
                output_size="1440x1440",
                preserve_rules=["保持包装主体"],
                text_space_hint="top_right_clean_space",
                composition_notes=["主体居中"],
                style_notes=["高端商业摄影"],
            )
        ]
    )
    result = GenerationResult(images=[GeneratedImage(shot_id="shot-01", image_path="a.png", preview_path="b.png", width=1440, height=1440)])
    qc_report = QCReport(passed=True, checks=[QCCheck(shot_id="shot-01", check_name="dimension", passed=True, details="ok")])

    assert task.model_dump()["task_id"] == "task-001"
    assert asset.model_dump()["filename"] == "demo.png"
    assert analysis.model_dump()["category"] == "tea"
    assert analysis.model_dump()["analysis_scope"] == "sku_level"
    assert shot_plan.model_dump()["shots"][0]["shot_id"] == "shot-01"
    assert shot_plan.model_dump()["shots"][0]["shot_type"] == "hero"
    assert copy_plan.model_dump()["items"][0]["title"] == "标题"
    assert layout_plan.model_dump()["items"][0]["blocks"][0]["kind"] == "title"
    assert prompt_plan.model_dump()["prompts"][0]["output_size"] == "1440x1440"
    assert prompt_plan.model_dump()["prompts"][0]["negative_prompt"][0] == "garbled text"
    assert result.model_dump()["images"][0]["width"] == 1440
    assert qc_report.model_dump()["checks"][0]["passed"] is True

