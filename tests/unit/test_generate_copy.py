from __future__ import annotations

from pathlib import Path

from src.core.config import ResolvedModelSelection
from src.core.paths import get_task_dir
from src.domain.copy_plan import CopyItem, CopyPlan
from src.domain.shot_plan import ShotPlan, ShotSpec
from src.domain.task import Task
from src.services.analysis.product_analyzer import build_mock_product_analysis
from src.services.planning.copy_generator import build_mock_copy_plan
from src.services.storage.local_storage import LocalStorageService
from src.workflows.nodes.generate_copy import (
    SUBTITLE_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    _normalize_copy_plan_for_overlay,
    generate_copy,
)
from src.workflows.state import WorkflowDependencies


class DummyPlanningProvider:
    last_response_status_code = 200
    last_response_metadata = {}


class DummyRenderer:
    pass


class DummyOCRService:
    pass


def test_normalize_copy_plan_shortens_long_copy_and_blocks_brand_drift() -> None:
    task = _build_task("task-copy-normalize")
    analysis = build_mock_product_analysis([], task.product_name)
    shot_plan = ShotPlan(
        shots=[
            ShotSpec(
                shot_id="shot_01",
                title="主图",
                purpose="突出品牌",
                composition_hint="主体居中",
                copy_goal="突出品牌感",
                shot_type="hero_brand",
            )
        ]
    )
    original_plan = CopyPlan(
        items=[
            CopyItem(
                shot_id="shot_01",
                title="“云岭典藏”高山好茶礼赠之选让你一眼记住",
                subtitle="宛如山间晨雾般轻柔的茶香体验，带来更完整的品牌故事表达",
                bullets=["卖点一很长很长", "卖点二继续展开"],
                cta="立即抢购",
            )
        ]
    )

    normalized_plan, reports = _normalize_copy_plan_for_overlay(
        copy_plan=original_plan,
        shot_plan=shot_plan,
        task=task,
        product_analysis=analysis,
    )

    item = normalized_plan.items[0]
    report = reports[0]

    assert len(item.title) <= TITLE_MAX_LENGTH
    assert len(item.subtitle) <= SUBTITLE_MAX_LENGTH
    assert item.bullets == []
    assert item.cta is None
    assert report.copy_shortened is True
    assert report.brand_anchor_valid is False


def test_build_mock_copy_plan_prefers_short_overlay_copy() -> None:
    task = _build_task("task-copy-mock")
    shot_plan = ShotPlan(
        shots=[
            ShotSpec(
                shot_id="shot_01",
                title="主图",
                purpose="突出品牌",
                composition_hint="主体居中",
                copy_goal="突出品牌感",
                shot_type="hero_brand",
            ),
            ShotSpec(
                shot_id="shot_02",
                title="细节图",
                purpose="突出细节",
                composition_hint="局部近景",
                copy_goal="工艺卖点",
                shot_type="package_detail",
            ),
        ]
    )

    plan = build_mock_copy_plan(task, shot_plan)

    assert len(plan.items) == 2
    assert all(len(item.title) <= TITLE_MAX_LENGTH for item in plan.items)
    assert all(len(item.subtitle) <= SUBTITLE_MAX_LENGTH for item in plan.items)
    assert all(item.bullets == [] for item in plan.items)
    assert all(item.cta is None for item in plan.items)


def test_generate_copy_logs_normalization_metadata(tmp_path: Path) -> None:
    task = _build_task(f"task-copy-node-{tmp_path.name}")
    storage = LocalStorageService()
    deps = WorkflowDependencies(
        storage=storage,
        planning_provider=DummyPlanningProvider(),
        vision_analysis_provider=None,
        image_generation_provider=object(),
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(),
        text_provider_mode="mock",
        vision_provider_mode="mock",
        image_provider_mode="mock",
        planning_model_selection=ResolvedModelSelection("planning", "mock", "mock-plan", "mock", "test"),
        vision_model_selection=ResolvedModelSelection("vision", "mock", "mock-vision", "mock", "test"),
    )
    shot_plan = ShotPlan(
        shots=[
            ShotSpec(
                shot_id="shot_01",
                title="主图",
                purpose="突出品牌",
                composition_hint="主体居中",
                copy_goal="突出品牌感",
                shot_type="hero_brand",
            )
        ]
    )
    state = {
        "task": task,
        "product_analysis": build_mock_product_analysis([], task.product_name),
        "shot_plan": shot_plan,
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }

    result = generate_copy(state, deps)

    assert result["copy_plan"].items[0].title
    assert any("original_length=" in line for line in result["logs"])
    assert any("normalized_length=" in line for line in result["logs"])
    assert any("copy_shortened=" in line for line in result["logs"])
    assert any("brand_anchor_valid=" in line for line in result["logs"])
    assert (get_task_dir(task.task_id) / "copy_plan.json").exists()


def _build_task(task_id: str) -> Task:
    return Task(
        task_id=task_id,
        brand_name="品牌A",
        product_name="高山乌龙茶礼盒",
        platform="taobao",
        output_size="1440x1440",
        shot_count=5,
        copy_tone="简洁高级",
        task_dir=str(get_task_dir(task_id)),
    )
