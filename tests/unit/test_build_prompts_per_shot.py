from __future__ import annotations

from pathlib import Path

from src.core.config import ResolvedModelSelection
from src.core.paths import get_task_dir
from src.domain.asset import Asset
from src.domain.copy_plan import CopyItem, CopyPlan
from src.domain.image_prompt_plan import ImagePromptPlan
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


class FakePromptProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate_structured(self, prompt: str, response_model, *, system_prompt: str | None = None):
        self.calls.append(prompt)
        if response_model is ImagePromptPlan:
            return response_model.model_validate(
                {
                    "prompts": [
                        {
                            "shot_id": "shot-01",
                            "shot_type": "hero",
                            "prompt": "batch prompt for shot-01",
                            "negative_prompt": ["garbled text", "wrong packaging"],
                            "output_size": "1440x1440",
                            "preserve_rules": ["保持包装主体", "保持标签位置"],
                            "text_space_hint": "top_right",
                            "composition_notes": ["主体清晰", "右侧留白"],
                            "style_notes": ["高端商业摄影", "真实棚拍质感"],
                        },
                        {
                            "shot_id": "shot-02",
                            "shot_type": "feature_detail",
                            "prompt": "batch prompt for shot-02",
                            "negative_prompt": ["garbled text", "wrong packaging"],
                            "output_size": "1440x1440",
                            "preserve_rules": ["保持包装主体", "保持标签位置"],
                            "text_space_hint": "top_left",
                            "composition_notes": ["主体清晰", "左侧留白"],
                            "style_notes": ["高端商业摄影", "真实棚拍质感"],
                        },
                    ]
                }
            )
        shot_id = "shot-01" if "shot-01" in prompt else "shot-02"
        return response_model.model_validate(
            {
                "shot_id": shot_id,
                "shot_type": "hero" if shot_id == "shot-01" else "feature_detail",
                "prompt": f"detailed prompt for {shot_id}",
                "negative_prompt": ["garbled text", "wrong packaging"],
                "output_size": "1440x1440",
                "preserve_rules": ["保持包装主体", "保持标签位置"],
                "text_space_hint": "top_right",
                "composition_notes": ["主体清晰", "右侧留白"],
                "style_notes": ["高端商业摄影", "真实棚拍质感"],
            }
        )


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


def test_build_prompts_real_mode_uses_per_shot_generation_and_saves_debug_artifacts(tmp_path: Path) -> None:
    storage = LocalStorageService()
    task_dir = tmp_path / "task-001"
    task_dir.mkdir(parents=True, exist_ok=True)
    text_provider = FakePromptProvider()
    deps = _build_deps(storage, text_provider, generation_mode="image_edit")
    task = _build_task("task-001", str(task_dir))
    state = _build_state(task, tmp_path, prompt_build_mode="per_shot", cache_enabled=False)

    result = build_prompts(state, deps)
    first_prompt = result["image_prompt_plan"].prompts[0]

    assert len(text_provider.calls) == 2
    assert all("image_input_sent_to_model" in call for call in text_provider.calls)
    assert all('"image_input_sent_to_model": false' in call for call in text_provider.calls)
    assert all("render_images" in call for call in text_provider.calls)
    assert all("demo.png" not in call for call in text_provider.calls)
    assert len(result["image_prompt_plan"].prompts) == 2
    assert result["image_prompt_plan"].generation_mode == "image_edit"
    assert first_prompt.generation_mode == "image_edit"
    assert first_prompt.prompt == "detailed prompt for shot-01"
    assert first_prompt.edit_instruction
    assert first_prompt.edit_instruction != first_prompt.prompt
    assert first_prompt.keep_subject_rules
    assert first_prompt.editable_regions
    assert first_prompt.locked_regions
    assert first_prompt.text_safe_zone == first_prompt.text_space_hint
    assert any("target_generation_mode=image_edit" in log for log in result["logs"])
    real_task_dir = get_task_dir(task.task_id)
    assert (real_task_dir / "image_prompt_plan.json").exists()
    assert (real_task_dir / "artifacts" / "shots" / "shot-01" / "prompt.json").exists()


def test_build_prompts_real_mode_uses_batch_generation_and_writes_per_shot_artifacts(tmp_path: Path) -> None:
    storage = LocalStorageService()
    task_dir = tmp_path / "task-batch"
    task_dir.mkdir(parents=True, exist_ok=True)
    text_provider = FakePromptProvider()
    deps = _build_deps(storage, text_provider, generation_mode="image_edit")
    task = _build_task("task-batch", str(task_dir))
    state = _build_state(task, tmp_path, prompt_build_mode="batch", cache_enabled=False)

    result = build_prompts(state, deps)

    assert len(text_provider.calls) == 1
    assert '"prompt_build_mode": "batch"' in text_provider.calls[0]
    assert len(result["image_prompt_plan"].prompts) == 2
    assert result["image_prompt_plan"].generation_mode == "image_edit"
    assert result["image_prompt_plan"].prompts[0].prompt == "batch prompt for shot-01"
    assert result["image_prompt_plan"].prompts[0].edit_instruction
    assert any("using batch mode target_generation_mode=image_edit" in log for log in result["logs"])
    real_task_dir = get_task_dir(task.task_id)
    assert (real_task_dir / "artifacts" / "shots" / "shot-01" / "prompt.json").exists()
    assert (real_task_dir / "artifacts" / "shots" / "shot-02" / "prompt.json").exists()


def test_build_prompts_uses_node_cache_on_second_run(tmp_path: Path) -> None:
    demo_path = tmp_path / "demo-cache.png"
    demo_path.write_bytes(b"cache-demo-image")
    storage = LocalStorageService()
    text_provider = FakePromptProvider()
    deps = _build_deps(storage, text_provider, generation_mode="image_edit")
    task = _build_task(f"task-cache-{tmp_path.name}", str(tmp_path / "task-cache"))
    state = _build_state(task, tmp_path, prompt_build_mode="per_shot", cache_enabled=True)
    state["assets"] = [Asset(asset_id="asset-01", filename="demo-cache.png", local_path=str(demo_path))]

    first_result = build_prompts(state, deps)
    second_result = build_prompts(state, deps)

    assert len(text_provider.calls) == 2
    assert len(first_result["image_prompt_plan"].prompts) == 2
    assert len(second_result["image_prompt_plan"].prompts) == 2
    assert any("cache miss" in log for log in first_result["logs"])
    assert any("cache hit" in log for log in second_result["logs"])


def test_build_prompts_t2i_mode_keeps_legacy_prompt_fields_compatible(tmp_path: Path) -> None:
    storage = LocalStorageService()
    text_provider = FakePromptProvider()
    deps = _build_deps(storage, text_provider, generation_mode="t2i")
    task = _build_task("task-t2i", str(tmp_path / "task-t2i"))
    state = _build_state(task, tmp_path, prompt_build_mode="per_shot", cache_enabled=False)
    state["assets"] = []

    result = build_prompts(state, deps)
    first_prompt = result["image_prompt_plan"].prompts[0]

    assert result["image_prompt_plan"].generation_mode == "t2i"
    assert first_prompt.generation_mode == "t2i"
    assert first_prompt.prompt == "detailed prompt for shot-01"
    assert first_prompt.negative_prompt
    assert first_prompt.preserve_rules
    assert first_prompt.edit_instruction


def test_build_prompts_uses_layout_text_safe_zone_without_reinferring(tmp_path: Path) -> None:
    storage = LocalStorageService()
    text_provider = FakePromptProvider()
    deps = _build_deps(storage, text_provider, generation_mode="image_edit")
    task = _build_task("task-layout-zone", str(tmp_path / "task-layout-zone"))
    state = _build_state(task, tmp_path, prompt_build_mode="per_shot", cache_enabled=False)
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
    assert any('"layout_text_safe_zone": "bottom_right"' in call for call in text_provider.calls)


def _build_deps(
    storage: LocalStorageService,
    text_provider: FakePromptProvider,
    *,
    generation_mode: str,
) -> WorkflowDependencies:
    return WorkflowDependencies(
        storage=storage,
        planning_provider=text_provider,
        vision_analysis_provider=None,
        image_generation_provider=FakeImageGenerationProvider(generation_mode),
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(),
        text_provider_mode="real",
        vision_provider_mode="mock",
        image_provider_mode="mock",
        planning_provider_name="FakePromptProvider",
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


def _build_state(task: Task, tmp_path: Path, *, prompt_build_mode: str, cache_enabled: bool) -> dict:
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
        "cache_enabled": cache_enabled,
        "ignore_cache": False,
        "prompt_build_mode": prompt_build_mode,
    }
