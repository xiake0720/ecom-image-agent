from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from src.core.config import ResolvedModelSelection
from src.domain.asset import Asset, AssetType
from src.domain.director_output import DirectorOutput, DirectorShot
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.domain.prompt_plan_v2 import PromptPlanV2, PromptShot
from src.domain.task import Task
from src.services.storage.local_storage import LocalStorageService
from src.workflows.nodes.render_images import render_images
from src.workflows.nodes.run_qc import run_qc
from src.workflows.state import WorkflowDependencies


class FakeV2ImageProvider:
    """用于验证 v2 render fallback 行为的最小图片 provider。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def generate_images_v2(self, prompt_plan, *, output_dir, reference_assets=None):
        """首张图第一次直出报错，后续 fallback 或其他图正常生成。"""
        del reference_assets
        shot = prompt_plan.shots[0]
        self.calls.append(
            {
                "shot_id": shot.shot_id,
                "title_copy": shot.title_copy,
                "subtitle_copy": shot.subtitle_copy,
                "layout_hint": shot.layout_hint,
            }
        )
        if shot.shot_id == "shot-01" and shot.title_copy:
            raise RuntimeError("direct text generation failed")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{len(self.calls):02d}_{shot.shot_id}.png"
        Image.new("RGB", (2048, 2048), color=(255, 255, 255)).save(output_path)
        return GenerationResult(
            images=[
                GeneratedImage(
                    shot_id=shot.shot_id,
                    image_path=str(output_path),
                    preview_path=str(output_path),
                    width=2048,
                    height=2048,
                )
            ]
        )


class DummyOCRService:
    """按图片文件名返回预设 OCR 结果，用于 v2 QC 检查。"""

    def read_text(self, image_path: str) -> list[str]:
        if "shot-01" in image_path:
            return []
        return ["礼盒细节", "包装结构清晰质感高级"]


class DummyRenderer:
    pass


def _build_task(tmp_path: Path, *, task_id: str) -> Task:
    """构造最小任务对象，避免直接写入仓库 outputs 目录。"""
    return Task(
        task_id=task_id,
        brand_name="品牌A",
        product_name="凤凰单丛",
        platform="tmall",
        output_size="1440x1440",
        shot_count=2,
        copy_tone="专业自然",
        workflow_version="v2",
        enable_overlay_fallback=True,
        task_dir=str(tmp_path / task_id),
    )


def _build_deps(image_provider) -> WorkflowDependencies:
    """构造 render/QC 复用的最小依赖集合。"""
    return WorkflowDependencies(
        storage=LocalStorageService(),
        planning_provider=object(),
        vision_analysis_provider=None,
        image_generation_provider=image_provider,
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(),
        text_provider_mode="mock",
        vision_provider_mode="mock",
        image_provider_mode="mock",
        image_provider_name=type(image_provider).__name__,
        image_model_selection=ResolvedModelSelection("image", "mock", "mock-image", "Mock Image", "test"),
    )


def _build_prompt_plan_v2() -> PromptPlanV2:
    """生成两张 v2 prompt，用于验证单张 fallback 不影响整组输出。"""
    return PromptPlanV2(
        shots=[
            PromptShot(
                shot_id="shot-01",
                shot_role="hero",
                render_prompt="高端茶叶主图，产品主体完整，画面高级统一。",
                title_copy="东方茶礼",
                subtitle_copy="甄选春茶醇香回甘",
                layout_hint="顶部留白，右下弱化文案区",
            ),
            PromptShot(
                shot_id="shot-02",
                shot_role="packaging_feature",
                render_prompt="包装特写，突出细节与结构品质。",
                title_copy="礼盒细节",
                subtitle_copy="包装结构清晰质感高级",
                layout_hint="左上留白，不遮挡包装主体",
            ),
        ]
    )


def _build_director_output() -> DirectorOutput:
    """生成与 prompt_plan_v2 对应的最小 director_output。"""
    return DirectorOutput(
        product_summary="凤凰单丛茶礼盒，强调送礼和品质。",
        category="tea",
        platform="tmall",
        visual_style="高级茶礼、统一暖金调性",
        shots=[
            DirectorShot(
                shot_id="shot-01",
                shot_role="hero",
                objective="建立第一视觉转化",
                audience="送礼与自饮人群",
                selling_points=["高端礼盒", "凤凰单丛"],
                scene="高级主图场景",
                composition="居中主体，顶部留白",
                visual_focus="包装主体",
                copy_direction="品牌感与高级感",
                compliance_notes=["不要改包装结构"],
            ),
            DirectorShot(
                shot_id="shot-02",
                shot_role="packaging_feature",
                objective="放大包装价值感",
                audience="注重品质与细节的人群",
                selling_points=["礼盒结构", "质感工艺"],
                scene="包装细节特写",
                composition="近景特写，左上留白",
                visual_focus="礼盒细节",
                copy_direction="卖点转化",
                compliance_notes=["不要改品牌识别"],
            ),
        ],
    )


def test_render_images_v2_marks_single_shot_overlay_fallback(monkeypatch, tmp_path: Path) -> None:
    """验证 v2 渲染时单张直出失败会记录 fallback 候选，而不是整组中断。"""
    task = _build_task(tmp_path, task_id="task-render-v2")
    image_provider = FakeV2ImageProvider()
    deps = _build_deps(image_provider)
    monkeypatch.setattr(
        "src.workflows.nodes.render_images.get_task_generated_dir",
        lambda task_id: str(tmp_path / task_id / "generated"),
    )
    monkeypatch.setattr(
        "src.workflows.nodes.render_images.get_task_generated_preview_dir",
        lambda task_id: str(tmp_path / task_id / "generated_preview"),
    )
    state = {
        "task": task,
        "workflow_version": "v2",
        "enable_overlay_fallback": True,
        "render_mode": "final",
        "assets": [
            Asset(asset_id="asset-01", filename="main.png", local_path=str(tmp_path / "main.png"), asset_type=AssetType.PRODUCT),
            Asset(asset_id="asset-02", filename="detail.png", local_path=str(tmp_path / "detail.png"), asset_type=AssetType.DETAIL),
        ],
        "prompt_plan_v2": _build_prompt_plan_v2(),
        "logs": [],
    }
    Image.new("RGB", (32, 32), color=(250, 250, 250)).save(tmp_path / "main.png")
    Image.new("RGB", (32, 32), color=(245, 245, 245)).save(tmp_path / "detail.png")

    result = render_images(state, deps)

    assert result["workflow_version"] == "v2"
    assert result["render_generation_mode"] == "t2i"
    assert len(result["generation_result_v2"].images) == 2
    assert result["needs_overlay_fallback"] is True
    assert len(result["overlay_fallback_candidates"]) == 1
    assert result["overlay_fallback_candidates"][0]["shot_id"] == "shot-01"
    assert "direct_text_generation_failed" in result["overlay_fallback_candidates"][0]["reason"]
    assert len(image_provider.calls) == 3
    assert image_provider.calls[1]["shot_id"] == "shot-01"
    assert image_provider.calls[1]["title_copy"] == ""
    assert image_provider.calls[2]["shot_id"] == "shot-02"
    assert any("workflow_version=v2" in log for log in result["logs"])


def test_run_qc_v2_reports_overlay_fallback_candidates(monkeypatch, tmp_path: Path) -> None:
    """验证 v2 QC 能识别图内文案缺失，并把单张图标记为 overlay fallback 候选。"""
    task = _build_task(tmp_path, task_id="task-qc-v2")
    task_dir = tmp_path / task.task_id
    (task_dir / "generated").mkdir(parents=True, exist_ok=True)
    (task_dir / "final").mkdir(parents=True, exist_ok=True)
    (task_dir / "previews").mkdir(parents=True, exist_ok=True)
    (task_dir / "exports").mkdir(parents=True, exist_ok=True)

    shot1_path = task_dir / "final" / "01_shot-01.png"
    shot2_path = task_dir / "final" / "02_shot-02.png"
    Image.new("RGB", (1440, 1440), color=(255, 255, 255)).save(shot1_path)
    Image.new("RGB", (1440, 1440), color=(255, 255, 255)).save(shot2_path)

    prompt_plan_v2 = _build_prompt_plan_v2()
    director_output = _build_director_output()
    (task_dir / "task.json").write_text(task.model_dump_json(indent=2), encoding="utf-8")
    (task_dir / "director_output.json").write_text(director_output.model_dump_json(indent=2), encoding="utf-8")
    (task_dir / "prompt_plan_v2.json").write_text(prompt_plan_v2.model_dump_json(indent=2), encoding="utf-8")
    (task_dir / "final_text_regions.json").write_text(
        json.dumps(
            {
                "workflow_version": "v2",
                "render_variant": "final",
                "shots": [
                    {"shot_id": "shot-01", "overlay_applied": False},
                    {"shot_id": "shot-02", "overlay_applied": False},
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("src.workflows.nodes.run_qc.get_task_dir", lambda task_id: task_dir)
    deps = _build_deps(image_provider=FakeV2ImageProvider())
    state = {
        "task": task,
        "workflow_version": "v2",
        "render_mode": "final",
        "render_variant": "final",
        "render_generation_mode": "t2i",
        "render_reference_asset_ids": ["asset-01"],
        "generation_result": GenerationResult(
            images=[
                GeneratedImage(
                    shot_id="shot-01",
                    image_path=str(shot1_path),
                    preview_path=str(shot1_path),
                    width=1440,
                    height=1440,
                    status="finalized",
                ),
                GeneratedImage(
                    shot_id="shot-02",
                    image_path=str(shot2_path),
                    preview_path=str(shot2_path),
                    width=1440,
                    height=1440,
                    status="finalized",
                ),
            ]
        ),
        "generation_result_v2": GenerationResult(
            images=[
                GeneratedImage(
                    shot_id="shot-01",
                    image_path=str(shot1_path),
                    preview_path=str(shot1_path),
                    width=1440,
                    height=1440,
                    status="finalized",
                ),
                GeneratedImage(
                    shot_id="shot-02",
                    image_path=str(shot2_path),
                    preview_path=str(shot2_path),
                    width=1440,
                    height=1440,
                    status="finalized",
                ),
            ]
        ),
        "prompt_plan_v2": prompt_plan_v2,
        "director_output": director_output,
        "overlay_fallback_candidates": [],
        "logs": [],
    }

    result = run_qc(state, deps)

    assert result["qc_report_v2"].review_required is True
    assert result["needs_overlay_fallback"] is True
    assert len(result["overlay_fallback_candidates"]) == 1
    assert result["overlay_fallback_candidates"][0]["shot_id"] == "shot-01"
    assert result["overlay_fallback_candidates"][0]["fallback_stage"] == "run_qc"
    assert "ocr_no_text_detected_for_direct_text_image" in result["overlay_fallback_candidates"][0]["reason"]
    assert any(check.check_name == "text_readability_check" for check in result["qc_report_v2"].checks)
