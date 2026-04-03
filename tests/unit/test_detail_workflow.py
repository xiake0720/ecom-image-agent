from __future__ import annotations

from pathlib import Path

from PIL import Image

from backend.engine.core import config as engine_config_module
from backend.engine.core.paths import ensure_task_dirs
from backend.engine.domain.task import Task, TaskStatus
from backend.engine.workflows.detail_graph import run_detail_workflow
from backend.engine.workflows.detail_state import DetailWorkflowState
from backend.schemas.detail import DetailPageAssetRef, DetailPageJobCreatePayload


def test_detail_workflow_plan_only_stops_after_prompt(monkeypatch, tmp_path) -> None:
    _configure_mock_runtime(monkeypatch, tmp_path)
    task_id = "detail-plan-only"
    task_dir = ensure_task_dirs(task_id)["task"]
    asset_path = task_dir / "inputs" / "packaging.png"
    _write_test_image(asset_path, size=(640, 640))

    state = _build_initial_state(task_id=task_id, task_dir=task_dir, asset_relative_path="inputs/packaging.png")

    result = run_detail_workflow(state, stop_after="detail_generate_prompt")

    assert result["task"].status == TaskStatus.COMPLETED
    assert (task_dir / "inputs" / "request_payload.json").exists()
    assert (task_dir / "plan" / "detail_plan.json").exists()
    assert (task_dir / "plan" / "detail_copy_plan.json").exists()
    assert (task_dir / "plan" / "detail_prompt_plan.json").exists()
    assert not (task_dir / "generated" / "detail_render_report.json").exists()


def test_detail_workflow_full_mock_mode_generates_artifacts(monkeypatch, tmp_path) -> None:
    _configure_mock_runtime(monkeypatch, tmp_path)
    task_id = "detail-full-mock"
    task_dir = ensure_task_dirs(task_id)["task"]
    asset_path = task_dir / "inputs" / "packaging.png"
    _write_test_image(asset_path, size=(640, 640))

    state = _build_initial_state(task_id=task_id, task_dir=task_dir, asset_relative_path="inputs/packaging.png")

    result = run_detail_workflow(state)

    assert result["task"].status in {TaskStatus.COMPLETED, TaskStatus.REVIEW_REQUIRED}
    assert (task_dir / "generated" / "detail_render_report.json").exists()
    assert list((task_dir / "generated").glob("*.png"))
    assert (task_dir / "qc" / "detail_qc_report.json").exists()
    assert (task_dir / "exports" / "detail_bundle.zip").exists()
    assert (task_dir / "detail_manifest.json").exists()


def _configure_mock_runtime(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE", "mock")
    monkeypatch.setenv("ECOM_IMAGE_AGENT_IMAGE_PROVIDER_MODE", "mock")
    monkeypatch.setenv("ECOM_IMAGE_AGENT_OUTPUTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("ECOM_IMAGE_AGENT_TASKS_DIR", str(tmp_path / "outputs" / "tasks"))
    monkeypatch.setenv("ECOM_IMAGE_AGENT_CACHE_DIR", str(tmp_path / "outputs" / "cache"))
    monkeypatch.setenv("ECOM_IMAGE_AGENT_EXPORTS_DIR", str(tmp_path / "outputs" / "exports"))
    engine_config_module.reload_settings()


def _build_initial_state(*, task_id: str, task_dir: Path, asset_relative_path: str) -> DetailWorkflowState:
    task = Task(
        task_id=task_id,
        brand_name="山野茶事",
        product_name="凤凰单丛礼盒",
        category="tea",
        platform="tmall",
        shot_count=4,
        aspect_ratio="1:3",
        image_size="2K",
        status=TaskStatus.CREATED,
        task_dir=str(task_dir),
        current_step="queued",
        current_step_label="详情图任务已提交",
        progress_percent=0,
        style_type="tea_tmall_premium_light",
        style_notes="克制高级，突出包装主体",
    )
    payload = DetailPageJobCreatePayload(
        brand_name="山野茶事",
        product_name="凤凰单丛礼盒",
        tea_type="乌龙茶",
        platform="tmall",
        style_preset="tea_tmall_premium_light",
        target_slice_count=4,
        selling_points=["花香层次丰富", "回甘持久", "礼赠体面"],
        specs={"净含量": "150g", "产地": "广东潮州"},
        brew_suggestion="100℃ 热水高冲，首泡快速出汤。",
        extra_requirements="首屏优先突出真实包装，不做夸张光效。",
    )
    return {
        "task": task,
        "detail_payload": payload,
        "detail_assets": [
            DetailPageAssetRef(
                asset_id="asset-001",
                role="packaging",
                file_name="packaging.png",
                relative_path=asset_relative_path,
            )
        ],
        "logs": [],
        "error_message": "",
    }


def _write_test_image(path: Path, *, size: tuple[int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (236, 228, 214)).save(path)
