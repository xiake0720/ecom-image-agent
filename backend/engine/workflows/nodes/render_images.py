"""v2 图片生成节点。

文件位置：
- `src/workflows/nodes/render_images.py`

职责：
- 消费 `prompt_plan_v2`
- 调用图片 provider 生成图片
- 在节点内部完成 overlay fallback，不再保留独立旧节点
- 明确区分产品参考图与背景风格参考图
"""

from __future__ import annotations

from pathlib import Path
import shutil

from PIL import Image

from backend.engine.core.config import get_settings
from backend.engine.core.paths import get_task_final_dir, get_task_generated_dir
from backend.engine.domain.generation_result import GeneratedImage, GenerationResult
from backend.engine.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from backend.engine.domain.prompt_plan_v2 import PromptPlanV2, PromptShot
from backend.engine.services.assets.reference_selector import select_reference_bundle
from backend.engine.workflows.state import (
    WorkflowDependencies,
    WorkflowState,
    build_render_progress_task,
    format_connected_contract_logs,
)


def render_images(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """执行 v2 图片生成，并在内部处理 overlay fallback。"""

    task = state["task"]
    prompt_plan = state.get("prompt_plan_v2")
    if prompt_plan is None or not prompt_plan.shots:
        raise RuntimeError("render_images requires prompt_plan_v2")

    settings = get_settings()
    generated_dir = Path(get_task_generated_dir(task.task_id))
    final_dir = Path(get_task_final_dir(task.task_id))
    generated_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)

    selection = select_reference_bundle(state.get("assets", []), max_images=2, max_background_style_images=2)
    generation_context = _resolve_generation_context(
        provider=deps.image_generation_provider,
        fallback_model_id=deps.image_model_selection.model_id if deps.image_model_selection else settings.runapi_image_model,
        reference_assets=selection.product_reference_assets,
        background_style_assets=selection.background_style_assets,
    )
    logs = [
        *state.get("logs", []),
        *format_connected_contract_logs(state, node_name="render_images"),
        f"[render_images] start shot_count={len(prompt_plan.shots)} model={generation_context['model_id']}",
        f"[render_images] product_reference_asset_ids={generation_context['reference_asset_ids']}",
        f"[render_images] background_style_asset_ids={generation_context['background_style_asset_ids']}",
        f"[render_images] overlay_fallback_enabled={str(settings.enable_overlay_fallback).lower()}",
    ]

    final_images: list[GeneratedImage] = []
    text_render_reports: dict[str, dict[str, object]] = {}
    fallback_count = 0
    total_shots = len(prompt_plan.shots)
    for index, shot in enumerate(prompt_plan.shots, start=1):
        generated_image, report, used_fallback = _render_single_shot(
            index=index,
            shot=shot,
            generated_dir=generated_dir,
            final_dir=final_dir,
            reference_assets=selection.product_reference_assets,
            background_style_assets=selection.background_style_assets,
            deps=deps,
            overlay_fallback_enabled=settings.enable_overlay_fallback,
        )
        final_images.append(generated_image)
        text_render_reports[shot.shot_id] = report
        fallback_count += 1 if used_fallback else 0
        logs.append(
            "[render_images] "
            f"shot_id={shot.shot_id} role={shot.shot_role} copy_strategy={shot.copy_strategy} "
            f"should_render_text={str(shot.should_render_text).lower()} "
            f"copy_source={shot.copy_source} overlay_fallback={str(used_fallback).lower()} final_path={generated_image.image_path}"
        )
        _publish_partial_render_result(
            base_state=state,
            deps=deps,
            task=task,
            images=final_images,
            text_render_reports=text_render_reports,
            logs=logs,
            completed_count=index,
            total_count=total_shots,
        )

    if not final_images:
        raise RuntimeError("generation returned no images")

    generation_result = GenerationResult(images=final_images)
    deps.storage.save_json_artifact(task.task_id, "final_text_regions.json", {"shots": list(text_render_reports.values())})
    return {
        "generation_result": generation_result,
        "generation_result_v2": generation_result,
        "text_render_reports": text_render_reports,
        "logs": [
            *logs,
            f"[render_images] completed count={len(final_images)} fallback_count={fallback_count}",
        ],
    }


def _render_single_shot(
    *,
    index: int,
    shot: PromptShot,
    generated_dir: Path,
    final_dir: Path,
    reference_assets: list,
    background_style_assets: list,
    deps: WorkflowDependencies,
    overlay_fallback_enabled: bool,
) -> tuple[GeneratedImage, dict[str, object], bool]:
    """执行单张图生成，并在失败时回退到 Pillow 贴字。"""

    provider = deps.image_generation_provider
    execution_shot = _build_execution_shot(shot)
    raw_result: GenerationResult | None = None
    raw_image: GeneratedImage | None = None
    used_fallback = False
    fallback_reason = ""

    if hasattr(provider, "generate_images_v2"):
        try:
            raw_result = provider.generate_images_v2(
                PromptPlanV2(shots=[execution_shot]),
                output_dir=generated_dir,
                reference_assets=reference_assets,
                background_style_assets=background_style_assets,
            )
            raw_image = _first_image(raw_result, shot.shot_id)
        except Exception:
            fallback_reason = "v2_generation_failed"
            if not overlay_fallback_enabled:
                raise
    else:
        fallback_reason = "provider_without_v2"
    if raw_image is None:
        used_fallback = True
        raw_result = provider.generate_images(
            _build_compatibility_plan(execution_shot),
            output_dir=generated_dir,
            reference_assets=reference_assets,
            background_style_assets=background_style_assets,
        )
        raw_image = _first_image(raw_result, shot.shot_id)

    if raw_image is None:
        raise RuntimeError(f"image generation returned no image for {shot.shot_id}")

    if used_fallback:
        final_path = final_dir / Path(raw_image.image_path).name
        render_report = deps.text_renderer.render_overlay(
            shot_id=shot.shot_id,
            image_path=raw_image.image_path,
            output_path=str(final_path),
            title=shot.title_copy,
            subtitle=shot.subtitle_copy,
            selling_points=shot.selling_points_for_render,
            layout_hint=shot.layout_hint,
        )
        final_image = _build_final_image(shot_id=shot.shot_id, final_path=final_path)
        report = {
            "shot_id": shot.shot_id,
            "overlay_applied": True,
            "font_source": render_report.font_source,
            "fallback_used": render_report.fallback_used,
            "fallback_reason": fallback_reason or "overlay_text_render",
            "copy_strategy": shot.copy_strategy,
            "text_density": shot.text_density,
            "should_render_text": shot.should_render_text,
            "copy_source": shot.copy_source,
            "selling_points_for_render": shot.selling_points_for_render,
            "title_box": _box_to_payload(render_report.title_box),
            "subtitle_box": _box_to_payload(render_report.subtitle_box),
            "selling_points_boxes": [_box_to_payload(box) for box in render_report.selling_points_boxes],
        }
        return final_image, report, True

    final_image = _copy_generated_to_final(raw_image, final_dir)
    report = {
        "shot_id": shot.shot_id,
        "overlay_applied": False,
        "font_source": "",
        "fallback_used": False,
        "fallback_reason": "",
        "copy_strategy": shot.copy_strategy,
        "text_density": shot.text_density,
        "should_render_text": shot.should_render_text,
        "copy_source": shot.copy_source,
        "selling_points_for_render": shot.selling_points_for_render,
        "title_box": None,
        "subtitle_box": None,
        "selling_points_boxes": [],
    }
    return final_image, report, False


def _build_execution_shot(shot: PromptShot) -> PromptShot:
    """在渲染层补齐最终 prompt 装配，确保硬约束一定下发。"""

    assembled_prompt = _assemble_final_render_prompt(shot)
    return shot.model_copy(update={"render_prompt": assembled_prompt})


def _assemble_final_render_prompt(shot: PromptShot) -> str:
    """把 render 层硬约束、图内文案和参考图边界收口成最终 prompt。"""

    lines = [
        shot.render_prompt,
        "最终执行约束：广告文案只允许使用下列主标题、副标题、卖点，严禁转写、复用、概括任何参考图可见文字。",
        "最终执行约束：产品参考图只用于保持包装结构、材质、颜色与标签一致。",
        "最终执行约束：背景风格参考图只用于学习背景氛围、色调与场景语言，不得替换产品包装。",
        f"最终执行约束：copy_strategy={shot.copy_strategy}，text_density={shot.text_density}，should_render_text={str(shot.should_render_text).lower()}。",
    ]
    if shot.should_render_text and shot.title_copy:
        lines.append(f"主标题：{shot.title_copy}")
    if shot.should_render_text and shot.subtitle_copy:
        lines.append(f"副标题：{shot.subtitle_copy}")
    if shot.should_render_text and shot.selling_points_for_render:
        lines.append(f"卖点：{'；'.join(shot.selling_points_for_render)}")
    if shot.layout_hint:
        lines.append(f"文字区域：{shot.layout_hint}")
    if shot.typography_hint:
        lines.append(f"文字层级：{shot.typography_hint}")
    if shot.subject_occupancy_ratio:
        lines.append(f"主体占比目标：约 {int(shot.subject_occupancy_ratio * 100)}%，不要让商品过小。")
    if not shot.should_render_text or shot.copy_strategy == "none":
        lines.append("本图优先不要出现广告大字；如果模型倾向加字，也必须压到极轻程度。")
    return "\n".join(lines).strip()


def _publish_partial_render_result(
    *,
    base_state: WorkflowState,
    deps: WorkflowDependencies,
    task,
    images: list[GeneratedImage],
    text_render_reports: dict[str, dict[str, object]],
    logs: list[str],
    completed_count: int,
    total_count: int,
) -> None:
    """在 `render_images` 节点内部按张上报已完成结果。"""

    if deps.progress_callback is None:
        return

    progress_task = build_render_progress_task(task, completed_count=completed_count, total_count=total_count)
    generation_result = GenerationResult(images=list(images))
    deps.progress_callback(
        {
            **base_state,
            "task": progress_task,
            "generation_result": generation_result,
            "generation_result_v2": generation_result,
            "text_render_reports": dict(text_render_reports),
            "logs": list(logs),
            "current_step": progress_task.current_step,
            "current_step_label": progress_task.current_step_label,
            "progress_percent": progress_task.progress_percent,
            "error_message": "",
        }
    )


def _build_compatibility_plan(shot: PromptShot) -> ImagePromptPlan:
    """把 v2 shot 映射成兼容型 ImagePromptPlan。"""

    width, height = get_settings().resolve_output_dimensions(aspect_ratio=shot.aspect_ratio, image_size=shot.image_size)
    prompt = ImagePrompt(
        shot_id=shot.shot_id,
        shot_type=shot.shot_role,
        prompt=shot.render_prompt,
        generation_mode="t2i",
        output_size=f"{width}x{height}",
        text_safe_zone=shot.layout_hint,
    )
    return ImagePromptPlan(generation_mode="t2i", prompts=[prompt])


def _resolve_generation_context(
    *,
    provider,
    fallback_model_id: str,
    reference_assets: list,
    background_style_assets: list,
) -> dict[str, object]:
    """提取图片 provider 的最小执行上下文。"""

    if hasattr(provider, "resolve_generation_context"):
        context = provider.resolve_generation_context(
            reference_assets=reference_assets,
            background_style_assets=background_style_assets,
        )
        return {
            "generation_mode": getattr(context, "generation_mode", "t2i"),
            "model_id": getattr(context, "model_id", fallback_model_id),
            "reference_asset_ids": list(getattr(context, "reference_asset_ids", [])),
            "background_style_asset_ids": list(getattr(context, "background_style_asset_ids", [])),
        }
    return {
        "generation_mode": "t2i",
        "model_id": fallback_model_id,
        "reference_asset_ids": [asset.asset_id for asset in reference_assets],
        "background_style_asset_ids": [asset.asset_id for asset in background_style_assets],
    }


def _first_image(result: GenerationResult | None, shot_id: str) -> GeneratedImage | None:
    """返回生成结果中的第一张图。"""

    if result is None or not result.images:
        return None
    image = result.images[0]
    return image if image.shot_id == shot_id else image.model_copy(update={"shot_id": shot_id})


def _copy_generated_to_final(image: GeneratedImage, final_dir: Path) -> GeneratedImage:
    """把生成图复制到 `final` 目录，统一最终结果出口。"""

    final_path = final_dir / Path(image.image_path).name
    shutil.copyfile(image.image_path, final_path)
    return _build_final_image(shot_id=image.shot_id, final_path=final_path)


def _build_final_image(*, shot_id: str, final_path: Path) -> GeneratedImage:
    """从 final 文件构建最终输出对象。"""

    with Image.open(final_path) as payload:
        width, height = payload.size
    return GeneratedImage(
        shot_id=shot_id,
        image_path=str(final_path),
        preview_path=str(final_path),
        width=width,
        height=height,
        status="finalized",
    )


def _box_to_payload(box: tuple[int, int, int, int] | None) -> dict[str, int] | None:
    """把矩形框转换成可落盘结构。"""

    if box is None:
        return None
    return {"x": box[0], "y": box[1], "width": box[2], "height": box[3]}
