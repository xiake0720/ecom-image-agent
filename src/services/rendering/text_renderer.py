"""Pillow 中文后贴字服务。

文件位置：
- `src/services/rendering/text_renderer.py`

职责：
- 为 render_images 的 overlay fallback 提供最小可用的中文贴字能力
- 统一输出文字区域、字体来源和 fallback 标记，便于 QC 与排查
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OverlayRenderReport:
    """单张图的贴字报告。"""

    shot_id: str
    overlay_applied: bool
    font_source: str
    fallback_used: bool
    title_box: tuple[int, int, int, int] | None
    subtitle_box: tuple[int, int, int, int] | None
    selling_points_boxes: list[tuple[int, int, int, int]]


class TextRenderer:
    """负责把标题、副标题和卖点绘制到图片上。"""

    def __init__(self, default_font_path: Path) -> None:
        self.default_font_path = default_font_path

    def render_overlay(
        self,
        *,
        shot_id: str,
        image_path: str,
        output_path: str,
        title: str,
        subtitle: str,
        selling_points: list[str] | None,
        layout_hint: str,
    ) -> OverlayRenderReport:
        """在图片上绘制标题、副标题和卖点，并返回贴字报告。"""

        with Image.open(image_path).convert("RGBA") as base:
            canvas = base.copy()
            draw = ImageDraw.Draw(canvas)
            width, height = canvas.size
            title_font, title_source, title_fallback = self._load_font(max(46, width // 18))
            subtitle_font, subtitle_source, subtitle_fallback = self._load_font(max(28, width // 32))
            selling_point_font, selling_point_source, selling_point_fallback = self._load_font(max(24, width // 38))
            anchor_x, anchor_y, align = self._resolve_anchor(width, height, layout_hint)

            title_box = None
            subtitle_box = None
            selling_points_boxes: list[tuple[int, int, int, int]] = []
            current_y = anchor_y
            if title:
                title_box = self._draw_text_block(draw, title, title_font, anchor_x, current_y, align, fill=(255, 255, 255, 255))
                current_y = title_box[1] + title_box[3] + max(14, height // 80)
            if subtitle:
                subtitle_box = self._draw_text_block(draw, subtitle, subtitle_font, anchor_x, current_y, align, fill=(245, 245, 245, 255))
                current_y = subtitle_box[1] + subtitle_box[3] + max(12, height // 90)
            for selling_point in selling_points or []:
                point_box = self._draw_text_block(
                    draw,
                    f"· {selling_point}",
                    selling_point_font,
                    anchor_x,
                    current_y,
                    align,
                    fill=(235, 235, 235, 255),
                )
                selling_points_boxes.append(point_box)
                current_y = point_box[1] + point_box[3] + max(8, height // 120)

            canvas.save(output_path)
            font_source_candidates = [title_source, subtitle_source, selling_point_source]
            unique_font_sources = [source for index, source in enumerate(font_source_candidates) if source not in font_source_candidates[:index]]
            font_source = "|".join(unique_font_sources)
            return OverlayRenderReport(
                shot_id=shot_id,
                overlay_applied=True,
                font_source=font_source,
                fallback_used=title_fallback or subtitle_fallback or selling_point_fallback,
                title_box=title_box,
                subtitle_box=subtitle_box,
                selling_points_boxes=selling_points_boxes,
            )

    def _load_font(self, size: int) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, str, bool]:
        """优先加载项目字体，缺失时回退系统字体。"""

        settings = get_settings()
        candidates = [*settings.resolve_project_font_candidates(), *settings.resolve_system_chinese_font_candidates()]
        for candidate in candidates:
            if not candidate.exists():
                continue
            try:
                return ImageFont.truetype(str(candidate), size=size), str(candidate), False
            except OSError:
                continue
        logger.warning("No Chinese font candidate available, fallback to PIL default font.")
        return ImageFont.load_default(), "PIL_default", True

    def _resolve_anchor(self, width: int, height: int, layout_hint: str) -> tuple[int, int, str]:
        """把布局提示映射成锚点位置。"""

        hint = str(layout_hint or "").lower()
        left = max(80, width // 18)
        right = width - max(80, width // 18)
        top = max(80, height // 18)
        bottom = height - max(360, height // 4)
        if "right" in hint:
            return right, top, "right"
        if "bottom" in hint:
            return left, bottom, "left"
        return left, top, "left"

    def _draw_text_block(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        x: int,
        y: int,
        align: str,
        *,
        fill: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int]:
        """绘制单个文本块，并给文字加轻微阴影保证可读性。"""

        bbox = draw.textbbox((x, y), text, font=font, anchor="ra" if align == "right" else "la")
        shadow_offset = max(2, font.size // 18) if hasattr(font, "size") else 2
        shadow_position = (x + shadow_offset, y + shadow_offset)
        draw.text(shadow_position, text, font=font, fill=(0, 0, 0, 110), anchor="ra" if align == "right" else "la")
        draw.text((x, y), text, font=font, fill=fill, anchor="ra" if align == "right" else "la")
        return bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]
