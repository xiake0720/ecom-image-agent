from __future__ import annotations

import base64
import json
from pathlib import Path
import zipfile

from PIL import Image

from src.core.config import Settings
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.domain.prompt_plan_v2 import PromptPlanV2, PromptShot
from src.domain.qc_report import QCReport
from src.domain.task import Task, TaskStatus
from src.providers.image.runapi_gemini31_image import RunApiGemini31ImageProvider
from src.services.rendering.text_renderer import TextRenderer
from src.workflows.nodes.finalize import finalize
from src.workflows.nodes.render_images import render_images
from src.workflows.nodes.run_qc import run_qc
from src.workflows.state import WorkflowDependencies


class FakeImageProvider:
    def __init__(self) -> None:
        self.v2_calls: list[str] = []
        self.compat_calls: list[str] = []

    def generate_images_v2(self, prompt_plan, *, output_dir: Path, reference_assets=None) -> GenerationResult:
        del reference_assets
        shot = prompt_plan.shots[0]
        self.v2_calls.append(shot.shot_id)
        if shot.shot_id == "shot_01":
            raise RuntimeError("force overlay fallback")
        return self.generate_images(_compat_plan_for_test(shot.shot_id), output_dir=output_dir, reference_assets=None)

    def generate_images(self, plan, *, output_dir: Path, reference_assets=None) -> GenerationResult:
        del reference_assets
        prompt = plan.prompts[0]
        self.compat_calls.append(prompt.shot_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{prompt.shot_id}.png"
        Image.new("RGB", (512, 512), color=(255, 255, 255)).save(output_path)
        return GenerationResult(
            images=[
                GeneratedImage(
                    shot_id=prompt.shot_id,
                    image_path=str(output_path),
                    preview_path=str(output_path),
                    width=512,
                    height=512,
                )
            ]
        )


class TmpStorageService:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    def save_json_artifact(self, task_id: str, filename: str, payload: object) -> Path:
        del task_id
        task_dir = self.root_dir
        target = task_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        content = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
        target.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    def save_task_manifest(self, task) -> Path:
        target = Path(task.task_dir) / "task.json"
        target.write_text(task.model_dump_json(indent=2), encoding="utf-8")
        return target

    def create_zip(self, task_id: str, source_dir: Path, output_name: str = "results") -> Path:
        del task_id
        exports_dir = self.root_dir / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        archive_path = exports_dir / f"{output_name}.zip"
        with zipfile.ZipFile(archive_path, mode="w") as archive:
            for path in sorted(source_dir.rglob("*")):
                if path.is_file():
                    archive.write(path, arcname=path.relative_to(source_dir))
        return archive_path


def test_render_qc_finalize_keeps_overlay_fallback_inside_render(monkeypatch, tmp_path: Path) -> None:
    task_dir = tmp_path / "task-render"
    task_dir.mkdir(parents=True, exist_ok=True)
    task = Task(task_id="task-render", brand_name="示例品牌", product_name="高山乌龙", task_dir=str(task_dir))
    provider = FakeImageProvider()
    storage = TmpStorageService(task_dir)
    deps = WorkflowDependencies(
        storage=storage,
        planning_provider=object(),
        image_generation_provider=provider,
        text_renderer=TextRenderer(Path("missing-font.ttf")),
        text_provider_mode="mock",
        image_provider_mode="mock",
    )
    monkeypatch.setattr("src.workflows.nodes.render_images.get_task_generated_dir", lambda task_id: str(task_dir / "generated"))
    monkeypatch.setattr("src.workflows.nodes.render_images.get_task_final_dir", lambda task_id: str(task_dir / "final"))
    monkeypatch.setattr("src.workflows.nodes.run_qc.get_task_dir", lambda task_id: task_dir)
    monkeypatch.setattr(
        "src.services.storage.zip_export.ensure_task_dirs",
        lambda task_id: {
            "task": task_dir,
            "inputs": task_dir / "inputs",
            "generated": task_dir / "generated",
            "generated_preview": task_dir / "generated_preview",
            "final": task_dir / "final",
            "final_preview": task_dir / "final_preview",
            "previews": task_dir / "previews",
            "exports": task_dir / "exports",
        },
    )
    state = {
        "task": task,
        "assets": [],
        "prompt_plan_v2": PromptPlanV2(
            shots=[
                PromptShot(
                    shot_id="shot_01",
                    shot_role="hero",
                    render_prompt="hero shot",
                    title_copy="东方茶礼",
                    subtitle_copy="包装主体稳定清晰可见",
                    layout_hint="top_left",
                ),
                PromptShot(
                    shot_id="shot_02",
                    shot_role="packaging_feature",
                    render_prompt="detail shot",
                    title_copy="细节见真",
                    subtitle_copy="包装结构细节清晰稳定",
                    layout_hint="top_right",
                ),
            ]
        ),
        "logs": [],
    }

    render_result = render_images(state, deps)
    qc_result = run_qc({**state, **render_result}, deps)
    final_result = finalize({**state, **render_result, **qc_result}, deps)

    assert len(render_result["generation_result_v2"].images) == 2
    assert render_result["text_render_reports"]["shot_01"]["overlay_applied"] is True
    assert render_result["text_render_reports"]["shot_02"]["overlay_applied"] is False
    assert provider.v2_calls == ["shot_01", "shot_02"]
    assert provider.compat_calls == ["shot_01", "shot_02"]
    assert isinstance(qc_result["qc_report_v2"], QCReport)
    assert qc_result["qc_report_v2"].review_required is True
    assert final_result["task"].status == TaskStatus.REVIEW_REQUIRED
    assert Path(final_result["export_zip_path"]).exists()
    assert Path(final_result["full_task_bundle_zip_path"]).exists()


def test_render_images_reports_partial_results_per_shot(monkeypatch, tmp_path: Path) -> None:
    task_dir = tmp_path / "task-progressive-render"
    task_dir.mkdir(parents=True, exist_ok=True)
    task = Task(task_id="task-progressive-render", brand_name="示例品牌", product_name="高山乌龙", task_dir=str(task_dir))
    provider = FakeImageProvider()
    progress_events: list[dict[str, object]] = []
    deps = WorkflowDependencies(
        storage=TmpStorageService(task_dir),
        planning_provider=object(),
        image_generation_provider=provider,
        text_renderer=TextRenderer(Path("missing-font.ttf")),
        text_provider_mode="mock",
        image_provider_mode="mock",
        progress_callback=lambda state: progress_events.append(state),
    )
    monkeypatch.setattr("src.workflows.nodes.render_images.get_task_generated_dir", lambda task_id: str(task_dir / "generated"))
    monkeypatch.setattr("src.workflows.nodes.render_images.get_task_final_dir", lambda task_id: str(task_dir / "final"))
    state = {
        "task": task,
        "assets": [],
        "prompt_plan_v2": PromptPlanV2(
            shots=[
                PromptShot(
                    shot_id="shot_01",
                    shot_role="hero",
                    render_prompt="hero shot",
                    title_copy="东方茶礼",
                    subtitle_copy="包装主体稳定清晰可见",
                    layout_hint="top_left",
                ),
                PromptShot(
                    shot_id="shot_02",
                    shot_role="packaging_feature",
                    render_prompt="detail shot",
                    title_copy="细节见真",
                    subtitle_copy="包装结构细节清晰稳定",
                    layout_hint="top_right",
                ),
            ]
        ),
        "logs": [],
    }

    render_result = render_images(state, deps)

    assert len(render_result["generation_result_v2"].images) == 2
    assert [len(event["generation_result_v2"].images) for event in progress_events] == [1, 2]
    assert progress_events[0]["task"].current_step == "render_images"
    assert progress_events[0]["task"].current_step_label == "正在生成图片（1/2）"
    assert progress_events[1]["task"].current_step_label == "正在生成图片（2/2）"


def test_runapi_gemini31_request_disables_environment_proxy(monkeypatch) -> None:
    session_state: dict[str, object] = {}

    class FakeResponse:
        status_code = 200
        text = '{"ok":true}'

        def json(self) -> dict[str, object]:
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "data": base64.b64encode(b"fake-image-bytes").decode("utf-8"),
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

    class FakeSession:
        def __init__(self) -> None:
            self.trust_env = True
            self.proxies = {"http": "http://proxy.local", "https": "http://proxy.local"}

        def __enter__(self):
            session_state["session"] = self
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, *args, **kwargs):
            session_state["post_args"] = args
            session_state["post_kwargs"] = kwargs
            return FakeResponse()

    monkeypatch.setattr("src.providers.image.runapi_gemini31_image.requests.Session", FakeSession)
    provider = RunApiGemini31ImageProvider(
        Settings(
            image_provider_mode="real",
            runapi_api_key="test-key",
            runapi_image_model="gemini-3.1-flash-image-preview",
        )
    )

    result = provider._generate_single(
        shot_id="shot_01",
        prompt_text="test prompt",
        reference_assets=[],
        aspect_ratio="1:1",
        image_size="2K",
    )

    fake_session = session_state["session"]
    assert result == b"fake-image-bytes"
    assert fake_session.trust_env is False
    assert fake_session.proxies == {}


def test_runapi_gemini31_supports_file_data_uri_response(monkeypatch) -> None:
    session_state: dict[str, object] = {"sessions": []}

    class FakeGenerateResponse:
        status_code = 200
        text = '{"ok":true}'
        content = b""

        def json(self) -> dict[str, object]:
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "fileData": {
                                        "mimeType": "image/jpeg",
                                        "fileUri": "https://runapi.co/images/fake-generated.jpg",
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

    class FakeDownloadResponse:
        status_code = 200
        text = ""
        content = b"downloaded-image-bytes"

        def json(self) -> dict[str, object]:
            raise AssertionError("download response should not be parsed as json")

    class FakeSession:
        def __init__(self) -> None:
            self.trust_env = True
            self.proxies = {"http": "http://proxy.local", "https": "http://proxy.local"}
            self.calls: list[tuple[str, str]] = []

        def __enter__(self):
            session_state["sessions"].append(self)
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url, **kwargs):
            self.calls.append(("post", url))
            return FakeGenerateResponse()

        def get(self, url, **kwargs):
            self.calls.append(("get", url))
            session_state["download_headers"] = kwargs.get("headers")
            return FakeDownloadResponse()

    monkeypatch.setattr("src.providers.image.runapi_gemini31_image.requests.Session", FakeSession)
    provider = RunApiGemini31ImageProvider(
        Settings(
            image_provider_mode="real",
            runapi_api_key="test-key",
            runapi_image_model="gemini-3.1-flash-image-preview",
        )
    )

    result = provider._generate_single(
        shot_id="shot_01",
        prompt_text="test prompt",
        reference_assets=[],
        aspect_ratio="1:1",
        image_size="2K",
    )

    sessions = session_state["sessions"]
    assert result == b"downloaded-image-bytes"
    assert len(sessions) == 2
    assert sessions[0].calls == [("post", "https://runapi.co/v1/models/gemini-3.1-flash-image-preview:generateContent")]
    assert sessions[1].calls == [("get", "https://runapi.co/images/fake-generated.jpg")]
    assert sessions[0].trust_env is False
    assert sessions[1].trust_env is False
    assert sessions[0].proxies == {}
    assert sessions[1].proxies == {}
    assert session_state["download_headers"]["Authorization"].startswith("Bearer ")


def _compat_plan_for_test(shot_id: str):
    from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan

    return ImagePromptPlan(
        generation_mode="t2i",
        prompts=[
            ImagePrompt(
                shot_id=shot_id,
                shot_type="compat",
                prompt=f"compat prompt for {shot_id}",
                output_size="512x512",
            )
        ],
    )
