from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

from src.core.paths import ensure_task_dirs, get_task_dir
from src.domain.copy_plan import CopyItem, CopyPlan
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from src.domain.layout_plan import LayoutBlock, LayoutItem, LayoutPlan
from src.domain.qc_report import QCReport
from src.domain.shot_plan import ShotPlan, ShotSpec
from src.domain.task import Task
from src.services.storage.local_storage import LocalStorageService
from src.workflows.nodes.finalize import finalize
from src.workflows.nodes.run_qc import run_qc
from src.workflows.state import WorkflowDependencies


class DummyOCRService:
    def read_text(self, image_path: str) -> list[str]:
        return []


class DummyRenderer:
    pass


def test_run_qc_adds_structure_dimension_and_text_overflow_checks() -> None:
    task_id = "task-qc"
    task_dir = _reset_task_dir(task_id)
    image_path = task_dir / "final" / "01_shot-01.png"
    Image.new("RGB", (1440, 1440), color=(255, 255, 255)).save(image_path)
    task = Task(
        task_id=task_id,
        brand_name="品牌A",
        product_name="产品A",
        platform="taobao",
        output_size="1440x1440",
        shot_count=1,
        copy_tone="专业自然",
        task_dir=str(task_dir),
    )
    storage = LocalStorageService()
    storage.save_task_manifest(task)
    for filename in [
        "product_analysis.json",
        "shot_plan.json",
        "copy_plan.json",
        "layout_plan.json",
        "image_prompt_plan.json",
    ]:
        (task_dir / filename).write_text("{}", encoding="utf-8")

    deps = WorkflowDependencies(
        storage=storage,
        planning_provider=object(),
        vision_analysis_provider=None,
        image_generation_provider=object(),
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(),
        text_provider_mode="mock",
        vision_provider_mode="mock",
        image_provider_mode="mock",
    )
    state = {
        "task": task,
        "copy_plan": CopyPlan(
            items=[
                CopyItem(
                    shot_id="shot-01",
                    title="短标题",
                    subtitle="短副标题",
                    bullets=["卖点一", "卖点二"],
                )
            ]
        ),
        "shot_plan": ShotPlan(
            shots=[
                ShotSpec(
                    shot_id="shot-01",
                    title="主图",
                    purpose="展示主包装",
                    composition_hint="主体居中，右侧留白",
                    copy_goal="突出品牌",
                )
            ]
        ),
        "layout_plan": LayoutPlan(
            items=[
                LayoutItem(
                    shot_id="shot-01",
                    canvas_width=1440,
                    canvas_height=1440,
                    text_safe_zone="top_left",
                    blocks=[
                        LayoutBlock(kind="title", x=80, y=80, width=500, height=120, font_size=64),
                        LayoutBlock(kind="subtitle", x=80, y=220, width=500, height=120, font_size=42),
                        LayoutBlock(kind="bullets", x=80, y=360, width=500, height=220, font_size=34),
                    ],
                )
            ]
        ),
        "image_prompt_plan": ImagePromptPlan(
            generation_mode="t2i",
            prompts=[
                ImagePrompt(
                    shot_id="shot-01",
                    shot_type="hero",
                    generation_mode="t2i",
                    prompt="premium product image",
                    output_size="1440x1440",
                )
            ],
        ),
        "generation_result": GenerationResult(
            images=[
                GeneratedImage(
                    shot_id="shot-01",
                    image_path=str(image_path),
                    preview_path=str(image_path),
                    width=1440,
                    height=1440,
                    status="finalized",
                )
            ]
        ),
        "logs": [],
        "render_variant": "final",
        "render_generation_mode": "t2i",
        "render_reference_asset_ids": [],
    }

    result = run_qc(state, deps)

    report = result["qc_report"]
    assert isinstance(report, QCReport)
    check_names = {check.check_name for check in report.checks}
    assert "task_json_exists" in check_names
    assert "generated_dir_exists" in check_names
    assert "task_output_dimension" in check_names
    assert "text_overflow_static_risk" in check_names
    assert "text_background_contrast" in check_names
    assert "text_area_complexity" in check_names
    assert "safe_zone_overlap_risk" in check_names
    assert "product_consistency_risk" in check_names
    assert "qc_report_exists" in check_names
    assert (task_dir / "qc_report.json").exists()
    assert report.passed is True
    assert report.review_required is True


def test_run_qc_warns_for_low_text_background_contrast() -> None:
    task_id = "task-qc-low-contrast"
    task_dir = _reset_task_dir(task_id)
    image_path = task_dir / "final" / "01_shot-01.png"
    Image.new("RGB", (1440, 1440), color=(240, 240, 240)).save(image_path)
    state, deps = _build_qc_state(task_id=task_id, task_dir=task_dir, image_path=image_path)

    result = run_qc(state, deps)

    contrast_check = next(check for check in result["qc_report"].checks if check.check_name == "text_background_contrast")
    assert contrast_check.status == "warning"
    assert "contrast_score=" in contrast_check.details


def test_run_qc_warns_when_generation_mode_and_render_route_mismatch() -> None:
    task_id = "task-qc-mode-mismatch"
    task_dir = _reset_task_dir(task_id)
    image_path = task_dir / "final" / "01_shot-01.png"
    Image.new("RGB", (1440, 1440), color=(255, 255, 255)).save(image_path)
    state, deps = _build_qc_state(task_id=task_id, task_dir=task_dir, image_path=image_path)
    state["image_prompt_plan"] = ImagePromptPlan(
        generation_mode="image_edit",
        prompts=[
            ImagePrompt(
                shot_id="shot-01",
                shot_type="hero",
                generation_mode="image_edit",
                prompt="keep the original package",
                edit_instruction="edit the reference product image",
                output_size="1440x1440",
            )
        ],
    )
    state["render_generation_mode"] = "t2i"
    state["render_reference_asset_ids"] = []

    result = run_qc(state, deps)

    consistency_check = next(check for check in result["qc_report"].checks if check.check_name == "product_consistency_risk")
    assert consistency_check.status == "warning"
    assert "expected_image_edit_but_actual_t2i" in consistency_check.details


def test_finalize_exports_final_zip_and_full_task_bundle() -> None:
    task_id = "task-finalize"
    task_dir = _reset_task_dir(task_id)
    (task_dir / "inputs" / "input.png").write_bytes(b"input")
    (task_dir / "generated" / "gen.png").write_bytes(b"generated")
    (task_dir / "final" / "final.png").write_bytes(b"final")
    (task_dir / "previews" / "preview.png").write_bytes(b"preview")
    for filename in [
        "task.json",
        "product_analysis.json",
        "shot_plan.json",
        "copy_plan.json",
        "layout_plan.json",
        "image_prompt_plan.json",
        "qc_report.json",
    ]:
        (task_dir / filename).write_text("{}", encoding="utf-8")
    task = Task(
        task_id=task_id,
        brand_name="品牌A",
        product_name="产品A",
        platform="taobao",
        output_size="1440x1440",
        shot_count=1,
        copy_tone="专业自然",
        task_dir=str(task_dir),
    )
    deps = WorkflowDependencies(
        storage=LocalStorageService(),
        planning_provider=object(),
        vision_analysis_provider=None,
        image_generation_provider=object(),
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(),
        text_provider_mode="mock",
        vision_provider_mode="mock",
        image_provider_mode="mock",
    )
    state = {
        "task": task,
        "qc_report": QCReport(passed=True, review_required=False, checks=[]),
        "logs": [],
        "render_variant": "final",
    }

    result = finalize(state, deps)

    final_zip = Path(result["export_zip_path"])
    bundle_zip = Path(result["full_task_bundle_zip_path"])
    assert final_zip.exists()
    assert bundle_zip.exists()
    assert final_zip.name.endswith("final_images.zip")
    assert bundle_zip.name.endswith("full_task_bundle.zip")


def _reset_task_dir(task_id: str) -> Path:
    task_dir = get_task_dir(task_id)
    if task_dir.exists():
        shutil.rmtree(task_dir)
    ensure_task_dirs(task_id)
    return task_dir


def _build_qc_state(*, task_id: str, task_dir: Path, image_path: Path) -> tuple[dict, WorkflowDependencies]:
    task = Task(
        task_id=task_id,
        brand_name="品牌A",
        product_name="产品A",
        platform="taobao",
        output_size="1440x1440",
        shot_count=1,
        copy_tone="专业自然",
        task_dir=str(task_dir),
    )
    storage = LocalStorageService()
    storage.save_task_manifest(task)
    for filename in [
        "product_analysis.json",
        "shot_plan.json",
        "copy_plan.json",
        "layout_plan.json",
        "image_prompt_plan.json",
    ]:
        (task_dir / filename).write_text("{}", encoding="utf-8")
    deps = WorkflowDependencies(
        storage=storage,
        planning_provider=object(),
        vision_analysis_provider=None,
        image_generation_provider=object(),
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(),
        text_provider_mode="mock",
        vision_provider_mode="mock",
        image_provider_mode="mock",
    )
    state = {
        "task": task,
        "copy_plan": CopyPlan(
            items=[
                CopyItem(
                    shot_id="shot-01",
                    title="标题",
                    subtitle="副标题",
                    bullets=["卖点一", "卖点二"],
                )
            ]
        ),
        "shot_plan": ShotPlan(
            shots=[
                ShotSpec(
                    shot_id="shot-01",
                    title="主图",
                    purpose="展示主包装",
                    composition_hint="主体居中，右侧留白",
                    copy_goal="突出品牌",
                )
            ]
        ),
        "layout_plan": LayoutPlan(
            items=[
                LayoutItem(
                    shot_id="shot-01",
                    canvas_width=1440,
                    canvas_height=1440,
                    text_safe_zone="top_left",
                    blocks=[
                        LayoutBlock(kind="title", x=80, y=80, width=500, height=120, font_size=64),
                        LayoutBlock(kind="subtitle", x=80, y=220, width=500, height=120, font_size=42),
                        LayoutBlock(kind="bullets", x=80, y=360, width=500, height=220, font_size=34),
                    ],
                )
            ]
        ),
        "image_prompt_plan": ImagePromptPlan(
            generation_mode="t2i",
            prompts=[
                ImagePrompt(
                    shot_id="shot-01",
                    shot_type="hero",
                    generation_mode="t2i",
                    prompt="premium product image",
                    output_size="1440x1440",
                )
            ],
        ),
        "generation_result": GenerationResult(
            images=[
                GeneratedImage(
                    shot_id="shot-01",
                    image_path=str(image_path),
                    preview_path=str(image_path),
                    width=1440,
                    height=1440,
                    status="finalized",
                )
            ]
        ),
        "logs": [],
        "render_variant": "final",
        "render_generation_mode": "t2i",
        "render_reference_asset_ids": [],
    }
    return state, deps
