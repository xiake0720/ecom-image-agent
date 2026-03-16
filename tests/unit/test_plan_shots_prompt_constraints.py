"""茶叶模板分流相关测试。

覆盖目标：
- 礼盒模板仍保留 carry_action / open_box_structure
- 圆柱金属罐改走 tea_tin_can_template
- 非茶叶类不受影响
- 下游 copy 节点仍可继续消费新的 `shot_plan`
"""

from __future__ import annotations

from src.core.config import ResolvedModelSelection
from src.domain.copy_plan import CopyPlan
from src.domain.product_analysis import (
    MaterialGuess,
    PackagingStructure,
    ProductAnalysis,
    VisualConstraints,
    VisualIdentity,
)
from src.domain.shot_plan import ShotPlan
from src.domain.task import Task
from src.services.planning.copy_generator import build_mock_copy_plan
from src.services.planning.tea_shot_planner import (
    TEA_GIFT_BOX_PHASE1_SHOTS,
    TEA_TIN_CAN_PACKSHOT_ONLY_PHASE1_SHOTS,
    TEA_TIN_CAN_PHASE1_SHOTS,
    build_tea_shot_plan,
    resolve_tea_asset_completeness_mode,
    resolve_tea_package_template_family,
    resolve_tea_template_name,
)
from src.services.storage.local_storage import LocalStorageService
from src.workflows.nodes.plan_shots import plan_shots
from src.workflows.state import WorkflowDependencies


class FakeShotPlanningProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate_structured(self, prompt: str, response_model, *, system_prompt: str | None = None):
        del system_prompt
        self.calls.append(prompt)
        return response_model.model_validate(
            {
                "shots": [
                    {
                        "shot_id": "shot_01",
                        "goal": "Make the package the only saturated hero subject in the frame.",
                        "focus": "full package hero view",
                        "scene_direction": "premium still life hero scene",
                        "composition_direction": "subject centered with top-right safe zone",
                        "text_safe_zone_preference": "top_right",
                    },
                    {
                        "shot_id": "shot_02",
                        "goal": "Show restrained human interaction while keeping the package recognizable.",
                        "focus": "package carried by hand",
                        "scene_direction": "muted lifestyle scene",
                        "composition_direction": "leave safe zone opposite the action direction",
                        "text_safe_zone_preference": "top_left",
                    },
                    {
                        "shot_id": "shot_03",
                        "goal": "Reveal the opening structure clearly.",
                        "focus": "box opening and internal structure",
                        "scene_direction": "clean premium tabletop",
                        "composition_direction": "top or 3/4 angle with safe zone above",
                        "text_safe_zone_preference": "top_right",
                    },
                    {
                        "shot_id": "shot_04",
                        "goal": "Connect the tea leaf detail with the same package world.",
                        "focus": "dry leaf texture and package relationship",
                        "scene_direction": "macro detail scene",
                        "composition_direction": "clear background safe zone",
                        "text_safe_zone_preference": "top_right",
                    },
                    {
                        "shot_id": "shot_05",
                        "goal": "Show tea soup color and drinking mood.",
                        "focus": "tea soup vessel and package cue",
                        "scene_direction": "premium brewed tea setting",
                        "composition_direction": "upper safe zone",
                        "text_safe_zone_preference": "top",
                    },
                ]
            }
        )


class DummyRenderer:
    pass


class DummyOCRService:
    pass


def _build_gift_box_analysis() -> ProductAnalysis:
    return ProductAnalysis(
        category="tea",
        subcategory="oolong",
        product_type="tea gift box",
        product_form="packaged_tea",
        packaging_structure=PackagingStructure(
            primary_container="gift_box",
            has_outer_box="yes",
            has_visible_lid="yes",
            container_count="1",
        ),
        visual_identity=VisualIdentity(
            dominant_colors=["red", "gold"],
            label_position="front_center",
            label_ratio="medium",
            style_impression=["premium"],
            must_preserve=["package silhouette", "label position"],
        ),
        material_guess=MaterialGuess(container_material="paper gift box", label_material="paper"),
        visual_constraints=VisualConstraints(
            recommended_style_direction=["premium still life", "restrained gift scene"],
            avoid=["festival clutter", "prop overload"],
        ),
        recommended_focuses=["package", "open structure", "dry leaf", "tea soup"],
        locked_elements=["package silhouette", "front label layout"],
        editable_elements=["background", "props", "lighting"],
        package_type="gift_box",
        package_template_family="tea_gift_box",
        primary_color="red",
        material="paper gift box",
        label_structure="front-centered hero label",
    )


def _build_tin_can_analysis() -> ProductAnalysis:
    return ProductAnalysis(
        category="tea",
        subcategory="single origin oolong",
        product_type="cylindrical metal tin",
        product_form="packaged_tea",
        packaging_structure=PackagingStructure(
            primary_container="tin_can",
            has_outer_box="no",
            has_visible_lid="yes",
            container_count="1",
        ),
        visual_identity=VisualIdentity(
            dominant_colors=["red", "gold"],
            label_position="front_center",
            label_ratio="medium",
            style_impression=["premium"],
            must_preserve=["cylindrical silhouette", "front label position"],
        ),
        material_guess=MaterialGuess(container_material="metal tin", label_material="paper"),
        visual_constraints=VisualConstraints(
            recommended_style_direction=["premium still life", "restrained product scene"],
            avoid=["festival clutter", "gift box props"],
        ),
        recommended_focuses=["tin hero", "package detail", "dry leaf", "tea soup"],
        locked_elements=["cylindrical can silhouette", "front label layout"],
        editable_elements=["background", "props", "lighting"],
        package_type="cylindrical metal tin",
        asset_completeness_mode="packshot_plus_detail",
        primary_color="red",
        material="cylindrical metal tin",
        label_structure="front-centered tin label",
    )


def _build_tin_can_packshot_only_analysis() -> ProductAnalysis:
    return _build_tin_can_analysis().model_copy(update={"asset_completeness_mode": "packshot_only"})


def _build_other_analysis() -> ProductAnalysis:
    return ProductAnalysis(
        category="beauty",
        subcategory="serum",
        product_type="facial serum",
        product_form="bottle",
        packaging_structure=PackagingStructure(
            primary_container="bottle",
            has_outer_box="no",
            has_visible_lid="yes",
            container_count="1",
        ),
        visual_identity=VisualIdentity(
            dominant_colors=["white", "silver"],
            label_position="front_center",
            label_ratio="small",
            style_impression=["clean"],
            must_preserve=["bottle silhouette"],
        ),
        material_guess=MaterialGuess(container_material="glass", label_material="paper"),
        visual_constraints=VisualConstraints(
            recommended_style_direction=["clean beauty still life"],
            avoid=["chaotic props"],
        ),
        recommended_focuses=["bottle", "dropper"],
    )


def _build_deps(provider: FakeShotPlanningProvider | None = None, *, text_mode: str = "mock") -> WorkflowDependencies:
    return WorkflowDependencies(
        storage=LocalStorageService(),
        planning_provider=provider or FakeShotPlanningProvider(),
        vision_analysis_provider=None,
        image_generation_provider=object(),
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(),
        text_provider_mode=text_mode,
        vision_provider_mode="mock",
        image_provider_mode="mock",
        planning_provider_name="FakeShotPlanningProvider",
        vision_provider_name="None",
        image_provider_name="FakeImageProvider",
        planning_model_selection=ResolvedModelSelection(
            capability="planning",
            provider_key="qwen",
            model_id="qwen/qwen3.5-122b-a10b",
            label="Qwen3.5",
            source="test",
        ),
        vision_model_selection=ResolvedModelSelection(
            capability="vision",
            provider_key="qwen",
            model_id="qwen/qwen3.5-122b-a10b",
            label="Qwen3.5",
            source="test",
        ),
    )


def test_build_tea_gift_box_shot_plan_keeps_gift_box_template() -> None:
    analysis = _build_gift_box_analysis()
    task = Task(
        task_id="task-5",
        brand_name="A",
        product_name="B",
        platform="tmall",
        output_size="1440x1440",
        shot_count=2,
        copy_tone="专业",
        task_dir="outputs/tasks/task-5",
    )

    plan = build_tea_shot_plan(task, analysis)

    assert resolve_tea_package_template_family(analysis) == "tea_gift_box"
    assert [(shot.shot_id, shot.shot_type) for shot in plan.shots] == list(TEA_GIFT_BOX_PHASE1_SHOTS)
    assert [shot.preferred_text_safe_zone for shot in plan.shots] == [
        "top_right",
        "top_left",
        "top_right",
        "top_right",
        "top",
    ]


def test_build_tea_tin_can_shot_plan_uses_tin_template() -> None:
    analysis = _build_tin_can_analysis()
    task = Task(
        task_id="task-tin-5",
        brand_name="A",
        product_name="cylindrical metal tin oolong",
        platform="tmall",
        output_size="1440x1440",
        shot_count=5,
        copy_tone="专业",
        task_dir="outputs/tasks/task-tin-5",
    )

    plan = build_tea_shot_plan(task, analysis)

    assert resolve_tea_package_template_family(analysis) == "tea_tin_can"
    assert resolve_tea_asset_completeness_mode(analysis) == "packshot_plus_detail"
    assert resolve_tea_template_name(analysis) == "tea_tin_can_packshot_plus_detail"
    assert [(shot.shot_id, shot.shot_type) for shot in plan.shots] == list(TEA_TIN_CAN_PHASE1_SHOTS)
    assert [shot.shot_type for shot in plan.shots] == [
        "hero_brand",
        "package_detail",
        "dry_leaf_detail",
        "tea_soup_experience",
        "lifestyle_or_brewing_context",
    ]
    assert "carry_action" not in [shot.shot_type for shot in plan.shots]
    assert "open_box_structure" not in [shot.shot_type for shot in plan.shots]


def test_build_tea_tin_can_packshot_only_plan_avoids_dry_leaf_and_tea_soup() -> None:
    analysis = _build_tin_can_packshot_only_analysis()
    task = Task(
        task_id="task-tin-packshot-only-5",
        brand_name="A",
        product_name="cylindrical metal tin oolong",
        platform="tmall",
        output_size="1440x1440",
        shot_count=5,
        copy_tone="专业",
        task_dir="outputs/tasks/task-tin-packshot-only-5",
    )

    plan = build_tea_shot_plan(task, analysis)

    assert resolve_tea_package_template_family(analysis) == "tea_tin_can"
    assert resolve_tea_asset_completeness_mode(analysis) == "packshot_only"
    assert resolve_tea_template_name(analysis) == "tea_tin_can_packshot_only"
    assert [(shot.shot_id, shot.shot_type) for shot in plan.shots] == list(TEA_TIN_CAN_PACKSHOT_ONLY_PHASE1_SHOTS)
    assert [shot.shot_type for shot in plan.shots] == [
        "hero_brand",
        "package_detail",
        "label_or_material_detail",
        "package_with_leaf_hint",
        "package_in_brewing_context",
    ]
    assert "dry_leaf_detail" not in [shot.shot_type for shot in plan.shots]
    assert "tea_soup_experience" not in [shot.shot_type for shot in plan.shots]


def test_plan_shots_real_mode_uses_fixed_gift_box_context_and_keeps_five_shots() -> None:
    provider = FakeShotPlanningProvider()
    deps = _build_deps(provider, text_mode="real")
    task = Task(
        task_id="task-plan-001",
        brand_name="品牌A",
        product_name="高山乌龙礼盒",
        platform="tmall",
        output_size="1440x1440",
        shot_count=9,
        copy_tone="专业自然",
        task_dir="outputs/tasks/task-plan-001",
    )
    state = {
        "task": task,
        "product_analysis": _build_gift_box_analysis(),
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }

    result = plan_shots(state, deps)

    assert isinstance(result["shot_plan"], ShotPlan)
    assert len(provider.calls) == 1
    prompt = provider.calls[0]
    assert '"planner_mode": "fixed_phase1_five_shots"' in prompt
    assert '"package_template_family": "tea_gift_box"' in prompt
    assert '"asset_completeness_mode": "packshot_only"' in prompt
    assert '"chosen_template_name": "tea_gift_box_default"' in prompt
    assert '"fixed_shot_slots"' in prompt
    assert '"editable_fields"' in prompt
    assert "text_safe_zone_preference" in prompt
    assert "must keep all five fixed shot slots" in prompt
    assert [(shot.shot_id, shot.shot_type) for shot in result["shot_plan"].shots] == list(TEA_GIFT_BOX_PHASE1_SHOTS)
    assert any("tea_fixed_phase1_template=true" in log for log in result["logs"])
    assert any("package_template_family=tea_gift_box" in log for log in result["logs"])
    assert any("chosen_template_name=tea_gift_box_default" in log for log in result["logs"])
    assert any("fixed_template_name=tea_gift_box_default" in log for log in result["logs"])


def test_plan_shots_mock_mode_routes_tin_can_to_tin_template() -> None:
    deps = _build_deps(text_mode="mock")
    task = Task(
        task_id="task-plan-tin-001",
        brand_name="品牌A",
        product_name="单罐乌龙",
        platform="tmall",
        output_size="1440x1440",
        shot_count=5,
        copy_tone="专业自然",
        task_dir="outputs/tasks/task-plan-tin-001",
    )
    state = {
        "task": task,
        "product_analysis": _build_tin_can_analysis(),
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }

    result = plan_shots(state, deps)

    assert [(shot.shot_id, shot.shot_type) for shot in result["shot_plan"].shots] == list(TEA_TIN_CAN_PHASE1_SHOTS)
    assert any("package_template_family=tea_tin_can" in log for log in result["logs"])
    assert any("asset_completeness_mode=packshot_plus_detail" in log for log in result["logs"])
    assert any("chosen_template_name=tea_tin_can_packshot_plus_detail" in log for log in result["logs"])
    assert any("fixed_template_name=tea_tin_can_packshot_plus_detail" in log for log in result["logs"])


def test_plan_shots_mock_mode_routes_tin_can_packshot_only_to_safe_template() -> None:
    deps = _build_deps(text_mode="mock")
    task = Task(
        task_id="task-plan-tin-packshot-only-001",
        brand_name="品牌A",
        product_name="单罐乌龙",
        platform="tmall",
        output_size="1440x1440",
        shot_count=5,
        copy_tone="专业自然",
        task_dir="outputs/tasks/task-plan-tin-packshot-only-001",
    )
    state = {
        "task": task,
        "product_analysis": _build_tin_can_packshot_only_analysis(),
        "analyze_selected_main_asset_id": "asset-main",
        "analyze_selected_detail_asset_id": None,
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }

    result = plan_shots(state, deps)

    assert [(shot.shot_id, shot.shot_type) for shot in result["shot_plan"].shots] == list(TEA_TIN_CAN_PACKSHOT_ONLY_PHASE1_SHOTS)
    assert any("package_template_family=tea_tin_can" in log for log in result["logs"])
    assert any("asset_completeness_mode=packshot_only" in log for log in result["logs"])
    assert any("selected_main_asset_id=asset-main" in log for log in result["logs"])
    assert any("selected_detail_asset_id=-" in log for log in result["logs"])
    assert any("chosen_template_name=tea_tin_can_packshot_only" in log for log in result["logs"])


def test_non_tea_category_keeps_existing_non_template_behavior() -> None:
    deps = _build_deps(text_mode="mock")
    task = Task(
        task_id="task-non-tea-001",
        brand_name="品牌B",
        product_name="修护精华",
        category="beauty",
        platform="tmall",
        output_size="1440x1440",
        shot_count=3,
        copy_tone="理性克制",
        task_dir="outputs/tasks/task-non-tea-001",
    )
    state = {
        "task": task,
        "product_analysis": _build_other_analysis(),
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }

    result = plan_shots(state, deps)

    assert len(result["shot_plan"].shots) == 3
    assert [(shot.shot_id, shot.shot_type) for shot in result["shot_plan"].shots] != list(TEA_GIFT_BOX_PHASE1_SHOTS)
    assert not any("tea_fixed_phase1_template=true" in log for log in result["logs"])


def test_downstream_copy_generation_can_still_consume_fixed_tin_can_shot_plan() -> None:
    task = Task(
        task_id="task-copy-001",
        brand_name="品牌C",
        product_name="老树红茶单罐",
        platform="tmall",
        output_size="1440x1440",
        shot_count=1,
        copy_tone="稳重",
        task_dir="outputs/tasks/task-copy-001",
    )
    shot_plan = build_tea_shot_plan(task, _build_tin_can_analysis())

    copy_plan = build_mock_copy_plan(task, shot_plan)

    assert isinstance(copy_plan, CopyPlan)
    assert len(copy_plan.items) == 5
    assert copy_plan.items[0].shot_id == "shot_01"
