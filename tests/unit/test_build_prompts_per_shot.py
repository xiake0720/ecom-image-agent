from __future__ import annotations

from pathlib import Path

from src.core.config import ResolvedModelSelection
from src.core.paths import get_task_dir
from src.domain.asset import Asset
from src.domain.copy_plan import CopyItem, CopyPlan
from src.domain.layout_plan import LayoutBlock, LayoutItem, LayoutPlan
from src.domain.product_analysis import (
    MaterialGuess,
    PackagingStructure,
    ProductAnalysis,
    VisualConstraints,
    VisualIdentity,
)
from src.domain.shot_prompt_specs import ShotPromptSpec, ShotPromptSpecPlan
from src.domain.shot_plan import ShotPlan, ShotSpec
from src.domain.style_architecture import StyleArchitecture
from src.domain.task import Task
from src.services.storage.local_storage import LocalStorageService
from src.workflows.nodes.build_prompts import build_prompts
from src.workflows.state import WorkflowDependencies


class FakeImageGenerationProvider:
    def __init__(self, generation_mode: str) -> None:
        self.generation_mode = generation_mode

    def resolve_generation_context(self, *, reference_assets=None):
        asset_ids = [asset.asset_id for asset in (reference_assets or [])]
        return type(
            "GenerationContext",
            (),
            {
                "generation_mode": self.generation_mode,
                "provider_alias": "fake",
                "model_id": "fake-image",
                "reference_asset_ids": asset_ids if self.generation_mode == "image_edit" else [],
                "selected_reference_assets": reference_assets or [],
            },
        )()


class DummyRenderer:
    pass


class DummyOCRService:
    pass


def test_build_prompts_maps_structured_shot_specs_to_legacy_prompt_plan(tmp_path: Path) -> None:
    storage = LocalStorageService()
    deps = _build_deps(storage, generation_mode="image_edit")
    task = _build_task("task-001", str(tmp_path / "task-001"))
    state = _build_state(task, tmp_path, cache_enabled=False)

    result = build_prompts(state, deps)
    first_prompt = result["image_prompt_plan"].prompts[0]

    assert len(result["image_prompt_plan"].prompts) == 2
    assert result["image_prompt_plan"].generation_mode == "image_edit"
    assert first_prompt.generation_mode == "image_edit"
    assert "Use the uploaded reference product as the exact hero subject" in first_prompt.prompt
    assert "strict product lock" in first_prompt.edit_instruction
    assert first_prompt.keep_subject_rules
    assert first_prompt.editable_regions
    assert first_prompt.locked_regions
    assert first_prompt.text_safe_zone == first_prompt.text_space_hint
    assert any("style_architecture_present=True" in log for log in result["logs"])
    assert any("shot_prompt_specs_present=True" in log for log in result["logs"])
    real_task_dir = get_task_dir(task.task_id)
    assert (real_task_dir / "image_prompt_plan.json").exists()
    assert (real_task_dir / "artifacts" / "shots" / "shot-01" / "prompt.json").exists()


def test_build_prompts_uses_node_cache_on_second_run(tmp_path: Path) -> None:
    storage = LocalStorageService()
    deps = _build_deps(storage, generation_mode="image_edit")
    task = _build_task(f"task-cache-{tmp_path.name}", str(tmp_path / "task-cache"))
    state = _build_state(task, tmp_path, cache_enabled=True)

    first_result = build_prompts(state, deps)
    second_result = build_prompts(state, deps)

    assert len(first_result["image_prompt_plan"].prompts) == 2
    assert len(second_result["image_prompt_plan"].prompts) == 2
    assert any("cache miss" in log for log in first_result["logs"])
    assert any("cache hit" in log for log in second_result["logs"])


def test_build_prompts_keeps_layout_text_safe_zone_authoritative(tmp_path: Path) -> None:
    storage = LocalStorageService()
    deps = _build_deps(storage, generation_mode="image_edit")
    task = _build_task("task-layout-zone", str(tmp_path / "task-layout-zone"))
    state = _build_state(task, tmp_path, cache_enabled=False)
    state["layout_plan"].items[0] = LayoutItem(
        shot_id="shot-01",
        canvas_width=1440,
        canvas_height=1440,
        text_safe_zone="bottom_right",
        blocks=[LayoutBlock(kind="title", x=120, y=110, width=300, height=200)],
    )

    result = build_prompts(state, deps)

    first_prompt = result["image_prompt_plan"].prompts[0]
    assert first_prompt.text_safe_zone == "bottom_right"
    assert first_prompt.text_space_hint == "bottom_right"


def _build_deps(storage: LocalStorageService, *, generation_mode: str) -> WorkflowDependencies:
    return WorkflowDependencies(
        storage=storage,
        planning_provider=object(),
        vision_analysis_provider=None,
        image_generation_provider=FakeImageGenerationProvider(generation_mode),
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(),
        text_provider_mode="mock",
        vision_provider_mode="mock",
        image_provider_mode="mock",
        planning_provider_name="StructuredMapper",
        vision_provider_name="None",
        image_provider_name="FakeImageProvider",
        planning_model_selection=ResolvedModelSelection(
            capability="planning",
            provider_key="mock",
            model_id="structured-mapper",
            label="StructuredMapper",
            source="test",
        ),
        vision_model_selection=ResolvedModelSelection(
            capability="vision",
            provider_key="mock",
            model_id="mock-vision",
            label="MockVision",
            source="test",
        ),
    )


def _build_task(task_id: str, task_dir: str) -> Task:
    return Task(
        task_id=task_id,
        brand_name="品牌A",
        product_name="产品A",
        platform="taobao",
        output_size="1440x1440",
        shot_count=2,
        copy_tone="专业自然",
        task_dir=task_dir,
    )


def _build_state(task: Task, tmp_path: Path, *, cache_enabled: bool) -> dict:
    return {
        "task": task,
        "assets": [Asset(asset_id="asset-01", filename="demo.png", local_path=str(tmp_path / "demo.png"))],
        "product_analysis": ProductAnalysis(
            category="tea",
            subcategory="乌龙茶",
            product_type="tea can",
            product_form="packaged_tea",
            packaging_structure=PackagingStructure(
                primary_container="tea_can",
                has_outer_box="yes",
                has_visible_lid="yes",
                container_count="1",
            ),
            visual_identity=VisualIdentity(
                dominant_colors=["green", "gold"],
                label_position="front_center",
                label_ratio="medium",
                style_impression=["东方雅致"],
                must_preserve=["package silhouette", "label position"],
            ),
            material_guess=MaterialGuess(container_material="metal", label_material="paper"),
            visual_constraints=VisualConstraints(
                recommended_style_direction=["premium still life", "keep package stable"],
                avoid=["plain white background", "package deformation"],
            ),
            recommended_focuses=["package", "label"],
            locked_elements=["package silhouette", "front label layout"],
            editable_elements=["background", "lighting", "props"],
            package_type="gift_box",
            primary_color="red",
            material="paper gift box",
            label_structure="front-centered hero label",
        ),
        "style_architecture": StyleArchitecture(
            platform="taobao",
            user_preferences=["premium", "gift", "light_background"],
            style_theme="premium tea gift box visual world",
            color_strategy=["keep the product as the only saturated center"],
            lighting_strategy=["main light direction fixed at upper-left"],
            lens_strategy=["50mm commercial lens feel"],
            prop_system=["tea tray", "neutral ceramic ware"],
            background_strategy=["ivory and warm gray only"],
            text_strategy=["reserve explicit text safe zones"],
            global_negative_rules=["do not redesign the label"],
        ),
        "shot_plan": ShotPlan(
            shots=[
                ShotSpec(
                    shot_id="shot-01",
                    title="主图",
                    purpose="展示主视觉",
                    composition_hint="主体居中",
                    copy_goal="突出品牌",
                    shot_type="hero_brand",
                    goal="show hero gift box",
                    focus="package hero",
                    scene_direction="premium still life",
                    composition_direction="subject centered, top-right safe zone",
                ),
                ShotSpec(
                    shot_id="shot-02",
                    title="细节图",
                    purpose="展示标签细节",
                    composition_hint="局部近景",
                    copy_goal="强调卖点",
                    shot_type="dry_leaf_detail",
                    goal="show dry leaf detail",
                    focus="dry leaf and package cue",
                    scene_direction="detail still life",
                    composition_direction="subject near left, top-left safe zone",
                ),
            ]
        ),
        "copy_plan": CopyPlan(
            items=[
                CopyItem(shot_id="shot-01", title="标题1", subtitle="副标题"),
                CopyItem(shot_id="shot-02", title="标题2", subtitle="副标题"),
            ]
        ),
        "layout_plan": LayoutPlan(
            items=[
                LayoutItem(
                    shot_id="shot-01",
                    canvas_width=1440,
                    canvas_height=1440,
                    text_safe_zone="top_right",
                    blocks=[LayoutBlock(kind="title", x=900, y=120, width=300, height=200)],
                ),
                LayoutItem(
                    shot_id="shot-02",
                    canvas_width=1440,
                    canvas_height=1440,
                    text_safe_zone="top_left",
                    blocks=[LayoutBlock(kind="title", x=80, y=100, width=300, height=200)],
                ),
            ]
        ),
        "shot_prompt_specs": ShotPromptSpecPlan(
            specs=[
                ShotPromptSpec(
                    shot_id="shot-01",
                    shot_type="hero_brand",
                    goal="show hero gift box",
                    product_lock=["package silhouette", "front label layout"],
                    subject_prompt="Use the uploaded reference product as the exact hero subject.",
                    package_appearance_prompt="Keep gift box shape, red package color, and front-centered label unchanged.",
                    composition_prompt="Subject centered, text-safe zone at top_right.",
                    background_prompt="Muted ivory background.",
                    lighting_prompt="Upper-left soft commercial light.",
                    style_prompt="premium tea gift box visual world",
                    quality_prompt="high-end commercial photography",
                    negative_prompt=["do not redesign the label"],
                    layout_constraints=["must reserve text safe zone at top_right"],
                    render_constraints=["image_edit mode should preserve product lock strictly"],
                    copy_intent="突出品牌",
                ),
                ShotPromptSpec(
                    shot_id="shot-02",
                    shot_type="dry_leaf_detail",
                    goal="show dry leaf detail",
                    product_lock=["package silhouette", "front label layout"],
                    subject_prompt="Use the uploaded reference product with visible tea detail linkage.",
                    package_appearance_prompt="Keep package body and label unchanged.",
                    composition_prompt="Subject near left, text-safe zone at top_left.",
                    background_prompt="Muted warm gray background.",
                    lighting_prompt="Upper-left soft commercial light.",
                    style_prompt="premium tea gift box visual world",
                    quality_prompt="premium macro detail photography",
                    negative_prompt=["do not redesign the label"],
                    layout_constraints=["must reserve text safe zone at top_left"],
                    render_constraints=["image_edit mode should preserve product lock strictly"],
                    copy_intent="强调卖点",
                ),
            ]
        ),
        "logs": [],
        "cache_enabled": cache_enabled,
        "ignore_cache": False,
        "prompt_build_mode": "per_shot",
    }
