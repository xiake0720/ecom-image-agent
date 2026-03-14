from __future__ import annotations

from src.domain.product_analysis import (
    MaterialGuess,
    PackagingStructure,
    ProductAnalysis,
    VisualConstraints,
    VisualIdentity,
)
from src.domain.shot_plan import ShotPlan, ShotSpec
from src.domain.task import Task
from src.services.planning.layout_generator import build_mock_layout_plan
from src.services.storage.local_storage import LocalStorageService
from src.workflows.nodes.generate_layout import generate_layout
from src.workflows.state import WorkflowDependencies


def test_generate_layout_outputs_text_safe_zone_and_logs() -> None:
    deps = _build_deps()
    task = _build_task("task-layout-node")
    state = {
        "task": task,
        "product_analysis": _build_product_analysis(),
        "shot_plan": _build_shot_plan(),
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }

    result = generate_layout(state, deps)

    first_item = result["layout_plan"].items[0]
    assert first_item.text_safe_zone in {"top_left", "top_right", "right_center", "left_center", "bottom_left", "bottom_right"}
    assert first_item.safe_zone_score_breakdown
    assert first_item.selection_reason
    assert any("chosen_text_safe_zone=" in log for log in result["logs"])
    assert any("safe_zone_score_breakdown=" in log for log in result["logs"])
    assert any("rejected_zones=" in log for log in result["logs"])


def test_mock_layout_plan_is_stable_and_prefers_prompt_safe_side() -> None:
    shot_plan = _build_shot_plan()
    product_analysis = _build_product_analysis()

    first_plan = build_mock_layout_plan(shot_plan, "1440x1440", product_analysis=product_analysis)
    second_plan = build_mock_layout_plan(shot_plan, "1440x1440", product_analysis=product_analysis)

    assert [item.text_safe_zone for item in first_plan.items] == [item.text_safe_zone for item in second_plan.items]
    assert first_plan.items[0].text_safe_zone == "top_right"
    assert first_plan.items[1].text_safe_zone in {"top_right", "right_center"}


def _build_deps() -> WorkflowDependencies:
    return WorkflowDependencies(
        storage=LocalStorageService(),
        planning_provider=None,
        vision_analysis_provider=None,
        image_generation_provider=None,
        text_renderer=None,
        ocr_service=None,
        text_provider_mode="mock",
        vision_provider_mode="mock",
        image_provider_mode="mock",
    )


def _build_task(task_id: str) -> Task:
    return Task(
        task_id=task_id,
        brand_name="品牌A",
        product_name="产品A",
        platform="taobao",
        output_size="1440x1440",
        shot_count=2,
        copy_tone="专业自然",
        task_dir=f"outputs/tasks/{task_id}",
    )


def _build_product_analysis() -> ProductAnalysis:
    return ProductAnalysis(
        category="tea",
        subcategory="乌龙茶",
        product_type="tea can",
        product_form="packaged_tea",
        packaging_structure=PackagingStructure(
            primary_container="tea_can",
            has_outer_box="no",
            has_visible_lid="yes",
            container_count="1",
        ),
        visual_identity=VisualIdentity(
            dominant_colors=["green", "gold"],
            label_position="front_center",
            label_ratio="medium",
            style_impression=["premium"],
            must_preserve=["package body", "label layout"],
        ),
        material_guess=MaterialGuess(container_material="metal", label_material="paper"),
        visual_constraints=VisualConstraints(
            recommended_style_direction=["soft premium still life"],
            avoid=["busy texture", "label distortion"],
        ),
        recommended_focuses=["package", "label"],
    )


def _build_shot_plan() -> ShotPlan:
    return ShotPlan(
        shots=[
            ShotSpec(
                shot_id="shot-01",
                title="主图",
                purpose="展示主包装",
                composition_hint="主体居中，右侧留白",
                copy_goal="突出品牌",
                shot_type="hero",
                goal="电商主图",
                focus="完整包装主体",
                scene_direction="premium still life",
                composition_direction="主体居中偏下，右侧保留干净文字区",
            ),
            ShotSpec(
                shot_id="shot-02",
                title="细节图",
                purpose="展示标签细节",
                composition_hint="主体靠左，右侧留白",
                copy_goal="强调细节卖点",
                shot_type="feature_detail",
                goal="突出材质与标签",
                focus="标签与局部材质",
                scene_direction="controlled detail shot",
                composition_direction="近景构图，主体靠左，右侧留白",
            ),
        ]
    )
