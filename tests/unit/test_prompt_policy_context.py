from __future__ import annotations

from src.domain.copy_plan import CopyItem
from src.domain.layout_plan import LayoutBlock, LayoutItem
from src.domain.product_analysis import (
    MaterialGuess,
    PackagingStructure,
    ProductAnalysis,
    VisualConstraints,
    VisualIdentity,
)
from src.domain.shot_plan import ShotSpec
from src.domain.task import Task
from src.services.prompting.context_builder import build_build_prompts_context, build_plan_shots_context
from src.services.prompting.policy_loader import load_category_policy


def test_policy_loader_loads_tea_category_policy() -> None:
    policy = load_category_policy("tea")
    assert policy["enabled"] is True
    assert "hero" in policy["core_shot_types"]
    assert "凉席" in policy["scene_prop_boundaries"]["banned"]


def test_context_builder_injects_tea_policy_into_runtime_context() -> None:
    task = Task(
        task_id="task-policy-001",
        brand_name="品牌A",
        product_name="高山乌龙",
        platform="tmall",
        output_size="1440x1440",
        shot_count=4,
        copy_tone="专业自然",
        task_dir="outputs/tasks/task-policy-001",
    )
    product_analysis = ProductAnalysis(
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
            style_impression=["东方雅致"],
            must_preserve=["包装主体轮廓", "标签位置"],
        ),
        material_guess=MaterialGuess(container_material="metal", label_material="paper"),
        visual_constraints=VisualConstraints(
            recommended_style_direction=["高端静物棚拍", "保留东方气质"],
            avoid=["凉席元素", "喧宾夺主花器"],
        ),
        visual_style_keywords=["高阶", "东方", "克制"],
        recommended_focuses=["包装主体", "茶汤", "叶底"],
    )
    shot = ShotSpec(
        shot_id="shot-01",
        title="主图",
        purpose="建立主视觉",
        composition_hint="主体居中，右侧留白",
        copy_goal="突出品牌与包装主体",
        shot_type="hero",
        goal="建立统一商业视觉",
        focus="包装主体与标签区",
        scene_direction="高级棚拍静物主图",
        composition_direction="主体居中偏下，右侧干净留白",
    )
    copy_item = CopyItem(shot_id="shot-01", title="标题", subtitle="副标题")
    layout_item = LayoutItem(
        shot_id="shot-01",
        canvas_width=1440,
        canvas_height=1440,
        blocks=[LayoutBlock(kind="title", x=980, y=120, width=280, height=220)],
    )

    plan_context = build_plan_shots_context(task=task, product_analysis=product_analysis)
    prompt_context = build_build_prompts_context(
        task=task,
        product_analysis=product_analysis,
        shot=shot,
        copy_item=copy_item,
        layout_item=layout_item,
    )

    assert plan_context["category_family"] == "tea"
    assert "hero" in plan_context["category_policy"]["core_shot_types"]
    assert "凉席" in plan_context["category_policy"]["scene_prop_boundaries"]["banned"]
    assert prompt_context["shot_type_policy"]["shot_type"] == "hero"
    assert "天猫" not in prompt_context["platform_policy"]["platform"]
    assert "质感稳定" in prompt_context["platform_policy"]["aesthetic_direction"]
