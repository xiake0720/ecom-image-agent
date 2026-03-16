from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from src.core.paths import ensure_task_dirs, get_task_dir
from src.domain.copy_plan import CopyItem, CopyPlan
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from src.domain.layout_plan import LayoutBlock, LayoutItem, LayoutPlan
from src.domain.product_analysis import ProductAnalysis
from src.domain.qc_report import QCReport
from src.domain.shot_plan import ShotPlan, ShotSpec
from src.domain.task import Task
from src.services.analysis.product_analyzer import build_mock_product_analysis
from src.services.planning.tea_shot_planner import build_tea_shot_plan
from src.services.storage.local_storage import LocalStorageService
from src.workflows.nodes.finalize import finalize
from src.workflows.nodes.overlay_text import overlay_text
from src.workflows.nodes.run_qc import run_qc
from src.workflows.state import WorkflowDependencies


class DummyOCRService:
    def __init__(self, texts: list[str] | None = None) -> None:
        self._texts = texts or []

    def read_text(self, image_path: str) -> list[str]:
        del image_path
        return list(self._texts)


class DummyRenderer:
    pass


class FakeTextRenderer:
    def render_copy(self, *, input_image_path: str, copy_item: CopyItem, layout_item: LayoutItem, output_path: str):
        del input_image_path, copy_item, layout_item
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1440, 1440), color=(255, 255, 255)).save(output_path)
        return SimpleNamespace(
            output_path=output_path,
            font_source="windows_system_font",
            font_loaded=True,
            fallback_used=True,
            requested_font_path="assets/fonts/NotoSansSC-Regular.otf",
            resolved_font_path="C:/Windows/Fonts/msyh.ttc",
            fallback_target="C:/Windows/Fonts/msyh.ttc",
            blocks=[
                SimpleNamespace(
                    kind="title",
                    requested_font_size=64,
                    used_font_size=60,
                    min_font_size_hit=False,
                    line_count=2,
                    x=96,
                    y=88,
                    width=320,
                    height=92,
                    block_width=500,
                    block_height=120,
                    density_ratio=0.74,
                    overflow_detected=False,
                    typography_preset="premium_minimal",
                    text_color=(255, 255, 255, 255),
                    background_plate_applied=False,
                    shadow_applied=True,
                    stroke_applied=False,
                ),
                SimpleNamespace(
                    kind="subtitle",
                    requested_font_size=42,
                    used_font_size=40,
                    min_font_size_hit=False,
                    line_count=1,
                    x=102,
                    y=196,
                    width=280,
                    height=42,
                    block_width=500,
                    block_height=120,
                    density_ratio=0.58,
                    overflow_detected=False,
                    typography_preset="premium_minimal",
                    text_color=(255, 255, 255, 255),
                    background_plate_applied=False,
                    shadow_applied=True,
                    stroke_applied=False,
                ),
            ],
        )


def test_run_qc_adds_structure_dimension_and_new_image_checks() -> None:
    task_id = "task-qc"
    task_dir = _reset_task_dir(task_id)
    image_path = task_dir / "final" / "01_shot-01.png"
    Image.new("RGB", (1440, 1440), color=(255, 255, 255)).save(image_path)
    state, deps = _build_generic_qc_state(task_id=task_id, task_dir=task_dir, image_path=image_path)

    result = run_qc(state, deps)

    report = result["qc_report"]
    assert isinstance(report, QCReport)
    check_names = {check.check_name for check in report.checks}
    assert "task_json_exists" in check_names
    assert "style_architecture_json_exists" in check_names
    assert "shot_prompt_specs_json_exists" in check_names
    assert "task_output_dimension" in check_names
    assert "text_overflow_static_risk" in check_names
    assert "text_background_contrast" in check_names
    assert "text_area_complexity" in check_names
    assert "safe_zone_overlap_risk" in check_names
    assert "shot_completeness_check" in check_names
    assert "product_consistency_check" in check_names
    assert "shot_type_match_check" in check_names
    assert "visual_shot_diversity_check" in check_names
    assert "qc_report_exists" in check_names
    assert report.shot_completeness_check
    assert report.product_consistency_check
    assert report.shot_type_match_check
    assert report.visual_shot_diversity_check
    assert (task_dir / "qc_report.json").exists()


def test_overlay_text_persists_actual_text_regions_json() -> None:
    task_id = "task-overlay-text-regions"
    task_dir = _reset_task_dir(task_id)
    image_path = task_dir / "generated" / "01_shot-01.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1440, 1440), color=(255, 255, 255)).save(image_path)
    task = Task(
        task_id=task_id,
        brand_name="鍝佺墝A",
        product_name="浜у搧A",
        platform="taobao",
        output_size="1440x1440",
        shot_count=1,
        copy_tone="涓撲笟鑷劧",
        task_dir=str(task_dir),
    )
    deps = WorkflowDependencies(
        storage=LocalStorageService(),
        planning_provider=object(),
        vision_analysis_provider=None,
        image_generation_provider=object(),
        text_renderer=FakeTextRenderer(),
        ocr_service=DummyOCRService(),
        text_provider_mode="mock",
        vision_provider_mode="mock",
        image_provider_mode="mock",
    )
    state = {
        "task": task,
        "copy_plan": CopyPlan(items=[CopyItem(shot_id="shot-01", title="标题", subtitle="副标题")]),
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
                    ],
                )
            ]
        ),
        "generation_result": GenerationResult(
            images=[
                GeneratedImage(
                    shot_id="shot-01",
                    image_path=str(image_path),
                    preview_path=str(image_path),
                    width=1440,
                    height=1440,
                    status="generated",
                )
            ]
        ),
        "logs": [],
        "render_variant": "final",
    }

    result = overlay_text(state, deps)

    regions_path = task_dir / "final_text_regions.json"
    assert regions_path.exists()
    payload = json.loads(regions_path.read_text(encoding="utf-8"))
    shot_payload = payload["shots"][0]
    assert shot_payload["shot_id"] == "shot-01"
    assert shot_payload["font_source"] == "windows_system_font"
    assert shot_payload["font_loaded"] is True
    assert shot_payload["fallback_used"] is True
    assert shot_payload["actual_text_regions"]
    assert shot_payload["actual_text_regions"][0]["min_font_size_hit"] is False
    assert shot_payload["merged_text_region"] == {"x": 96, "y": 88, "width": 320, "height": 150}
    assert shot_payload["title_region"]["kind"] == "title"
    assert shot_payload["subtitle_region"]["kind"] == "subtitle"
    assert "text_render_reports" in result


def test_run_qc_warns_for_low_text_background_contrast() -> None:
    task_id = "task-qc-low-contrast"
    task_dir = _reset_task_dir(task_id)
    image_path = task_dir / "final" / "01_shot-01.png"
    Image.new("RGB", (1440, 1440), color=(240, 240, 240)).save(image_path)
    state, deps = _build_generic_qc_state(task_id=task_id, task_dir=task_dir, image_path=image_path)

    result = run_qc(state, deps)

    contrast_check = next(check for check in result["qc_report"].checks if check.check_name == "text_background_contrast")
    assert contrast_check.status == "warning"
    assert "contrast_score=" in contrast_check.details
    readability_check = next(check for check in result["qc_report"].checks if check.check_name == "text_readability_check")
    assert readability_check.status == "warning"
    assert "low_contrast" in readability_check.details


def test_run_qc_warns_when_text_area_overlaps_subject_focus() -> None:
    task_id = "task-qc-text-overlap"
    task_dir = _reset_task_dir(task_id)
    image_path = task_dir / "final" / "01_shot-01.png"
    Image.new("RGB", (1440, 1440), color=(180, 180, 180)).save(image_path)
    state, deps = _build_generic_qc_state(task_id=task_id, task_dir=task_dir, image_path=image_path)
    state["layout_plan"] = LayoutPlan(
        items=[
            LayoutItem(
                shot_id="shot-01",
                canvas_width=1440,
                canvas_height=1440,
                text_safe_zone="right_center",
                blocks=[
                    LayoutBlock(kind="title", x=450, y=460, width=520, height=220, font_size=72),
                    LayoutBlock(kind="subtitle", x=450, y=700, width=520, height=160, font_size=40),
                ],
            )
        ]
    )

    result = run_qc(state, deps)

    safe_zone_check = next(check for check in result["qc_report"].checks if check.check_name == "text_safe_zone_check")
    assert safe_zone_check.status in {"warning", "failed"}
    assert "overlap_ratio=" in safe_zone_check.details


def test_run_qc_uses_actual_text_regions_from_disk_when_state_missing() -> None:
    task_id = "task-qc-actual-text-regions"
    task_dir = _reset_task_dir(task_id)
    image_path = task_dir / "final" / "01_shot-01.png"
    Image.new("RGB", (1440, 1440), color=(180, 180, 180)).save(image_path)
    state, deps = _build_generic_qc_state(task_id=task_id, task_dir=task_dir, image_path=image_path)
    (task_dir / "final_text_regions.json").write_text(
        json.dumps(
            {
                "render_variant": "final",
                "shots": [
                    {
                        "shot_id": "shot-01",
                        "actual_text_regions": [
                            {"kind": "title", "x": 92, "y": 104, "width": 280, "height": 66},
                            {"kind": "subtitle", "x": 96, "y": 188, "width": 260, "height": 42},
                        ],
                        "merged_text_region": {"x": 92, "y": 104, "width": 280, "height": 126},
                        "title_region": {"kind": "title", "x": 92, "y": 104, "width": 280, "height": 66},
                        "subtitle_region": {"kind": "subtitle", "x": 96, "y": 188, "width": 260, "height": 42},
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_qc(state, deps)

    safe_zone_check = next(check for check in result["qc_report"].checks if check.check_name == "text_safe_zone_check")
    assert "actual_render_region=yes" in safe_zone_check.details
    assert "region_source=actual" in safe_zone_check.details
    assert "text_rect=(92, 104, 280, 126)" in safe_zone_check.details


def test_run_qc_fails_when_text_overflow_info_exists() -> None:
    task_id = "task-qc-text-overflow"
    task_dir = _reset_task_dir(task_id)
    image_path = task_dir / "final" / "01_shot-01.png"
    Image.new("RGB", (1440, 1440), color=(220, 220, 220)).save(image_path)
    state, deps = _build_generic_qc_state(task_id=task_id, task_dir=task_dir, image_path=image_path)
    state["text_render_reports"] = {
        "shot-01": {
            "output_path": str(image_path),
            "blocks": [
                {
                    "kind": "title",
                    "requested_font_size": 80,
                    "used_font_size": 18,
                    "min_font_size_hit": True,
                    "line_count": 6,
                    "x": 80,
                    "y": 80,
                    "width": 520,
                    "height": 220,
                    "block_width": 520,
                    "block_height": 220,
                    "density_ratio": 1.08,
                    "overflow_detected": True,
                    "typography_preset": "premium_minimal",
                    "text_color": [255, 255, 255, 255],
                    "background_plate_applied": False,
                    "shadow_applied": False,
                    "stroke_applied": False,
                }
            ],
        }
    }

    result = run_qc(state, deps)

    readability_check = next(check for check in result["qc_report"].checks if check.check_name == "text_readability_check")
    assert readability_check.status == "failed"
    assert "text_overflow_detected" in readability_check.details


def test_run_qc_warns_when_used_font_size_is_below_commercial_threshold() -> None:
    task_id = "task-qc-small-font"
    task_dir = _reset_task_dir(task_id)
    image_path = task_dir / "final" / "01_shot-01.png"
    Image.new("RGB", (1440, 1440), color=(210, 210, 210)).save(image_path)
    state, deps = _build_generic_qc_state(task_id=task_id, task_dir=task_dir, image_path=image_path)
    state["text_render_reports"] = {
        "shot-01": {
            "output_path": str(image_path),
            "merged_text_region": {"x": 120, "y": 100, "width": 180, "height": 72},
            "blocks": [
                {
                    "kind": "title",
                    "requested_font_size": 64,
                    "used_font_size": 34,
                    "min_font_size_hit": True,
                    "line_count": 2,
                    "x": 120,
                    "y": 100,
                    "width": 180,
                    "height": 40,
                    "block_width": 500,
                    "block_height": 120,
                    "density_ratio": 0.82,
                    "overflow_detected": False,
                },
                {
                    "kind": "subtitle",
                    "requested_font_size": 42,
                    "used_font_size": 20,
                    "min_font_size_hit": True,
                    "line_count": 1,
                    "x": 124,
                    "y": 150,
                    "width": 170,
                    "height": 24,
                    "block_width": 500,
                    "block_height": 120,
                    "density_ratio": 0.64,
                    "overflow_detected": False,
                },
            ],
        }
    }

    result = run_qc(state, deps)

    readability_check = next(check for check in result["qc_report"].checks if check.check_name == "text_readability_check")
    assert readability_check.status in {"warning", "failed"}
    assert "title_below_min_readable_size" in readability_check.details or "title_far_below_min_readable_size" in readability_check.details
    assert "subtitle_below_min_readable_size" in readability_check.details or "subtitle_far_below_min_readable_size" in readability_check.details
    assert "merged_text_region_ratio=" in readability_check.details
    assert "used_font_sizes=" in readability_check.details


def test_run_qc_falls_back_to_layout_when_actual_text_regions_missing() -> None:
    task_id = "task-qc-fallback-text-region"
    task_dir = _reset_task_dir(task_id)
    image_path = task_dir / "final" / "01_shot-01.png"
    Image.new("RGB", (1440, 1440), color=(220, 220, 220)).save(image_path)
    state, deps = _build_generic_qc_state(task_id=task_id, task_dir=task_dir, image_path=image_path)

    result = run_qc(state, deps)

    safe_zone_check = next(check for check in result["qc_report"].checks if check.check_name == "text_safe_zone_check")
    assert "actual_render_region=no" in safe_zone_check.details
    assert "region_source=fallback" in safe_zone_check.details


def test_run_qc_fails_when_final_tea_phase1_has_fewer_than_five_images() -> None:
    task_id = "task-qc-tea-final-missing-shot"
    task_dir = _reset_task_dir(task_id)
    state, deps = _build_tea_phase1_qc_state(task_id=task_id, task_dir=task_dir, image_count=4)

    result = run_qc(state, deps)

    completeness_check = next(check for check in result["qc_report"].checks if check.check_name == "shot_completeness_check")
    assert completeness_check.status == "failed"
    assert "missing_shots=" in completeness_check.details
    assert result["qc_report"].passed is False


def test_run_qc_warns_or_fails_when_image_edit_has_no_reference_assets() -> None:
    task_id = "task-qc-image-edit-no-refs"
    task_dir = _reset_task_dir(task_id)
    state, deps = _build_generic_qc_state(
        task_id=task_id,
        task_dir=task_dir,
        image_path=task_dir / "final" / "01_shot-01.png",
        image_color=(180, 30, 30),
    )
    state["image_prompt_plan"] = ImagePromptPlan(
        generation_mode="image_edit",
        prompts=[
            ImagePrompt(
                shot_id="shot-01",
                shot_type="hero_brand",
                generation_mode="image_edit",
                prompt="legacy prompt",
                edit_instruction="edit the reference package image",
                output_size="1440x1440",
            )
        ],
    )
    state["render_generation_mode"] = "image_edit"
    state["render_reference_asset_ids"] = []

    result = run_qc(state, deps)

    consistency_check = next(check for check in result["qc_report"].checks if check.check_name == "product_consistency_check")
    assert consistency_check.status == "failed"
    assert consistency_check.evidence_completeness in {"partial", "missing"}
    assert "image_edit_expected_but_reference_assets_missing" in consistency_check.details
    assert "evidence_completeness=" in consistency_check.details


def test_run_qc_does_not_pass_product_consistency_without_evidence() -> None:
    task_id = "task-qc-product-consistency-no-evidence"
    task_dir = _reset_task_dir(task_id)
    state, deps = _build_generic_qc_state(
        task_id=task_id,
        task_dir=task_dir,
        image_path=task_dir / "final" / "01_shot-01.png",
        image_color=(180, 180, 180),
        ocr_texts=[],
        primary_color="",
    )
    deps.ocr_service = DummyOCRService([])
    state["product_analysis"] = state["product_analysis"].model_copy(
        update={
            "must_preserve_texts": [],
            "locked_elements": [],
            "text_anchor_source": "none",
            "text_anchor_status": "unreadable",
            "primary_color": "",
        }
    )

    result = run_qc(state, deps)

    consistency_check = next(check for check in result["qc_report"].checks if check.check_name == "product_consistency_check")
    assert consistency_check.status in {"warning", "failed"}
    assert consistency_check.status != "passed"
    assert consistency_check.evidence_completeness == "missing"
    assert "brand_text_targets=['none']" in consistency_check.details
    assert "text_anchor_source=none" in consistency_check.details
    assert "text_anchor_status=unreadable" in consistency_check.details
    assert "ocr_texts=['none']" in consistency_check.details
    assert "primary_color_detected=None" in consistency_check.details
    assert "decision_reason=no_reliable_product_evidence_available" in consistency_check.details


def test_run_qc_marks_partial_product_evidence_as_warning() -> None:
    task_id = "task-qc-product-consistency-partial-evidence"
    task_dir = _reset_task_dir(task_id)
    state, deps = _build_generic_qc_state(
        task_id=task_id,
        task_dir=task_dir,
        image_path=task_dir / "final" / "01_shot-01.png",
        image_color=(180, 30, 30),
        ocr_texts=["閸濅胶澧滱"],
        primary_color="",
    )

    result = run_qc(state, deps)

    consistency_check = next(check for check in result["qc_report"].checks if check.check_name == "product_consistency_check")
    assert consistency_check.status == "warning"
    assert consistency_check.evidence_completeness == "partial"
    assert "text_anchor_count=1" in consistency_check.details
    assert "decision_reason=partial_product_evidence_only" in consistency_check.details


def test_run_qc_builds_shot_type_match_summary_for_tea_phase1() -> None:
    task_id = "task-qc-shot-type-summary"
    task_dir = _reset_task_dir(task_id)
    state, deps = _build_tea_phase1_qc_state(task_id=task_id, task_dir=task_dir, image_count=5)

    result = run_qc(state, deps)

    assert len(result["qc_report"].shot_type_match_check) == 5
    related_ids = {item.related_shot_id for item in result["qc_report"].shot_type_match_check}
    assert related_ids == {"shot_01", "shot_02", "shot_03", "shot_04", "shot_05"}
    assert len(result["qc_report"].visual_shot_diversity_check) == 1
    assert len(result["qc_report"].text_safe_zone_check) == 5
    assert len(result["qc_report"].text_readability_check) == 5


def test_run_qc_warns_when_five_shots_are_visually_too_similar() -> None:
    task_id = "task-qc-low-diversity"
    task_dir = _reset_task_dir(task_id)
    state, deps = _build_tea_phase1_qc_state(task_id=task_id, task_dir=task_dir, image_count=5)

    result = run_qc(state, deps)

    diversity_check = next(check for check in result["qc_report"].checks if check.check_name == "visual_shot_diversity_check")
    assert diversity_check.status == "warning"
    assert "similar_pairs=" in diversity_check.details
    assert "hero_like_shots=" in diversity_check.details


def test_run_qc_shot_type_match_uses_image_signals_not_only_prompt_metadata() -> None:
    task_id = "task-qc-shot-visual-rules"
    task_dir = _reset_task_dir(task_id)
    state, deps = _build_tea_tin_can_qc_state(task_id=task_id, task_dir=task_dir, image_count=5)

    result = run_qc(state, deps)

    shot_type_checks = {
        check.related_shot_id: check
        for check in result["qc_report"].checks
        if check.check_name == "shot_type_match_check"
    }
    assert shot_type_checks["shot_02"].status == "warning"
    assert "package_detail_too_similar_to_hero" in shot_type_checks["shot_02"].details
    assert shot_type_checks["shot_03"].status == "warning"
    assert "dry_leaf_texture_signal_weak" in shot_type_checks["shot_03"].details
    assert shot_type_checks["shot_04"].status == "warning"
    assert "tea_soup_visual_signal_weak" in shot_type_checks["shot_04"].details
    assert shot_type_checks["shot_05"].status == "warning"
    assert "visual_warnings=" in shot_type_checks["shot_05"].details


def test_different_shots_do_not_share_identical_text_rect_when_actual_regions_exist() -> None:
    task_id = "task-qc-different-text-rects"
    task_dir = _reset_task_dir(task_id)
    state, deps = _build_tea_phase1_qc_state(task_id=task_id, task_dir=task_dir, image_count=5)
    state["text_render_reports"] = {
        "shot_01": _build_text_region_report(80, 90, 340, 140),
        "shot_02": _build_text_region_report(110, 120, 300, 120),
        "shot_03": _build_text_region_report(140, 150, 320, 136),
        "shot_04": _build_text_region_report(170, 180, 280, 112),
        "shot_05": _build_text_region_report(200, 210, 360, 132),
    }

    result = run_qc(state, deps)

    details_list = [
        check.details
        for check in result["qc_report"].checks
        if check.check_name == "text_safe_zone_check"
    ]
    text_rects = {
        re.search(r"text_rect=\(([^)]*)\)", details).group(1)
        for details in details_list
    }
    assert len(text_rects) == 5
    assert all("actual_render_region=yes" in details for details in details_list)


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
        "style_architecture.json",
        "shot_plan.json",
        "copy_plan.json",
        "layout_plan.json",
        "shot_prompt_specs.json",
        "image_prompt_plan.json",
        "qc_report.json",
    ]:
        (task_dir / filename).write_text("{}", encoding="utf-8")
    task = Task(
        task_id=task_id,
        brand_name="鍝佺墝A",
        product_name="浜у搧A",
        platform="taobao",
        output_size="1440x1440",
        shot_count=1,
        copy_tone="涓撲笟鑷劧",
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


def _build_generic_qc_state(
    *,
    task_id: str,
    task_dir: Path,
    image_path: Path,
    image_color: tuple[int, int, int] = (255, 255, 255),
    ocr_texts: list[str] | None = None,
    primary_color: str = "red",
) -> tuple[dict, WorkflowDependencies]:
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1440, 1440), color=image_color).save(image_path)
    task = Task(
        task_id=task_id,
        brand_name="鍝佺墝A",
        product_name="浜у搧A",
        platform="taobao",
        output_size="1440x1440",
        shot_count=1,
        copy_tone="涓撲笟鑷劧",
        task_dir=str(task_dir),
    )
    storage = LocalStorageService()
    storage.save_task_manifest(task)
    for filename in [
        "product_analysis.json",
        "style_architecture.json",
        "shot_plan.json",
        "copy_plan.json",
        "layout_plan.json",
        "shot_prompt_specs.json",
        "image_prompt_plan.json",
    ]:
        (task_dir / filename).write_text("{}", encoding="utf-8")
    deps = WorkflowDependencies(
        storage=storage,
        planning_provider=object(),
        vision_analysis_provider=None,
        image_generation_provider=object(),
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(["品牌A"]),
        text_provider_mode="mock",
        vision_provider_mode="mock",
        image_provider_mode="mock",
    )
    analysis = build_mock_product_analysis([], task.product_name).model_copy(
        update={
            "primary_color": primary_color,
            "must_preserve_texts": ["鍝佺墝A"],
            "locked_elements": ["front package hero"],
        }
    )
    state = {
        "task": task,
        "product_analysis": analysis,
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
                    shot_type="hero_brand",
                    goal="show package as hero",
                    focus="package",
                    scene_direction="clean premium product scene",
                    composition_direction="package centered with copy zone",
                    required_subjects=["package hero"],
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
                    shot_type="hero_brand",
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


def _build_tea_phase1_qc_state(*, task_id: str, task_dir: Path, image_count: int) -> tuple[dict, WorkflowDependencies]:
    task = Task(
        task_id=task_id,
        brand_name="鍝佺墝A",
        product_name="鍑ゅ嚢鍗曚笡绀肩洅",
        platform="taobao",
        output_size="1440x1440",
        shot_count=5,
        copy_tone="楂樼绀艰禒",
        task_dir=str(task_dir),
    )
    storage = LocalStorageService()
    storage.save_task_manifest(task)
    for filename in [
        "product_analysis.json",
        "style_architecture.json",
        "shot_plan.json",
        "copy_plan.json",
        "layout_plan.json",
        "shot_prompt_specs.json",
        "image_prompt_plan.json",
    ]:
        (task_dir / filename).write_text("{}", encoding="utf-8")

    analysis = build_mock_product_analysis([], task.product_name).model_copy(
        update={
            "category": "tea_gift_box",
            "primary_color": "red",
            "must_preserve_texts": ["鍝佺墝A"],
            "locked_elements": ["gift box structure", "front label"],
        }
    )
    shot_plan = build_tea_shot_plan(task, analysis)
    copy_items = []
    layout_items = []
    prompt_items = []
    generated_images = []
    for index, shot in enumerate(shot_plan.shots[:image_count], start=1):
        image_path = task_dir / "final" / f"{index:02d}_{shot.shot_id}.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1440, 1440), color=(180, 40, 40)).save(image_path)
        copy_items.append(
            CopyItem(
                shot_id=shot.shot_id,
                title=shot.title,
                subtitle=shot.purpose,
                bullets=[shot.copy_goal],
            )
        )
        layout_items.append(
            LayoutItem(
                shot_id=shot.shot_id,
                canvas_width=1440,
                canvas_height=1440,
                text_safe_zone=("top_right" if shot.preferred_text_safe_zone == "top" else shot.preferred_text_safe_zone or "top_right"),
                blocks=[
                    LayoutBlock(kind="title", x=80, y=80, width=520, height=120, font_size=64),
                    LayoutBlock(kind="subtitle", x=80, y=220, width=520, height=120, font_size=42),
                ],
            )
        )
        prompt_items.append(
            ImagePrompt(
                shot_id=shot.shot_id,
                shot_type=shot.shot_type,
                generation_mode="image_edit" if shot.shot_type in {"hero_brand", "open_box_structure"} else "t2i",
                prompt=shot.goal or shot.purpose,
                edit_instruction=f"edit for {shot.shot_type}",
                output_size="1440x1440",
            )
        )
        generated_images.append(
            GeneratedImage(
                shot_id=shot.shot_id,
                image_path=str(image_path),
                preview_path=str(image_path),
                width=1440,
                height=1440,
                status="finalized",
            )
        )

    deps = WorkflowDependencies(
        storage=storage,
        planning_provider=object(),
        vision_analysis_provider=None,
        image_generation_provider=object(),
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(["品牌A"]),
        text_provider_mode="mock",
        vision_provider_mode="mock",
        image_provider_mode="mock",
    )
    state = {
        "task": task,
        "product_analysis": analysis,
        "copy_plan": CopyPlan(items=copy_items),
        "shot_plan": shot_plan,
        "layout_plan": LayoutPlan(items=layout_items),
        "image_prompt_plan": ImagePromptPlan(generation_mode="image_edit", prompts=prompt_items),
        "generation_result": GenerationResult(images=generated_images),
        "logs": [],
        "render_variant": "final",
        "render_generation_mode": "image_edit",
        "render_reference_asset_ids": ["asset-main"],
    }
    return state, deps


def _build_tea_tin_can_qc_state(*, task_id: str, task_dir: Path, image_count: int) -> tuple[dict, WorkflowDependencies]:
    task = Task(
        task_id=task_id,
        brand_name="品牌A",
        product_name="凤凰单丛铁罐",
        platform="taobao",
        output_size="1440x1440",
        shot_count=5,
        copy_tone="高端礼赠",
        task_dir=str(task_dir),
    )
    storage = LocalStorageService()
    storage.save_task_manifest(task)
    for filename in [
        "product_analysis.json",
        "style_architecture.json",
        "shot_plan.json",
        "copy_plan.json",
        "layout_plan.json",
        "shot_prompt_specs.json",
        "image_prompt_plan.json",
    ]:
        (task_dir / filename).write_text("{}", encoding="utf-8")

    analysis = build_mock_product_analysis([], task.product_name).model_copy(
        update={
            "category": "tea",
            "package_template_family": "tea_tin_can",
            "asset_completeness_mode": "packshot_plus_detail",
            "primary_color": "red",
            "must_preserve_texts": ["品牌A"],
            "locked_elements": ["tin can silhouette", "front label"],
        }
    )
    shot_plan = build_tea_shot_plan(task, analysis)
    copy_items = []
    layout_items = []
    prompt_items = []
    generated_images = []
    for index, shot in enumerate(shot_plan.shots[:image_count], start=1):
        image_path = task_dir / "final" / f"{index:02d}_{shot.shot_id}.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1440, 1440), color=(180, 40, 40)).save(image_path)
        copy_items.append(CopyItem(shot_id=shot.shot_id, title=shot.title, subtitle=shot.purpose, bullets=[shot.copy_goal]))
        layout_items.append(
            LayoutItem(
                shot_id=shot.shot_id,
                canvas_width=1440,
                canvas_height=1440,
                text_safe_zone=("top_right" if shot.preferred_text_safe_zone == "top" else shot.preferred_text_safe_zone or "top_right"),
                blocks=[
                    LayoutBlock(kind="title", x=80, y=80, width=520, height=120, font_size=64),
                    LayoutBlock(kind="subtitle", x=80, y=220, width=520, height=120, font_size=42),
                ],
            )
        )
        prompt_items.append(
            ImagePrompt(
                shot_id=shot.shot_id,
                shot_type=shot.shot_type,
                generation_mode="image_edit" if shot.shot_type in {"hero_brand", "package_detail"} else "t2i",
                prompt=shot.goal or shot.purpose,
                edit_instruction=f"edit for {shot.shot_type}",
                output_size="1440x1440",
            )
        )
        generated_images.append(
            GeneratedImage(
                shot_id=shot.shot_id,
                image_path=str(image_path),
                preview_path=str(image_path),
                width=1440,
                height=1440,
                status="finalized",
            )
        )

    deps = WorkflowDependencies(
        storage=storage,
        planning_provider=object(),
        vision_analysis_provider=None,
        image_generation_provider=object(),
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(["品牌A"]),
        text_provider_mode="mock",
        vision_provider_mode="mock",
        image_provider_mode="mock",
    )
    state = {
        "task": task,
        "product_analysis": analysis,
        "copy_plan": CopyPlan(items=copy_items),
        "shot_plan": shot_plan,
        "layout_plan": LayoutPlan(items=layout_items),
        "image_prompt_plan": ImagePromptPlan(generation_mode="image_edit", prompts=prompt_items),
        "generation_result": GenerationResult(images=generated_images),
        "logs": [],
        "render_variant": "final",
        "render_generation_mode": "image_edit",
        "render_reference_asset_ids": ["asset-main"],
    }
    return state, deps


def _build_text_region_report(x: int, y: int, width: int, height: int) -> dict:
    return {
        "shot_id": f"shot-{x}",
        "font_source": "windows_system_font",
        "font_loaded": True,
        "fallback_used": False,
        "actual_text_regions": [
            {"kind": "title", "x": x, "y": y, "width": width, "height": int(height * 0.56), "min_font_size_hit": False},
            {"kind": "subtitle", "x": x + 8, "y": y + int(height * 0.62), "width": width - 16, "height": int(height * 0.28), "min_font_size_hit": False},
        ],
        "merged_text_region": {"x": x, "y": y, "width": width, "height": height},
        "title_region": {"kind": "title", "x": x, "y": y, "width": width, "height": int(height * 0.56), "min_font_size_hit": False},
        "subtitle_region": {"kind": "subtitle", "x": x + 8, "y": y + int(height * 0.62), "width": width - 16, "height": int(height * 0.28), "min_font_size_hit": False},
    }

