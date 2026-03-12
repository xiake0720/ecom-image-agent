from __future__ import annotations

from pathlib import Path

from src.core.paths import get_task_dir
from src.core.config import ResolvedModelSelection
from src.domain.asset import Asset
from src.domain.copy_plan import CopyItem, CopyPlan
from src.domain.image_prompt_plan import ImagePrompt
from src.domain.layout_plan import LayoutBlock, LayoutItem, LayoutPlan
from src.domain.product_analysis import (
    MaterialGuess,
    PackagingStructure,
    ProductAnalysis,
    VisualConstraints,
    VisualIdentity,
)
from src.domain.shot_plan import ShotPlan, ShotSpec
from src.domain.task import Task
from src.services.storage.local_storage import LocalStorageService
from src.workflows.nodes.build_prompts import build_prompts
from src.workflows.state import WorkflowDependencies


class FakePerShotTextProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate_structured(self, prompt: str, response_model, *, system_prompt: str | None = None):
        self.calls.append(prompt)
        shot_id = "shot-01" if "shot-01" in prompt else "shot-02"
        return response_model.model_validate(
            {
                "shot_id": shot_id,
                "shot_type": "hero" if shot_id == "shot-01" else "feature_detail",
                "prompt": f"detailed prompt for {shot_id}",
                "negative_prompt": ["garbled text", "wrong packaging"],
                "output_size": "1440x1440",
                "preserve_rules": ["保持包装主体", "保持标签位置"],
                "text_space_hint": "top_right_clean_space",
                "composition_notes": ["主体清晰", "右侧留白"],
                "style_notes": ["高端商业摄影", "真实棚拍质感"],
            }
        )


class DummyRenderer:
    pass


class DummyOCRService:
    pass


def test_build_prompts_real_mode_uses_per_shot_generation_and_saves_debug_artifacts(tmp_path: Path) -> None:
    storage = LocalStorageService()
    task_dir = tmp_path / "task-001"
    task_dir.mkdir(parents=True, exist_ok=True)
    text_provider = FakePerShotTextProvider()
    deps = WorkflowDependencies(
        storage=storage,
        planning_provider=text_provider,
        vision_analysis_provider=None,
        image_generation_provider=object(),
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(),
        text_provider_mode="real",
        vision_provider_mode="mock",
        image_provider_mode="mock",
        planning_provider_name="FakePerShotTextProvider",
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
        task_id="task-001",
        brand_name="品牌A",
        product_name="产品A",
        platform="taobao",
        output_size="1440x1440",
        shot_count=2,
        copy_tone="专业自然",
        task_dir=str(task_dir),
    )
    state = {
        "task": task,
        "assets": [Asset(asset_id="asset-01", filename="demo.png", local_path=str(tmp_path / "demo.png"))],
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
                recommended_style_direction=["高端静物棚拍", "保留东方气质"],
                avoid=["纯白背景", "包装变形"],
            ),
            recommended_focuses=["包装主体", "标签区"],
        ),
        "shot_plan": ShotPlan(
            shots=[
                ShotSpec(
                    shot_id="shot-01",
                    title="主图",
                    purpose="展示主视觉",
                    composition_hint="主体居中",
                    copy_goal="突出品牌",
                    shot_type="hero",
                    goal="突出品牌主视觉",
                    focus="包装主体",
                    scene_direction="高级棚拍场景",
                    composition_direction="主体居中，右侧留白",
                ),
                ShotSpec(
                    shot_id="shot-02",
                    title="细节图",
                    purpose="展示标签细节",
                    composition_hint="局部近景",
                    copy_goal="强调卖点",
                    shot_type="feature_detail",
                    goal="强调包装细节",
                    focus="标签与材质",
                    scene_direction="包装细节近景场景",
                    composition_direction="主体靠左，右侧留白",
                ),
            ]
        ),
        "copy_plan": CopyPlan(
            items=[
                CopyItem(shot_id="shot-01", title="标题1", subtitle="副标题1"),
                CopyItem(shot_id="shot-02", title="标题2", subtitle="副标题2"),
            ]
        ),
        "layout_plan": LayoutPlan(
            items=[
                LayoutItem(
                    shot_id="shot-01",
                    canvas_width=1440,
                    canvas_height=1440,
                    blocks=[LayoutBlock(kind="title", x=900, y=120, width=300, height=200)],
                ),
                LayoutItem(
                    shot_id="shot-02",
                    canvas_width=1440,
                    canvas_height=1440,
                    blocks=[LayoutBlock(kind="title", x=80, y=100, width=300, height=200)],
                ),
            ]
        ),
        "logs": [],
    }

    result = build_prompts(state, deps)

    assert len(text_provider.calls) == 2
    assert all("image_input_sent_to_model" in call for call in text_provider.calls)
    assert all('"image_input_sent_to_model": false' in call for call in text_provider.calls)
    assert all("render_images" in call for call in text_provider.calls)
    assert all("demo.png" not in call for call in text_provider.calls)
    assert all("参考素材" not in call for call in text_provider.calls)
    assert len(result["image_prompt_plan"].prompts) == 2
    assert any("当前未向模型发送图片输入" in log for log in result["logs"])
    assert any("build_image_prompts.md" in log for log in result["logs"])
    real_task_dir = get_task_dir(task.task_id)
    assert (real_task_dir / "image_prompt_plan.json").exists()
    assert (real_task_dir / "artifacts" / "shots" / "shot-01" / "shot.json").exists()
    assert (real_task_dir / "artifacts" / "shots" / "shot-01" / "copy.json").exists()
    assert (real_task_dir / "artifacts" / "shots" / "shot-01" / "layout.json").exists()
    assert (real_task_dir / "artifacts" / "shots" / "shot-01" / "prompt.json").exists()
    assert result["image_prompt_plan"].prompts[0].prompt == "detailed prompt for shot-01"
    assert result["image_prompt_plan"].prompts[1].text_space_hint == "top_right_clean_space" or result["image_prompt_plan"].prompts[1].text_space_hint == "top_left_clean_space"
