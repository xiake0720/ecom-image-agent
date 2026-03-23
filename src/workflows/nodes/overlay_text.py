"""中文后贴字节点。

文件位置：
- `src/workflows/nodes/overlay_text.py`

核心职责：
<<<<<<< HEAD
- 保留 v1 的 Pillow 后贴字逻辑
- 为 v2 提供“只对 fallback 候选图补字”的选择性 overlay
- 统一把最终输出放入 `final/` 或 `final_preview/`，便于后续 QC 和结果页展示
=======
- 在生成图上叠加中文文案。
- 输出 preview / final 成品图。
- 记录 typography preset、自适应文字样式，以及实际文本渲染区域。

节点前后关系：
- 上游节点：`render_images`
- 下游节点：`run_qc`
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
"""

from __future__ import annotations

<<<<<<< HEAD
import shutil
=======
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
from pathlib import Path

from src.core.config import get_settings
from src.core.paths import get_task_final_dir, get_task_final_preview_dir, get_task_preview_dir
<<<<<<< HEAD
from src.domain.copy_plan import CopyItem
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.domain.layout_plan import LayoutBlock, LayoutItem
=======
from src.domain.generation_result import GeneratedImage, GenerationResult
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
from src.services.rendering.image_postprocess import save_preview
from src.workflows.state import WorkflowDependencies, WorkflowState


def overlay_text(state: WorkflowState, deps: WorkflowDependencies) -> dict:
<<<<<<< HEAD
    """执行 Pillow 中文后贴字，并兼容 v1/v2 两种路径。"""
    workflow_version = str(state.get("workflow_version") or get_settings().workflow_version or "v1").strip().lower()
    if workflow_version == "v2" and state.get("prompt_plan_v2") is not None:
        return _overlay_text_v2(state, deps)
    return _overlay_text_v1(state, deps)


def _overlay_text_v1(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """保留现有 v1 全量后贴字逻辑。"""
=======
    """执行 Pillow 中文后贴字并生成预览缩略图。

    关键副作用：
    - 写出最终贴字后的图片。
    - 回写每个 shot 的真实文本区域。
    - 额外落盘 `final_text_regions.json` 或 `preview_text_regions.json`，供 QC 和调试读取。
    """
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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
<<<<<<< HEAD
            render_blocks=render_report.blocks,
        )
=======
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
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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

<<<<<<< HEAD
    text_regions_filename = _resolve_text_regions_filename(render_variant)
    deps.storage.save_json_artifact(
        task.task_id,
        text_regions_filename,
        {
            "render_variant": render_variant,
            "workflow_version": "v1",
            "shots": [text_render_reports[shot_id] for shot_id in sorted(text_render_reports.keys())],
        },
    )
=======
    text_regions_payload = {
        "render_variant": render_variant,
        "shots": [text_render_reports[shot_id] for shot_id in sorted(text_render_reports.keys())],
    }
    text_regions_filename = _resolve_text_regions_filename(render_variant)
    deps.storage.save_json_artifact(task.task_id, text_regions_filename, text_regions_payload)

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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
<<<<<<< HEAD
=======
    # preview 阶段会额外保留一份结果，便于 UI 单独展示预览区并支持后续继续生成 final。
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    if render_variant == "preview":
        updates["preview_generation_result"] = result
    return updates


<<<<<<< HEAD
def _overlay_text_v2(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """仅对 v2 fallback 候选图执行后贴字，其余图片直接转存为最终结果。

    设计目的：
    - v2 仍然是“直出图内文案优先”
    - 只有失败图才允许退回 Pillow
    - 这样既保留新链路目标，也不会因为单张失败拖垮整组结果
    """
    task = state["task"]
    render_variant = str(state.get("render_variant") or "final")
    logs = [
        *state.get("logs", []),
        (
            f"[overlay_text] start workflow_version=v2 render_variant={render_variant} "
            f"image_count={len(state['generation_result'].images)} "
            f"text_render_preset={get_settings().resolve_text_render_preset()}"
        ),
    ]
    prompt_shot_map = {shot.shot_id: shot for shot in state["prompt_plan_v2"].shots}
    fallback_map = {
        str(item.get("shot_id")): item
        for item in state.get("overlay_fallback_candidates", []) or []
        if item.get("shot_id")
    }
    final_images: list[GeneratedImage] = []
    text_render_reports: dict[str, dict] = {}

    for image in state["generation_result"].images:
        final_base_dir = Path(get_task_final_preview_dir(task.task_id)) if render_variant == "preview" else Path(get_task_final_dir(task.task_id))
        final_path = final_base_dir / Path(image.image_path).name
        preview_thumb_path = Path(get_task_preview_dir(task.task_id)) / f"{render_variant}_{Path(image.image_path).name}"
        fallback_candidate = fallback_map.get(image.shot_id)
        prompt_shot = prompt_shot_map.get(image.shot_id)

        if fallback_candidate is not None and prompt_shot is not None:
            # v2 不再依赖旧 copy/layout 节点，这里现场把 prompt_plan_v2
            # 的标题、副标题和 layout_hint 合成为最小可用布局。
            copy_item = CopyItem(
                shot_id=prompt_shot.shot_id,
                title=prompt_shot.title_copy,
                subtitle=prompt_shot.subtitle_copy,
                bullets=[],
                cta=None,
            )
            layout_item = _build_v2_layout_item(prompt_shot, image)
            render_report = deps.text_renderer.render_copy(
                input_image_path=image.image_path,
                copy_item=copy_item,
                layout_item=layout_item,
                output_path=str(final_path),
            )
            text_render_reports[image.shot_id] = _build_text_region_report(
                shot_id=image.shot_id,
                output_path=render_report.output_path,
                render_blocks=render_report.blocks,
            )
            logs.append(
                f"[overlay_text] v2 overlay applied shot_id={image.shot_id} reason={fallback_candidate.get('reason', '-')}"
            )
        else:
            # 没有进入 fallback 的图片直接透传，避免对“已经直出成功”的结果
            # 再做二次加工，保持 v2 的原始输出。
            final_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(image.image_path, final_path)
            text_render_reports[image.shot_id] = {
                "shot_id": image.shot_id,
                "output_path": str(final_path),
                "actual_text_regions": [],
                "merged_text_region": None,
                "title_region": None,
                "subtitle_region": None,
                "blocks": [],
                "overlay_applied": False,
            }
            logs.append(f"[overlay_text] v2 passthrough shot_id={image.shot_id} overlay_applied=false")

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

    result = GenerationResult(images=final_images)
    text_regions_filename = _resolve_text_regions_filename(render_variant)
    deps.storage.save_json_artifact(
        task.task_id,
        text_regions_filename,
        {
            "render_variant": render_variant,
            "workflow_version": "v2",
            "shots": [text_render_reports[shot_id] for shot_id in sorted(text_render_reports.keys())],
        },
    )
    updates = {
        "generation_result": result,
        "generation_result_v2": result,
        "text_render_reports": text_render_reports,
        "needs_overlay_fallback": False,
        "logs": [
            *logs,
            f"[overlay_text] saved_text_regions={text_regions_filename}",
            f"[overlay_text] completed workflow_version=v2 render_variant={render_variant} finalized_images={len(final_images)}",
        ],
    }
    if render_variant == "preview":
        updates["preview_generation_result"] = result
    return updates


def _build_v2_layout_item(prompt_shot, image: GeneratedImage) -> LayoutItem:
    """根据 v2 的 layout_hint 合成最小可用布局。

    这里不是要复刻旧 layout 节点，而是给 fallback 一条能稳定落地的最小路径：
    - 只生成 title/subtitle 两个块
    - 优先从 `layout_hint` 推断安全区
    - 字号和块尺寸按画布比例做保守估算
    """
    text_safe_zone = _resolve_text_safe_zone_from_hint(prompt_shot.layout_hint)
    title_font_size = max(48, int(min(image.width, image.height) * 0.055))
    subtitle_font_size = max(28, int(title_font_size * 0.62))
    title_x, title_y = _resolve_anchor_position(
        text_safe_zone=text_safe_zone,
        canvas_width=image.width,
        canvas_height=image.height,
        title_block_height=int(image.height * 0.10),
    )
    block_width = int(image.width * 0.34)
    title_height = int(image.height * 0.10)
    subtitle_height = int(image.height * 0.08)
    gap = int(image.height * 0.02)
    return LayoutItem(
        shot_id=prompt_shot.shot_id,
        canvas_width=image.width,
        canvas_height=image.height,
        text_safe_zone=text_safe_zone,
        selection_reason=f"v2 layout_hint synthesized from: {prompt_shot.layout_hint}",
        blocks=[
            LayoutBlock(
                kind="title",
                x=title_x,
                y=title_y,
                width=block_width,
                height=title_height,
                font_size=title_font_size,
            ),
            LayoutBlock(
                kind="subtitle",
                x=title_x,
                y=title_y + title_height + gap,
                width=block_width,
                height=subtitle_height,
                font_size=subtitle_font_size,
            ),
        ],
    )


def _resolve_text_safe_zone_from_hint(layout_hint: str) -> str:
    """从 v2 layout_hint 中推断最接近的安全区。"""
    hint = str(layout_hint or "").strip().lower()
    if "左上" in hint or "left top" in hint or "top left" in hint:
        return "top_left"
    if "右上" in hint or "right top" in hint or "top right" in hint or "顶部" in hint or "top" in hint:
        return "top_right"
    if "左下" in hint or "bottom left" in hint:
        return "bottom_left"
    if "右下" in hint or "bottom right" in hint or "底部" in hint or "bottom" in hint:
        return "bottom_right"
    if "左侧" in hint or "left" in hint:
        return "left_center"
    if "右侧" in hint or "right" in hint:
        return "right_center"
    return "top_right"


def _resolve_anchor_position(*, text_safe_zone: str, canvas_width: int, canvas_height: int, title_block_height: int) -> tuple[int, int]:
    """根据安全区给标题块定位。"""
    left_margin = int(canvas_width * 0.06)
    right_margin = int(canvas_width * 0.60)
    top_margin = int(canvas_height * 0.07)
    center_y = int(canvas_height * 0.38)
    bottom_y = int(canvas_height * 0.70)
    if text_safe_zone == "top_left":
        return left_margin, top_margin
    if text_safe_zone == "top_right":
        return right_margin, top_margin
    if text_safe_zone == "left_center":
        return left_margin, center_y
    if text_safe_zone == "right_center":
        return right_margin, center_y
    if text_safe_zone == "bottom_left":
        return left_margin, bottom_y
    if text_safe_zone == "bottom_right":
        return right_margin, bottom_y
    return right_margin, top_margin + max(title_block_height // 10, 1)


def _build_text_region_report(*, shot_id: str, output_path: str, render_blocks: list) -> dict:
=======
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
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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
<<<<<<< HEAD
=======
            "min_font_size_hit": block.min_font_size_hit,
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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
<<<<<<< HEAD
=======
        "font_source": font_source,
        "font_loaded": font_loaded,
        "fallback_used": fallback_used,
        "requested_font_path": requested_font_path,
        "resolved_font_path": resolved_font_path,
        "fallback_target": fallback_target,
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        "actual_text_regions": actual_text_regions,
        "merged_text_region": _merge_text_regions(actual_text_regions),
        "title_region": _first_region_by_kind(actual_text_regions, "title"),
        "subtitle_region": _first_region_by_kind(actual_text_regions, "subtitle"),
        "blocks": actual_text_regions,
<<<<<<< HEAD
        "overlay_applied": True,
=======
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    }


def _merge_text_regions(regions: list[dict]) -> dict | None:
<<<<<<< HEAD
    """把多个文本块合并成一个总区域。"""
=======
    """把多个文本块合并成一个总区域，供 QC 快速判断是否压主体。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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
<<<<<<< HEAD
    """取某类文本块的首个区域。"""
=======
    """取某类文本块的首个区域，便于调试标题和副标题。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    for region in regions:
        if region.get("kind") == kind:
            return region
    return None


def _resolve_text_regions_filename(render_variant: str) -> str:
    """根据 preview/final 返回对应的文本区域 artifact 文件名。"""
    return "preview_text_regions.json" if render_variant == "preview" else "final_text_regions.json"
