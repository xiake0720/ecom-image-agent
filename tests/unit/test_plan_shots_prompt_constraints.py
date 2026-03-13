from __future__ import annotations

from src.core.config import ResolvedModelSelection
from src.domain.product_analysis import (
    MaterialGuess,
    PackagingStructure,
    ProductAnalysis,
    VisualConstraints,
    VisualIdentity,
)
from src.domain.shot_plan import ShotPlan
from src.domain.task import Task
from src.services.planning.tea_shot_planner import build_tea_shot_plan
from src.services.storage.local_storage import LocalStorageService
from src.workflows.nodes.plan_shots import plan_shots
from src.workflows.state import WorkflowDependencies


class FakeShotPlanningProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate_structured(self, prompt: str, response_model, *, system_prompt: str | None = None):
        self.calls.append(prompt)
        return response_model.model_validate(
            {
                "shots": [
                    {
                        "shot_id": "shot-01",
                        "title": "主图",
                        "purpose": "建立整组统一主视觉与商品识别",
                        "composition_hint": "主体居中偏下，右侧或上方留白",
                        "copy_goal": "突出品牌、茶类与包装主体",
                        "shot_type": "hero",
                        "goal": "建立茶叶整组统一商业主视觉",
                        "focus": "包装主体与标签区",
                        "scene_direction": "高级棚拍主图，灰绿背景，克制道具",
                        "composition_direction": "主体居中偏下，右侧干净留白",
                    },
                    {
                        "shot_id": "shot-02",
                        "title": "干茶细节",
                        "purpose": "补充茶叶条索、干茶形态与包装呼应",
                        "composition_hint": "近景细节，局部特写，顶部留白",
                        "copy_goal": "强调干茶形态与原料质感",
                        "shot_type": "dry_leaf_detail",
                        "goal": "补充干茶条索与原料质感信息",
                        "focus": "干茶条索与材质",
                        "scene_direction": "同色系静物细节场景，不加入跑题道具",
                        "composition_direction": "主体近景偏左，上方留白",
                    },
                    {
                        "shot_id": "shot-03",
                        "title": "茶汤图",
                        "purpose": "展示冲泡后的汤色、清透度与饮用氛围",
                        "composition_hint": "杯盏稳定，侧方留白",
                        "copy_goal": "强调汤色、香气联想与饮用体验",
                        "shot_type": "tea_soup",
                        "goal": "完成茶叶核心图型中的茶汤表现",
                        "focus": "茶汤色泽与器具搭配",
                        "scene_direction": "统一灰绿暖金基调的冲泡场景",
                        "composition_direction": "主体偏中间，右上留白",
                    },
                ]
            }
        )


class DummyRenderer:
    pass


class DummyOCRService:
    pass


def _build_tea_analysis(*, has_outer_box: str = "no", container_count: str = "1") -> ProductAnalysis:
    return ProductAnalysis(
        category="tea",
        subcategory="乌龙茶",
        product_type="tea can",
        product_form="packaged_tea",
        packaging_structure=PackagingStructure(
            primary_container="tea_can",
            has_outer_box=has_outer_box,
            has_visible_lid="yes",
            container_count=container_count,
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
            recommended_style_direction=["高端静物棚拍", "克制东方气质"],
            avoid=["凉席元素", "喧宾夺主花器"],
        ),
        visual_style_keywords=["高级", "安定", "东方质感"],
        recommended_focuses=["包装主体", "干茶条索", "茶汤状态", "叶底状态"],
    )


def test_build_tea_shot_plan_uses_ordered_slots_for_five_six_and_seven_images() -> None:
    tea_analysis = _build_tea_analysis()
    task5 = Task(task_id="task-5", brand_name="A", product_name="B", platform="tmall", output_size="1440x1440", shot_count=5, copy_tone="专业", task_dir="outputs/tasks/task-5")
    task6 = Task(task_id="task-6", brand_name="A", product_name="B", platform="tmall", output_size="1440x1440", shot_count=6, copy_tone="专业", task_dir="outputs/tasks/task-6")
    task7 = Task(task_id="task-7", brand_name="A", product_name="B", platform="tmall", output_size="1440x1440", shot_count=7, copy_tone="专业", task_dir="outputs/tasks/task-7")

    plan5 = build_tea_shot_plan(task5, tea_analysis)
    plan6 = build_tea_shot_plan(task6, tea_analysis)
    plan7 = build_tea_shot_plan(task7, tea_analysis)

    assert [shot.shot_type for shot in plan5.shots] == [
        "hero",
        "dry_leaf_detail",
        "tea_soup",
        "brewed_leaf_detail",
        "packaging_display",
    ]
    assert [shot.shot_type for shot in plan6.shots] == [
        "hero",
        "dry_leaf_detail",
        "tea_soup",
        "brewed_leaf_detail",
        "packaging_display",
        "tea_table_scene",
    ]
    assert [shot.shot_type for shot in plan7.shots] == [
        "hero",
        "dry_leaf_detail",
        "tea_soup",
        "brewed_leaf_detail",
        "packaging_display",
        "tea_table_scene",
        "multi_can_display",
    ]


def test_plan_shots_real_mode_uses_tea_slots_then_only_enriches_detail_fields() -> None:
    provider = FakeShotPlanningProvider()
    deps = WorkflowDependencies(
        storage=LocalStorageService(),
        planning_provider=provider,
        vision_analysis_provider=None,
        image_generation_provider=object(),
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(),
        text_provider_mode="real",
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
    task = Task(
        task_id="task-plan-001",
        brand_name="品牌A",
        product_name="高山乌龙",
        platform="tmall",
        output_size="1440x1440",
        shot_count=5,
        copy_tone="专业自然",
        task_dir="outputs/tasks/task-plan-001",
    )
    state = {
        "task": task,
        "product_analysis": _build_tea_analysis(),
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }

    result = plan_shots(state, deps)

    assert isinstance(result["shot_plan"], ShotPlan)
    assert len(provider.calls) == 1
    prompt = provider.calls[0]
    assert '"planner_mode": "templated_slots_then_minimal_enrichment"' in prompt
    assert '"fixed_shot_slots"' in prompt
    assert '"editable_fields"' in prompt
    assert "不得新增、删除或替换 shot slots" in prompt
    assert [shot.shot_type for shot in result["shot_plan"].shots] == [
        "hero",
        "dry_leaf_detail",
        "tea_soup",
        "brewed_leaf_detail",
        "packaging_display",
    ]
    assert any("tea 类目优先走模板化槽位规划" in log for log in result["logs"])
