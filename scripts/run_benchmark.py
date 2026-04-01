from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import io
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Iterator

from PIL import Image

from backend.engine.core.config import get_settings
from backend.engine.core.logging import attach_task_file_handler, detach_task_file_handler, initialize_logging
from backend.engine.core.paths import ensure_task_dirs
from backend.engine.domain.generation_result import GenerationResult
from backend.engine.domain.qc_report import QCReport
from backend.engine.domain.task import Task, TaskStatus
from backend.engine.services.storage.local_storage import LocalStorageService
from backend.engine.workflows.graph import build_workflow, reload_runtime
from backend.engine.workflows.state import WorkflowExecutionError, format_workflow_log


@dataclass(frozen=True)
class ProviderCombo:
    label: str
    text: str
    vision: str
    image: str

    def as_string(self) -> str:
        return f"{self.label}:text={self.text},vision={self.vision},image={self.image}"


def main() -> None:
    args = _parse_args()
    case_root = Path(args.case_root).resolve()
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_path = Path(args.output).resolve() if args.output else Path("outputs/benchmarks") / run_id / "benchmark_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    combos = _resolve_provider_combos(args.provider_combo, budget_mode=args.budget_mode)
    prompt_build_modes = args.prompt_build_mode or [args.prompt_build_mode_default]
    report_runs: list[dict[str, object]] = []

    for case_name in args.cases:
        case_dir = case_root / case_name
        case_manifest = _load_case_manifest(case_dir)
        for combo in combos:
            for prompt_build_mode in prompt_build_modes:
                report_runs.append(
                    _run_single_benchmark(
                        case_dir=case_dir,
                        case_manifest=case_manifest,
                        budget_mode=args.budget_mode,
                        provider_combo=combo,
                        prompt_build_mode=prompt_build_mode,
                        render_mode=args.render_mode,
                    )
                )

    report = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(),
        "case_root": str(case_root),
        "budget_mode": args.budget_mode,
        "render_mode": args.render_mode,
        "prompt_build_modes": prompt_build_modes,
        "provider_combos": [combo.as_string() for combo in combos],
        "runs": report_runs,
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"benchmark_report.json written to: {output_path}")


def _parse_args() -> argparse.Namespace:
    default_settings = get_settings()
    parser = argparse.ArgumentParser(description="Run minimal benchmark cases against the existing workflow.")
    parser.add_argument(
        "--case-root",
        default="tests/fixtures/ecom_cases",
        help="Case fixture root directory. Default: tests/fixtures/ecom_cases",
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        required=True,
        help="Case names under the case root, for example: tea_single_can tea_gift_box",
    )
    parser.add_argument(
        "--budget-mode",
        choices=["local", "cheap", "balanced", "production"],
        default=default_settings.resolve_budget_mode(),
        help="Effective budget mode for this benchmark run.",
    )
    parser.add_argument(
        "--provider-combo",
        action="append",
        default=[],
        help="Provider combo, for example: mock_all:text=mock,vision=mock,image=mock",
    )
    parser.add_argument(
        "--prompt-build-mode",
        action="append",
        choices=["per_shot", "batch"],
        default=[],
        help="Prompt build mode. Can be repeated to compare both modes.",
    )
    parser.add_argument(
        "--render-mode",
        choices=["preview", "final", "full_auto"],
        default=default_settings.resolve_render_mode(),
        help="Render mode passed into the workflow.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path for benchmark_report.json. Default: outputs/benchmarks/{run_id}/benchmark_report.json",
    )
    args = parser.parse_args()
    args.prompt_build_mode_default = default_settings.resolve_prompt_build_mode()
    return args


def _resolve_provider_combos(raw_values: list[str], *, budget_mode: str) -> list[ProviderCombo]:
    if raw_values:
        return [_parse_provider_combo(value) for value in raw_values]

    with _temporary_env(
        {
            "ECOM_IMAGE_AGENT_BUDGET_MODE": budget_mode,
            "ECOM_IMAGE_AGENT_TEXT_PROVIDER": None,
            "ECOM_IMAGE_AGENT_VISION_PROVIDER": None,
            "ECOM_IMAGE_AGENT_IMAGE_PROVIDER": None,
            "ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE": None,
            "ECOM_IMAGE_AGENT_VISION_PROVIDER_MODE": None,
            "ECOM_IMAGE_AGENT_IMAGE_PROVIDER_MODE": None,
        }
    ):
        reload_runtime()
        settings = get_settings()
        return [
            ProviderCombo(
                label="budget_default",
                text=settings.resolve_text_provider_route().alias,
                vision=settings.resolve_vision_provider_route().alias,
                image=settings.resolve_image_provider_route().alias,
            )
        ]


def _parse_provider_combo(raw_value: str) -> ProviderCombo:
    label = "custom"
    mapping_part = raw_value
    if ":" in raw_value:
        label, mapping_part = raw_value.split(":", maxsplit=1)

    values: dict[str, str] = {}
    for item in mapping_part.split(","):
        key, value = item.split("=", maxsplit=1)
        values[key.strip().lower()] = value.strip().lower()

    for required_key in ("text", "vision", "image"):
        if required_key not in values:
            raise RuntimeError(f"provider combo missing `{required_key}`: {raw_value}")

    normalized_label = label.strip() or f"text-{values['text']}_vision-{values['vision']}_image-{values['image']}"
    return ProviderCombo(
        label=normalized_label,
        text=values["text"],
        vision=values["vision"],
        image=values["image"],
    )


def _run_single_benchmark(
    *,
    case_dir: Path,
    case_manifest: dict[str, object],
    budget_mode: str,
    provider_combo: ProviderCombo,
    prompt_build_mode: str,
    render_mode: str,
) -> dict[str, object]:
    env_overrides = {
        "ECOM_IMAGE_AGENT_BUDGET_MODE": budget_mode,
        "ECOM_IMAGE_AGENT_PROMPT_BUILD_MODE": prompt_build_mode,
        "ECOM_IMAGE_AGENT_RENDER_MODE": render_mode,
        "ECOM_IMAGE_AGENT_TEXT_PROVIDER": provider_combo.text,
        "ECOM_IMAGE_AGENT_VISION_PROVIDER": provider_combo.vision,
        "ECOM_IMAGE_AGENT_IMAGE_PROVIDER": provider_combo.image,
        "ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE": _provider_mode_from_alias(provider_combo.text),
        "ECOM_IMAGE_AGENT_VISION_PROVIDER_MODE": _provider_mode_from_alias(provider_combo.vision),
        "ECOM_IMAGE_AGENT_IMAGE_PROVIDER_MODE": _provider_mode_from_alias(provider_combo.image),
    }

    task_id = ""
    with _temporary_env(env_overrides):
        reload_runtime()
        settings = get_settings()
        initialize_logging(settings)
        storage = LocalStorageService()
        task_id = storage.create_task_id()
        task_dirs = ensure_task_dirs(task_id)
        started_at = perf_counter()
        attach_task_file_handler(task_id, task_dirs["task"], settings=settings)
        try:
            task = _build_task(case_manifest=case_manifest, task_id=task_id, task_dir=task_dirs["task"])
            storage.save_task_manifest(task)
            uploads_payload, used_placeholder_inputs = _load_case_uploads(case_dir, case_manifest)
            assets = storage.save_uploads(task_id, uploads_payload)
            initial_state = {
                "task": task,
                "assets": assets,
                "logs": [
                    format_workflow_log(
                        task_id=task_id,
                        node_name="benchmark_entry",
                        event="start",
                        detail=(
                            f"case={case_manifest['case_name']}, "
                            f"provider_combo={provider_combo.as_string()}, "
                            f"prompt_build_mode={prompt_build_mode}, "
                            f"render_mode={render_mode}, "
                            f"placeholder_inputs={used_placeholder_inputs}"
                        ),
                    )
                ],
                "cache_enabled": settings.enable_node_cache,
                "ignore_cache": False,
                "prompt_build_mode": prompt_build_mode,
                "render_mode": render_mode,
                "analyze_max_reference_images": settings.analyze_max_reference_images,
                "render_max_reference_images": settings.render_max_reference_images,
            }
            state = build_workflow().invoke(initial_state)
            total_latency_ms = int((perf_counter() - started_at) * 1000)
            return {
                "task_id": task_id,
                "case_name": str(case_manifest["case_name"]),
                "provider_combo": provider_combo.as_string(),
                "render_mode": render_mode,
                "prompt_build_mode": prompt_build_mode,
                "total_latency_ms": total_latency_ms,
                "total_tokens": _extract_total_tokens(state, task_dirs["task"]),
                "generated_image_count": _extract_generated_image_count(state),
                "qc_status": _extract_qc_status(state),
                "task_dir": str(task_dirs["task"]),
            }
        except WorkflowExecutionError as exc:
            total_latency_ms = int((perf_counter() - started_at) * 1000)
            return {
                "task_id": task_id,
                "case_name": str(case_manifest["case_name"]),
                "provider_combo": provider_combo.as_string(),
                "render_mode": render_mode,
                "prompt_build_mode": prompt_build_mode,
                "total_latency_ms": total_latency_ms,
                "total_tokens": 0,
                "generated_image_count": 0,
                "qc_status": "failed",
                "task_dir": str(task_dirs["task"]),
                "error": str(exc),
            }
        finally:
            detach_task_file_handler(task_id)


def _build_task(*, case_manifest: dict[str, object], task_id: str, task_dir: Path) -> Task:
    task_config = dict(case_manifest["task"])
    return Task(
        task_id=task_id,
        brand_name=str(task_config["brand_name"]),
        product_name=str(task_config["product_name"]),
        category=str(case_manifest.get("category", "tea")),
        platform=str(task_config["platform"]),
        output_size=str(task_config["output_size"]),
        shot_count=int(task_config["shot_count"]),
        copy_tone=str(task_config["copy_tone"]),
        status=TaskStatus.RUNNING,
        task_dir=str(task_dir),
    )


def _load_case_manifest(case_dir: Path) -> dict[str, object]:
    manifest_path = case_dir / "case.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Missing case manifest: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _load_case_uploads(case_dir: Path, case_manifest: dict[str, object]) -> tuple[list[tuple[str, bytes]], bool]:
    inputs_dir = case_dir / "inputs"
    expected_count = int(case_manifest.get("input_count", 0))
    actual_inputs = sorted(path for path in inputs_dir.iterdir() if path.is_file() and not path.name.startswith("."))
    uploads_payload = [(path.name, path.read_bytes()) for path in actual_inputs[:expected_count]]
    used_placeholder_inputs = False

    placeholder_specs = list(case_manifest.get("placeholder_inputs", []))
    if len(uploads_payload) >= expected_count:
        return uploads_payload, used_placeholder_inputs

    if len(placeholder_specs) < expected_count - len(uploads_payload):
        raise RuntimeError(
            f"Case `{case_manifest['case_name']}` lacks enough real inputs and placeholder_inputs. "
            f"expected={expected_count}, actual={len(uploads_payload)}, placeholders={len(placeholder_specs)}"
        )

    for spec in placeholder_specs[len(uploads_payload) : expected_count]:
        uploads_payload.append((str(spec["filename"]), _build_placeholder_image_bytes(spec)))
        used_placeholder_inputs = True
    return uploads_payload, used_placeholder_inputs


def _build_placeholder_image_bytes(spec: dict[str, object]) -> bytes:
    width, height = [int(value) for value in str(spec.get("size", "1600x1600")).split("x", maxsplit=1)]
    color = tuple(spec.get("color", [220, 220, 220]))
    payload = io.BytesIO()
    Image.new("RGB", (width, height), color=color).save(payload, format="PNG")
    return payload.getvalue()


def _extract_generated_image_count(state: dict[str, object]) -> int:
    result = state.get("generation_result")
    if not result:
        result = state.get("preview_generation_result")
    if isinstance(result, GenerationResult):
        return len(result.images)
    if isinstance(result, dict):
        return len(result.get("images", []))
    return 0


def _extract_qc_status(state: dict[str, object]) -> str:
    report = state.get("qc_report") or state.get("preview_qc_report")
    if isinstance(report, QCReport):
        if report.passed:
            return "passed"
        if report.review_required:
            return "review_required"
    if isinstance(report, dict):
        if report.get("passed"):
            return "passed"
        if report.get("review_required"):
            return "review_required"
    task = state.get("task")
    if isinstance(task, Task):
        return task.status.value
    if isinstance(task, dict) and task.get("status"):
        return str(task["status"])
    return "unknown"


def _extract_total_tokens(state: dict[str, object], task_dir: Path) -> int:
    if isinstance(state.get("total_tokens"), int):
        return int(state["total_tokens"])
    token_path = task_dir / "token_usage.json"
    if token_path.exists():
        payload = json.loads(token_path.read_text(encoding="utf-8"))
        return int(payload.get("total_tokens", 0))
    return 0


def _provider_mode_from_alias(alias: str) -> str:
    return "mock" if alias == "mock" else "real"


@contextmanager
def _temporary_env(overrides: dict[str, str | None]) -> Iterator[None]:
    original_values: dict[str, str | None] = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in original_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        reload_runtime()


if __name__ == "__main__":
    main()
