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
                        "purpose": "建立整组统一主视觉",
                        "composition_hint": "主体居中，右侧留白",
                        "copy_goal": "突出品牌与包装主体",
                        "shot_type": "hero",
                        "goal": "先建立整组统一风格锚点",
                        "focus": "包装主体与标签区",
                        "scene_direction": "高级棚拍主图，灰绿背景，克制道具",
                        "composition_direction": "主体居中偏下，右侧干净留白",
                    },
                    {
                        "shot_id": "shot-02",
                        "title": "干茶细节",
                        "purpose": "补充茶叶形态细节",
                        "composition_hint": "局部近景，顶部留白",
                        "copy_goal": "强调茶叶形态与质感",
                        "shot_type": "dry_leaf_detail",
                        "goal": "补充茶叶类目的核心信息层",
                        "focus": "干茶条索与包装呼应",
                        "scene_direction": "同色系静物细节场景，不加入离题器物",
                        "composition_direction": "主体近景靠左，上方留白",
                    },
                    {
                        "shot_id": "shot-03",
                        "title": "茶汤图",
                        "purpose": "展示冲泡后茶汤质感",
                        "composition_hint": "主体稳定，侧边留白",
                        "copy_goal": "强调汤色与饮用氛围",
                        "shot_type": "tea_soup",
                        "goal": "完成茶叶类目的核心图型覆盖",
                        "focus": "茶汤色泽与器具克制搭配",
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


def test_plan_shots_real_mode_injects_category_family_and_style_anchor_constraints() -> None:
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
        shot_count=3,
        copy_tone="专业自然",
        task_dir="outputs/tasks/task-plan-001",
    )
    state = {
        "task": task,
        "product_analysis": ProductAnalysis(
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
                recommended_style_direction=["高端静物棚拍", "克制东方气质"],
                avoid=["凉席元素", "喧宾夺主花器"],
            ),
            visual_style_keywords=["高级", "安定", "东方质感"],
            recommended_focuses=["包装主体", "标签区", "茶叶形态"],
        ),
        "logs": [],
    }

    result = plan_shots(state, deps)

    assert isinstance(result["shot_plan"], ShotPlan)
    assert len(provider.calls) == 1
    prompt = provider.calls[0]
    assert '"category_family": "tea"' in prompt
    assert '"core_shot_types"' in prompt
    assert "凉席元素" in prompt
    assert "整组统一风格锚点" in prompt
    assert any("当前识别到的类目族群：tea" in log for log in result["logs"])
    assert any("当前选择的整组风格锚点摘要" in log for log in result["logs"])
    assert any("核心图型数量=3，扩展图型数量=0" in log for log in result["logs"])
