"""中文后贴字节点。

文件位置：
- `src/workflows/nodes/overlay_text.py`

核心职责：
- 在生成图上叠加中文文案。
- 输出 preview / final 成品图。
- 记录 typography preset、自适应文字样式，以及实际文本渲染区域。

节点前后关系：
- 上游节点：`render_images`
- 下游节点：`run_qc`
"""

from __future__ import annotations

from pathlib import Path

from src.core.config import get_settings
from src.core.paths import get_task_final_dir, get_task_final_preview_dir, get_task_preview_dir
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.services.rendering.image_postprocess import save_preview
from src.workflows.state import WorkflowDependencies, WorkflowState


def overlay_text(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """执行 Pillow 中文后贴字并生成预览缩略图。

    关键副作用：
    - 写出最终贴字后的图片。
    - 回写每个 shot 的真实文本区域。
    - 额外落盘 `final_text_regions.json` 或 `preview_text_regions.json`，供 QC 和调试读取。
    """
    task = state["task"]
    render_variant = str(state.get("render_variant") or "final")
    logs = [
        *state.get("logs", []),
        (
            f"[overlay_text] start render_variant={render_variant} "
            f"image_count={len(state['generation_result'].images)} "
            f"text_render_preset={get_settings().resolve_text_render_preset()}"
        ),
    ]
    copy_map = {item.shot_id: item for item in state["copy_plan"].items}
    layout_map = {item.shot_id: item for item in state["layout_plan"].items}
    final_images: list[GeneratedImage] = []
    text_render_reports: dict[str, dict] = {}

    for image in state["generation_result"].images:
        final_base_dir = Path(get_task_final_preview_dir(task.task_id)) if render_variant == "preview" else Path(get_task_final_dir(task.task_id))
        final_path = final_base_dir / Path(image.image_path).name
        preview_thumb_path = Path(get_task_preview_dir(task.task_id)) / f"{render_variant}_{Path(image.image_path).name}"
        render_report = deps.text_renderer.render_copy(
            input_image_path=image.image_path,
            copy_item=copy_map[image.shot_id],
            layout_item=layout_map[image.shot_id],
            output_path=str(final_path),
        )
        normalized_report = _build_text_region_report(
            shot_id=image.shot_id,
            output_path=render_report.output_path,
            font_source=render_report.font_source,
            font_loaded=render_report.font_loaded,
            fallback_used=render_report.fallback_used,
            requested_font_path=render_report.requested_font_path,
            resolved_font_path=render_report.resolved_font_path,
            fallback_target=render_report.fallback_target,
            render_blocks=render_report.blocks,
        )
        block_summaries = [
            (
                f"{block.kind}:preset={block.typography_preset},"
                f"color={block.text_color},"
                f"plate={block.background_plate_applied},"
                f"shadow={block.shadow_applied},"
                f"stroke={block.stroke_applied},"
                f"requested_font_size={block.requested_font_size},"
                f"used_font_size={block.used_font_size},"
                f"min_font_size_hit={block.min_font_size_hit},"
                f"overflow_detected={block.overflow_detected}"
            )
            for block in render_report.blocks
        ]
        logs.append(
            (
                "[overlay] "
                f"shot_id={image.shot_id} "
                f"typography_preset={get_settings().resolve_text_render_preset()} "
                f"adaptive_color_result={block_summaries or ['no_text_blocks_rendered']}"
            )
        )
        logs.append(
            (
                "[overlay] "
                f"shot_id={image.shot_id} "
                f"font_source={render_report.font_source} "
                f"font_loaded={render_report.font_loaded} "
                f"fallback_used={render_report.fallback_used} "
                f"resolved_font_path={render_report.resolved_font_path} "
                f"fallback_target={render_report.fallback_target or '-'}"
            )
        )
        logs.append(
            (
                "[overlay] "
                f"shot_id={image.shot_id} "
                f"actual_text_regions={len(normalized_report['actual_text_regions'])} "
                f"merged_text_region={normalized_report['merged_text_region'] or '-'}"
            )
        )
        text_render_reports[image.shot_id] = normalized_report
        save_preview(str(final_path), preview_thumb_path)
        final_images.append(
            image.model_copy(
                update={
                    "image_path": str(final_path),
                    "preview_path": str(preview_thumb_path),
                    "status": "finalized",
                }
            )
        )

    text_regions_payload = {
        "render_variant": render_variant,
        "shots": [text_render_reports[shot_id] for shot_id in sorted(text_render_reports.keys())],
    }
    text_regions_filename = _resolve_text_regions_filename(render_variant)
    deps.storage.save_json_artifact(task.task_id, text_regions_filename, text_regions_payload)

    result = GenerationResult(images=final_images)
    updates = {
        "generation_result": result,
        "text_render_reports": text_render_reports,
        "logs": [
            *logs,
            f"[overlay_text] saved_text_regions={text_regions_filename}",
            f"[overlay_text] completed render_variant={render_variant} finalized_images={len(final_images)}",
            "[overlay_text] chinese copy overlay finished with Pillow",
        ],
    }
    # preview 阶段会额外保留一份结果，便于 UI 单独展示预览区并支持后续继续生成 final。
    if render_variant == "preview":
        updates["preview_generation_result"] = result
    return updates


def _build_text_region_report(
    *,
    shot_id: str,
    output_path: str,
    font_source: str,
    font_loaded: bool,
    fallback_used: bool,
    requested_font_path: str,
    resolved_font_path: str,
    fallback_target: str | None,
    render_blocks: list,
) -> dict:
    """把文本渲染报告归一化成便于 QC 和落盘的结构。"""
    actual_text_regions = [
        {
            "kind": block.kind,
            "x": block.x,
            "y": block.y,
            "width": block.width,
            "height": block.height,
            "requested_font_size": block.requested_font_size,
            "used_font_size": block.used_font_size,
            "min_font_size_hit": block.min_font_size_hit,
            "line_count": block.line_count,
            "density_ratio": block.density_ratio,
            "overflow_detected": block.overflow_detected,
        }
        for block in render_blocks
        if block.width > 0 and block.height > 0
    ]
    return {
        "shot_id": shot_id,
        "output_path": output_path,
        "font_source": font_source,
        "font_loaded": font_loaded,
        "fallback_used": fallback_used,
        "requested_font_path": requested_font_path,
        "resolved_font_path": resolved_font_path,
        "fallback_target": fallback_target,
        "actual_text_regions": actual_text_regions,
        "merged_text_region": _merge_text_regions(actual_text_regions),
        "title_region": _first_region_by_kind(actual_text_regions, "title"),
        "subtitle_region": _first_region_by_kind(actual_text_regions, "subtitle"),
        "blocks": actual_text_regions,
    }


def _merge_text_regions(regions: list[dict]) -> dict | None:
    """把多个文本块合并成一个总区域，供 QC 快速判断是否压主体。"""
    if not regions:
        return None
    left = min(int(region["x"]) for region in regions)
    top = min(int(region["y"]) for region in regions)
    right = max(int(region["x"]) + int(region["width"]) for region in regions)
    bottom = max(int(region["y"]) + int(region["height"]) for region in regions)
    return {
        "x": left,
        "y": top,
        "width": right - left,
        "height": bottom - top,
    }


def _first_region_by_kind(regions: list[dict], kind: str) -> dict | None:
    """取某类文本块的首个区域，便于调试标题和副标题。"""
    for region in regions:
        if region.get("kind") == kind:
            return region
    return None


def _resolve_text_regions_filename(render_variant: str) -> str:
    """根据 preview/final 返回对应的文本区域 artifact 文件名。"""
    return "preview_text_regions.json" if render_variant == "preview" else "final_text_regions.json"
