from __future__ import annotations

from pathlib import Path

from src.core.config import ResolvedModelSelection
from src.core.paths import ensure_task_dirs
from src.core.paths import get_task_dir
from src.domain.asset import Asset, AssetType
from src.domain.generation_result import GenerationResult
from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from src.domain.layout_plan import LayoutPlan
from src.domain.shot_plan import ShotPlan, ShotSpec
from src.domain.task import Task
from src.services.analysis.product_analyzer import build_mock_product_analysis
from src.services.planning.layout_generator import build_mock_layout_plan
from src.services.planning.tea_shot_planner import TEA_PHASE1_SHOTS, build_tea_shot_plan
from src.services.storage.local_storage import LocalStorageService
from src.workflows.graph import build_workflow
from src.workflows.nodes.analyze_product import analyze_product
from src.workflows.nodes.finalize import finalize
from src.workflows.nodes.generate_copy import generate_copy
from src.workflows.nodes.generate_layout import generate_layout
from src.workflows.nodes.plan_shots import plan_shots
from src.workflows.nodes.render_images import render_images
from src.workflows.nodes.shot_prompt_refiner import shot_prompt_refiner
from src.workflows.nodes.style_director import style_director
from src.workflows.state import WorkflowDependencies


class DummyPlanningProvider:
    def generate_structured(self, *args, **kwargs):
        raise AssertionError("Mock-mode tests should not call the planning provider.")


class PartialStylePlanningProvider:
    def generate_structured(self, prompt: str, response_model, *, system_prompt: str | None = None):
        del prompt, system_prompt
        return response_model.model_validate(
            {
                "platform": "tmall",
                "user_preferences": ["premium"],
                "style_theme": "restrained commercial tea world",
                "main_light_direction": "",
                "color_strategy": [],
                "lighting_strategy": [],
                "lens_strategy": [],
                "prop_system": [],
                "background_strategy": [],
                "text_strategy": [],
                "global_negative_rules": [],
            }
        )


class CapturingImageProvider:
    def __init__(self) -> None:
        self.captured_plan: ImagePromptPlan | None = None

    def resolve_generation_context(self, *, reference_assets=None):
        asset_ids = [asset.asset_id for asset in (reference_assets or [])]
        return type(
            "GenerationContext",
            (),
            {
                "generation_mode": "image_edit" if asset_ids else "t2i",
                "provider_alias": "fake-image",
                "model_id": "fake-image-edit",
                "reference_asset_ids": asset_ids,
                "selected_reference_assets": reference_assets or [],
            },
        )()

    def generate_images(self, plan, *, output_dir, reference_assets=None):
        self.captured_plan = plan
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "01_shot_01.png"
        path.write_bytes(b"fake")
        return GenerationResult.model_validate(
            {
                "images": [
                    {
                        "shot_id": "shot_01",
                        "image_path": str(path),
                        "preview_path": str(path),
                        "width": 1440,
                        "height": 1440,
                        "status": "generated",
                    }
                ]
            }
        )


class DummyRenderer:
    pass


class DummyOCRService:
    pass


def test_tea_phase1_shot_plan_is_fixed_to_five_shots() -> None:
    task = _build_task("task-fixed-five")
    task = task.model_copy(update={"shot_count": 2})
    analysis = build_mock_product_analysis([], task.product_name)

    plan = build_tea_shot_plan(task, analysis)

    assert len(plan.shots) == 5
    assert [(shot.shot_id, shot.shot_type) for shot in plan.shots] == list(TEA_PHASE1_SHOTS)


def test_style_director_outputs_required_fields() -> None:
    task = _build_task("task-style-director")
    ensure_task_dirs(task.task_id)
    storage = LocalStorageService()
    storage.save_task_manifest(task)
    state = {
        "task": task,
        "product_analysis": build_mock_product_analysis([], task.product_name),
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }

    result = style_director(state, _build_deps(storage=storage))
    architecture = result["style_architecture"]

    assert architecture.style_theme
    assert architecture.main_light_direction
    assert architecture.color_strategy
    assert architecture.lighting_strategy
    assert architecture.lens_strategy
    assert architecture.prop_system
    assert architecture.background_strategy
    assert architecture.text_strategy
    assert architecture.global_negative_rules
    assert (get_task_dir(task.task_id) / "style_architecture.json").exists()
    assert any("style_architecture_generated=true" in line for line in result["logs"])
    assert any("main_light_direction=upper-left" in line or "main_light_direction=upper-right" in line for line in result["logs"])
    assert any("background_strategy_summary=" in line and "none" not in line for line in result["logs"])
    assert any("platform_and_preferences=" in line for line in result["logs"])


def test_style_director_fills_missing_key_fields_with_defaults() -> None:
    task = _build_task("task-style-director-defaults")
    ensure_task_dirs(task.task_id)
    storage = LocalStorageService()
    storage.save_task_manifest(task)
    deps = _build_deps(storage=storage, planning_provider=PartialStylePlanningProvider(), text_mode="real")
    state = {
        "task": task,
        "product_analysis": build_mock_product_analysis([], task.product_name),
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }

    result = style_director(state, deps)
    architecture = result["style_architecture"]

    assert architecture.main_light_direction == "upper-left"
    assert architecture.color_strategy
    assert architecture.background_strategy
    assert architecture.lens_strategy
    assert not any("main_light_direction=unspecified" in line for line in result["logs"])
    assert not any("background_strategy_summary=-" in line for line in result["logs"])


def test_style_director_result_can_be_written_back_into_state() -> None:
    task = _build_task("task-style-state")
    state = {
        "task": task,
        "product_analysis": build_mock_product_analysis([], task.product_name),
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }

    updates = style_director(state, _build_deps())
    state = {**state, **updates}

    assert "style_architecture" in state
    assert state["style_architecture"].platform == task.platform
    assert state["style_architecture"].style_theme


def test_shot_prompt_refiner_outputs_structured_eight_layer_specs() -> None:
    task = _build_task("task-shot-specs")
    analysis = build_mock_product_analysis([], task.product_name)
    shot_plan = build_tea_shot_plan(task, analysis)
    layout_plan = build_mock_layout_plan(shot_plan, task.output_size, product_analysis=analysis)
    state = {
        "task": task,
        "product_analysis": analysis,
        "style_architecture": style_director(
            {
                "task": task,
                "product_analysis": analysis,
                "logs": [],
                "cache_enabled": False,
                "ignore_cache": False,
            },
            _build_deps(),
        )["style_architecture"],
        "shot_plan": shot_plan,
        "layout_plan": layout_plan,
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }

    result = shot_prompt_refiner(state, _build_deps())
    plan = result["shot_prompt_specs"]
    spec = plan.specs[0]

    assert len(plan.specs) == 5
    assert spec.subject_prompt
    assert spec.package_appearance_prompt
    assert spec.composition_prompt
    assert spec.background_prompt
    assert spec.lighting_prompt
    assert spec.style_prompt
    assert spec.quality_prompt
    assert spec.negative_prompt
    assert spec.product_lock.must_preserve
    assert spec.layout_constraints.preferred_text_safe_zone
    assert spec.render_constraints.generation_mode == "t2i"
    assert "upper-left" in spec.lighting_prompt or "left" in spec.lighting_prompt
    assert state["style_architecture"].style_theme in spec.style_prompt
    assert spec.has_complete_prompt_layers() is True
    assert any("complete_eight_layers=true" in line for line in result["logs"])
    assert any("generation_mode_summary=t2i" in line for line in result["logs"])


def test_shot_prompt_refiner_adds_exclusive_rules_for_tin_can_detail_modes() -> None:
    task = _build_task("task-shot-spec-diff")
    analysis = build_mock_product_analysis([], task.product_name).model_copy(
        update={
            "package_template_family": "tea_tin_can",
            "asset_completeness_mode": "packshot_plus_detail",
            "package_type": "tea_tin_can",
            "material": "metal tin",
            "label_structure": "front wrap label",
            "primary_color": "green",
        }
    )
    shot_plan = ShotPlan(
        shots=[
            ShotSpec(
                shot_id="shot_01",
                title="Hero",
                purpose="hero",
                composition_hint="stable hero",
                copy_goal="brand",
                shot_type="hero_brand",
            ),
            ShotSpec(
                shot_id="shot_02",
                title="Detail",
                purpose="detail",
                composition_hint="close crop",
                copy_goal="detail",
                shot_type="package_detail",
            ),
            ShotSpec(
                shot_id="shot_03",
                title="Leaf",
                purpose="leaf",
                composition_hint="leaf foreground",
                copy_goal="leaf",
                shot_type="dry_leaf_detail",
            ),
            ShotSpec(
                shot_id="shot_04",
                title="Soup",
                purpose="soup",
                composition_hint="vessel foreground",
                copy_goal="soup",
                shot_type="tea_soup_experience",
            ),
            ShotSpec(
                shot_id="shot_05",
                title="Context",
                purpose="context",
                composition_hint="brewing table",
                copy_goal="context",
                shot_type="lifestyle_or_brewing_context",
            ),
        ]
    )
    layout_plan = build_mock_layout_plan(shot_plan, task.output_size, product_analysis=analysis)
    style_architecture = style_director(
        {
            "task": task,
            "product_analysis": analysis,
            "logs": [],
            "cache_enabled": False,
            "ignore_cache": False,
        },
        _build_deps(),
    )["style_architecture"]

    result = shot_prompt_refiner(
        {
            "task": task,
            "product_analysis": analysis,
            "style_architecture": style_architecture,
            "shot_plan": shot_plan,
            "layout_plan": layout_plan,
            "logs": [],
            "cache_enabled": False,
            "ignore_cache": False,
        },
        _build_deps(),
    )

    spec_map = {spec.shot_type: spec for spec in result["shot_prompt_specs"].specs}

    assert "absolute first subject" in spec_map["hero_brand"].subject_prompt
    assert "must not look like the hero image" in spec_map["package_detail"].subject_prompt
    assert "package_detail must not look like hero image" in spec_map["package_detail"].negative_prompt
    assert spec_map["package_detail"].render_constraints.product_lock_level == "medium_product_lock"
    assert "Dry tea leaves must be the absolute first subject" in spec_map["dry_leaf_detail"].subject_prompt
    assert spec_map["dry_leaf_detail"].render_constraints.product_lock_level == "anchor_only_product_lock"
    assert "Visible liquid is mandatory" in spec_map["tea_soup_experience"].subject_prompt
    assert "tea_soup_experience must include brewed tea vessel" in spec_map["tea_soup_experience"].negative_prompt
    assert "Brewing props or explicit scene anchors are mandatory" in spec_map["lifestyle_or_brewing_context"].subject_prompt
    assert any("primary_subject=dry tea leaves in the foreground" in line for line in result["logs"])
    assert any("banned_fallback_pattern=full front hero package composition" in line for line in result["logs"])


def test_render_images_assembles_execution_prompt_from_shot_spec(tmp_path: Path) -> None:
    task = _build_task(f"task-render-spec-{tmp_path.name}")
    analysis = build_mock_product_analysis([], task.product_name)
    shot_plan = build_tea_shot_plan(task, analysis)
    layout_plan = build_mock_layout_plan(shot_plan, task.output_size, product_analysis=analysis)
    deps = _build_deps(image_provider=CapturingImageProvider())
    style_architecture = style_director(
        {
            "task": task,
            "product_analysis": analysis,
            "logs": [],
            "cache_enabled": False,
            "ignore_cache": False,
        },
        deps,
    )["style_architecture"]
    shot_specs = shot_prompt_refiner(
        {
            "task": task,
            "product_analysis": analysis,
            "style_architecture": style_architecture,
            "shot_plan": shot_plan,
            "layout_plan": layout_plan,
            "logs": [],
            "cache_enabled": False,
            "ignore_cache": False,
        },
        deps,
    )["shot_prompt_specs"]
    state = {
        "task": task,
        "assets": [
            Asset(asset_id="asset-01", filename="main.png", local_path=str(tmp_path / "main.png"), asset_type=AssetType.PRODUCT),
            Asset(asset_id="asset-02", filename="detail.png", local_path=str(tmp_path / "detail.png"), asset_type=AssetType.DETAIL),
        ],
        "product_analysis": analysis,
        "style_architecture": style_architecture,
        "shot_prompt_specs": shot_specs,
        "image_prompt_plan": ImagePromptPlan(
            generation_mode="image_edit",
            prompts=[
                ImagePrompt(
                    shot_id="shot_01",
                    shot_type="hero_brand",
                    prompt="legacy prompt",
                    edit_instruction="legacy edit instruction",
                    output_size="1440x1440",
                )
            ],
        ),
        "logs": [],
        "render_mode": "final",
    }

    result = render_images(state, deps)

    captured_prompt = deps.image_generation_provider.captured_plan.prompts[0].edit_instruction
    assert captured_prompt.index("[Task Type And Current Shot Objective]") < captured_prompt.index("[Product Identity Lock]")
    assert captured_prompt.index("[Shot Differentiation Rules]") < captured_prompt.index("[Product Identity Lock]")
    assert captured_prompt.index("[Allowed Editable Regions]") < captured_prompt.index("[Product Identity Lock]")
    assert "[Task Type And Current Shot Objective]" in captured_prompt
    assert "[Shot Differentiation Rules]" in captured_prompt
    assert "[Subject Hierarchy]" in captured_prompt
    assert "[Allowed Editable Regions]" in captured_prompt
    assert "[Product Identity Lock]" in captured_prompt
    assert "[Global Style Architecture]" in captured_prompt
    assert "[Layout And Text Safe Zone]" in captured_prompt
    assert "Allowed scene change level:" in captured_prompt
    assert "Editable regions final:" in captured_prompt
    assert "Must preserve visuals:" in captured_prompt
    assert "Must preserve texts:" in captured_prompt
    assert "Must not change:" in captured_prompt
    assert "Editable region strategy:" in captured_prompt
    assert "legacy prompt" not in captured_prompt
    assert "('" not in captured_prompt
    assert any("execution_source=image_edit_contract_mode" in line for line in result["logs"])
    assert any("reference_asset_ids=['asset-01', 'asset-02']" in line for line in result["logs"])
    assert any("allowed_scene_change_level=" in line for line in result["logs"])
    assert any("editable_regions_final=" in line for line in result["logs"])
    assert not any("keep_subject_rules=[\"('" in line or "keep_subject_rules=['(\"" in line for line in result["logs"])


def test_render_images_falls_back_to_legacy_prompt_when_contracts_are_missing(tmp_path: Path) -> None:
    task = _build_task(f"task-render-legacy-{tmp_path.name}")
    deps = _build_deps(image_provider=CapturingImageProvider())
    state = {
        "task": task,
        "assets": [
            Asset(
                asset_id="asset-01",
                filename="main.png",
                local_path=str(tmp_path / "main.png"),
                asset_type=AssetType.PRODUCT,
            )
        ],
        "image_prompt_plan": ImagePromptPlan(
            generation_mode="image_edit",
            prompts=[
                ImagePrompt(
                    shot_id="shot_01",
                    shot_type="hero_brand",
                    prompt="legacy prompt",
                    edit_instruction="legacy edit instruction",
                    output_size="1440x1440",
                )
            ],
        ),
        "logs": [],
        "render_mode": "final",
    }

    result = render_images(state, deps)

    captured_prompt = deps.image_generation_provider.captured_plan.prompts[0].edit_instruction
    assert captured_prompt == "legacy edit instruction"
    assert any("execution_source=legacy_prompt_fallback" in line for line in result["logs"])


def test_pipeline_nodes_persist_style_and_shot_spec_artifacts() -> None:
    task_id = "task-architecture-artifacts"
    task_dir = get_task_dir(task_id)
    task = _build_task(task_id)
    storage = LocalStorageService()
    ensure_task_dirs(task_id)
    storage.save_task_manifest(task)
    deps = _build_deps(storage=storage)
    state = {
        "task": task,
        "assets": [
            Asset(asset_id="asset-01", filename="main.png", local_path=str(task_dir / "inputs" / "main.png"), asset_type=AssetType.PRODUCT),
        ],
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }

    state = {**state, **analyze_product(state, deps)}
    state = {**state, **style_director(state, deps)}
    state = {**state, **plan_shots(state, deps)}
    state = {**state, **generate_copy(state, deps)}
    state = {**state, **generate_layout(state, deps)}
    state = {**state, **shot_prompt_refiner(state, deps)}

    assert (task_dir / "product_analysis.json").exists()
    assert (task_dir / "style_architecture.json").exists()
    assert (task_dir / "shot_plan.json").exists()
    assert (task_dir / "shot_prompt_specs.json").exists()


def test_core_structured_contracts_are_connected_in_workflow_state() -> None:
    task_id = "task-connected-contracts"
    task = _build_task(task_id)
    task_dir = get_task_dir(task_id)
    storage = LocalStorageService()
    ensure_task_dirs(task_id)
    storage.save_task_manifest(task)
    deps = _build_deps(storage=storage)
    state = {
        "task": task,
        "assets": [
            Asset(
                asset_id="asset-01",
                filename="main.png",
                local_path=str(task_dir / "inputs" / "main.png"),
                asset_type=AssetType.PRODUCT,
            )
        ],
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
        "render_mode": "preview",
    }

    state = {**state, **analyze_product(state, deps)}
    state = {**state, **style_director(state, deps)}
    state = {**state, **plan_shots(state, deps)}
    state = {**state, **generate_copy(state, deps)}
    state = {**state, **generate_layout(state, deps)}
    state = {**state, **shot_prompt_refiner(state, deps)}

    assert state["product_analysis"]
    assert state["product_lock"]
    assert state["style_architecture"]
    assert state["shot_plan"]
    assert state["shot_prompt_specs"]
    assert state["product_lock"].model_dump() == state["product_analysis"].model_dump()
    assert any("style_architecture_connected=true" in line for line in state["logs"])
    assert any("shot_prompt_specs_available_for_render=true" in line for line in state["logs"])
    assert any("connected_contract_files=" in line for line in state["logs"])


def test_finalize_logs_core_contract_artifact_presence() -> None:
    task_id = "task-finalize-contract-artifacts"
    task = _build_task(task_id)
    task_dir = get_task_dir(task_id)
    storage = LocalStorageService()
    ensure_task_dirs(task_id)
    storage.save_task_manifest(task)
    deps = _build_deps(storage=storage)
    state = {
        "task": task,
        "assets": [
            Asset(
                asset_id="asset-01",
                filename="main.png",
                local_path=str(task_dir / "inputs" / "main.png"),
                asset_type=AssetType.PRODUCT,
            )
        ],
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
        "render_mode": "preview",
        "render_variant": "preview",
        "generated_images": [],
        "final_image_paths": [],
        "preview_image_paths": [],
    }

    state = {**state, **analyze_product(state, deps)}
    state = {**state, **style_director(state, deps)}
    state = {**state, **plan_shots(state, deps)}
    state = {**state, **generate_copy(state, deps)}
    state = {**state, **generate_layout(state, deps)}
    state = {**state, **shot_prompt_refiner(state, deps)}
    finalized = finalize(state, deps)

    assert finalized["artifact_paths"]["product_analysis"] == task_dir / "product_analysis.json"
    assert finalized["artifact_paths"]["style_architecture"] == task_dir / "style_architecture.json"
    assert finalized["artifact_paths"]["shot_plan"] == task_dir / "shot_plan.json"
    assert finalized["artifact_paths"]["shot_prompt_specs"] == task_dir / "shot_prompt_specs.json"
    assert any("contract_artifact_presence=" in line for line in finalized["logs"])
    assert any("shot_prompt_specs_available_for_render=true" in line for line in finalized["logs"])


def test_workflow_order_keeps_structured_contract_chain_connected() -> None:
    build_workflow.cache_clear()
    graph = build_workflow().get_graph()
    edges = {(edge.source, edge.target) for edge in graph.edges}

    assert ("analyze_product", "style_director") in edges
    assert ("style_director", "plan_shots") in edges
    assert ("plan_shots", "generate_copy") in edges
    assert ("generate_layout", "shot_prompt_refiner") in edges
    assert ("shot_prompt_refiner", "build_prompts") in edges
    assert ("build_prompts", "render_images") in edges


def _build_task(task_id: str) -> Task:
    return Task(
        task_id=task_id,
        brand_name="品牌A",
        product_name="凤凰单丛礼盒",
        platform="taobao",
        output_size="1440x1440",
        shot_count=5,
        copy_tone="高端礼赠",
        task_dir=str(get_task_dir(task_id)),
    )


def _build_deps(*, storage=None, image_provider=None, planning_provider=None, text_mode: str = "mock") -> WorkflowDependencies:
    return WorkflowDependencies(
        storage=storage or LocalStorageService(),
        planning_provider=planning_provider or DummyPlanningProvider(),
        vision_analysis_provider=None,
        image_generation_provider=image_provider or CapturingImageProvider(),
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(),
        text_provider_mode=text_mode,
        vision_provider_mode="mock",
        image_provider_mode="mock",
        planning_model_selection=ResolvedModelSelection("planning", "mock", "mock-plan", "mock", "test"),
        vision_model_selection=ResolvedModelSelection("vision", "mock", "mock-vision", "mock", "test"),
        image_model_selection=ResolvedModelSelection("image", "mock", "mock-image", "mock", "test"),
    )
