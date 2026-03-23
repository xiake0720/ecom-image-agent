"""Pillow 中文后贴字渲染器。

文件位置：
- `src/services/rendering/text_renderer.py`

核心职责：
<<<<<<< HEAD
- 定义 typography token
- 根据背景自适应选择深浅字、阴影、描边和底板
- 按布局把标题、副标题、卖点、CTA 渲染到最终图片
=======
- 定义文字 preset 与自适应样式。
- 在图片上执行标题、副标题、卖点、CTA 的中文后贴字。
- 返回可供 workflow、QC 和测试链路消费的结构化渲染报告。
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
"""

from __future__ import annotations

from dataclasses import dataclass
<<<<<<< HEAD
=======
import json
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
import logging
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageStat

<<<<<<< HEAD
from src.core.config import get_settings
from src.domain.copy_plan import CopyItem
from src.domain.layout_plan import LayoutBlock, LayoutItem
from src.services.rendering.font_utils import load_font
=======
from src.core.config import Settings, get_settings
from src.domain.copy_plan import CopyItem
from src.domain.layout_plan import LayoutBlock, LayoutItem
from src.services.rendering.font_utils import LoadedFont, load_font
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShadowConfig:
<<<<<<< HEAD
=======
    """阴影绘制参数。"""

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    enabled: bool
    offset_x: int
    offset_y: int
    fill: tuple[int, int, int, int]


@dataclass(frozen=True)
class StrokeConfig:
<<<<<<< HEAD
=======
    """描边绘制参数。"""

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    enabled: bool
    width: int
    fill: tuple[int, int, int, int]


@dataclass(frozen=True)
class PlateConfig:
<<<<<<< HEAD
=======
    """底板绘制参数。"""

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    enabled: bool
    padding_x: int
    padding_y: int
    radius: int
    fill: tuple[int, int, int, int]


@dataclass(frozen=True)
class TypographyToken:
<<<<<<< HEAD
=======
    """不同文字块使用的基础排版 token。"""

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    kind: str
    font_size: int
    line_height: float
    letter_spacing: int
    font_weight: str
    text_color_default: tuple[int, int, int]
    shadow_strategy: str
    stroke_strategy: str
    background_plate_strategy: str


@dataclass(frozen=True)
class ResolvedTextStyle:
<<<<<<< HEAD
=======
    """基于背景局部区域解析出的最终文字样式。"""

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    text_color: tuple[int, int, int, int]
    accent_color: tuple[int, int, int, int]
    shadow: ShadowConfig
    stroke: StrokeConfig
    plate: PlateConfig
    prefer_light_text: bool
    mean_luminance: float
    luminance_stddev: float
    contrast_with_choice: float


<<<<<<< HEAD
@dataclass
class PlacedTextBlock:
    kind: str
    requested_font_size: int
    used_font_size: int
=======
@dataclass(frozen=True)
class FitTextResult:
    """记录一个文字块在尺寸约束下的适配结果。"""

    lines: list[str]
    requested_font_size: int
    used_font_size: int
    min_font_size_hit: bool
    overflow_detected: bool
    font_info: LoadedFont


@dataclass
class PlacedTextBlock:
    """记录单个文字块的真实渲染结果。"""

    kind: str
    requested_font_size: int
    used_font_size: int
    min_font_size_hit: bool
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    line_count: int
    x: int
    y: int
    width: int
    height: int
    block_width: int
    block_height: int
    density_ratio: float
    overflow_detected: bool
    typography_preset: str
    text_color: tuple[int, int, int, int]
    background_plate_applied: bool
    shadow_applied: bool
    stroke_applied: bool


@dataclass
class TextRenderReport:
<<<<<<< HEAD
    output_path: str
    blocks: list[PlacedTextBlock]
=======
    """整张图的文字渲染结果。"""

    output_path: str
    blocks: list[PlacedTextBlock]
    font_source: str
    font_loaded: bool
    fallback_used: bool
    requested_font_path: str
    resolved_font_path: str
    fallback_target: str | None
    test_metadata_path: str | None = None
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c


PRESET_TOKENS: dict[str, dict[str, TypographyToken]] = {
    "premium_minimal": {
        "title": TypographyToken("title", 96, 1.12, 1, "semi_bold", (244, 241, 236), "auto_soft", "auto_subtle", "auto_minimal"),
        "subtitle": TypographyToken("subtitle", 46, 1.24, 0, "regular", (235, 232, 227), "auto_soft", "auto_none", "auto_rare"),
        "bullets": TypographyToken("bullets", 38, 1.32, 0, "regular", (232, 229, 224), "auto_soft", "auto_none", "auto_rare"),
<<<<<<< HEAD
        "cta": TypographyToken("cta", 32, 1.1, 1, "medium", (245, 244, 241), "auto_soft", "auto_subtle", "prefer_plate"),
=======
        "cta": TypographyToken("cta", 32, 1.10, 1, "medium", (245, 244, 241), "auto_soft", "auto_subtle", "prefer_plate"),
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    },
    "commercial_balanced": {
        "title": TypographyToken("title", 102, 1.14, 1, "semi_bold", (244, 241, 236), "auto_soft", "auto_subtle", "auto_supportive"),
        "subtitle": TypographyToken("subtitle", 50, 1.26, 0, "regular", (236, 232, 228), "auto_soft", "auto_subtle", "auto_supportive"),
        "bullets": TypographyToken("bullets", 40, 1.34, 0, "regular", (234, 230, 226), "auto_soft", "auto_none", "auto_supportive"),
        "cta": TypographyToken("cta", 34, 1.12, 1, "medium", (245, 244, 241), "auto_soft", "auto_subtle", "prefer_plate"),
    },
}


class TextRenderer:
    """中文后贴字主渲染器。"""
<<<<<<< HEAD
    def __init__(self, font_path: Path | None = None, *, preset_name: str | None = None) -> None:
        settings = get_settings()
        self.font_path = font_path or settings.default_font_path
        self.preset_name = preset_name or settings.resolve_text_render_preset()
        self.adaptive_style_enabled = bool(settings.text_render_adaptive_style_enabled)
=======

    def __init__(self, font_path: Path | None = None, *, preset_name: str | None = None) -> None:
        settings = get_settings()
        self.settings: Settings = settings
        self.font_path = font_path or settings.default_font_path
        self.preset_name = preset_name or settings.resolve_text_render_preset()
        self.adaptive_style_enabled = bool(settings.text_render_adaptive_style_enabled)
        self.project_font_candidates = settings.resolve_project_font_candidates(self.font_path)
        self.system_font_candidates = settings.resolve_system_chinese_font_candidates()
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c

    def render_copy(
        self,
        *,
        input_image_path: str,
        copy_item: CopyItem,
        layout_item: LayoutItem,
        output_path: str,
    ) -> TextRenderReport:
<<<<<<< HEAD
        """在单张图片上渲染结构化中文文案并落盘成品图。"""
        logger.info(
            "开始执行中文后贴字，shot_id=%s，输入=%s，输出=%s，布局块数量=%s，preset=%s",
=======
        """在单张图片上渲染结构化中文文案并输出结构化报告。"""
        logger.info(
            "Start text rendering: shot_id=%s, input=%s, output=%s, block_count=%s, preset=%s, configured_font=%s",
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
            copy_item.shot_id,
            input_image_path,
            output_path,
            len(layout_item.blocks),
            self.preset_name,
<<<<<<< HEAD
=======
            self.font_path,
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        )
        with Image.open(input_image_path).convert("RGBA") as image:
            analysis_image = image.copy()
            draw = ImageDraw.Draw(image)
            reports: list[PlacedTextBlock] = []
<<<<<<< HEAD
=======
            active_font_info: LoadedFont | None = None

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
            for block in layout_item.blocks:
                text = self._resolve_text(copy_item, block)
                if not text:
                    continue
                token = self._get_typography_token(block.kind)
<<<<<<< HEAD
                lines, font_size = self._fit_text(draw, text, block, token, layout_item)
                font = load_font(self.font_path, font_size)
                style = self._resolve_text_style(analysis_image, block, token, layout_item)
                placement = self._draw_lines(draw, lines, block, font, token, style, layout_item)
                reports.append(
                    PlacedTextBlock(
                        kind=block.kind,
                        requested_font_size=self._requested_font_size(block, token, layout_item),
                        used_font_size=font_size,
                        line_count=len(lines),
=======
                fit_result = self._fit_text(draw, text, block, token, layout_item)
                active_font_info = fit_result.font_info
                style = self._resolve_text_style(analysis_image, block, token, layout_item)
                placement = self._draw_lines(
                    draw,
                    fit_result.lines,
                    block,
                    fit_result.font_info.font,
                    token,
                    style,
                )
                logger.info(
                    "Rendered text block: shot_id=%s, kind=%s, requested_font_size=%s, used_font_size=%s, min_font_size_hit=%s, overflow_detected=%s, font_source=%s, resolved_font_path=%s, fallback_used=%s, fallback_target=%s",
                    copy_item.shot_id,
                    block.kind,
                    fit_result.requested_font_size,
                    fit_result.used_font_size,
                    fit_result.min_font_size_hit,
                    fit_result.overflow_detected,
                    fit_result.font_info.font_source,
                    fit_result.font_info.resolved_font_path,
                    fit_result.font_info.fallback_used,
                    fit_result.font_info.fallback_target,
                )
                reports.append(
                    PlacedTextBlock(
                        kind=block.kind,
                        requested_font_size=fit_result.requested_font_size,
                        used_font_size=fit_result.used_font_size,
                        min_font_size_hit=fit_result.min_font_size_hit,
                        line_count=len(fit_result.lines),
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
                        x=placement["x"],
                        y=placement["y"],
                        width=placement["width"],
                        height=placement["height"],
                        block_width=block.width,
                        block_height=block.height,
                        density_ratio=placement["density_ratio"],
<<<<<<< HEAD
                        overflow_detected=placement["overflow_detected"],
=======
                        overflow_detected=fit_result.overflow_detected or placement["overflow_detected"],
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
                        typography_preset=self.preset_name,
                        text_color=style.text_color,
                        background_plate_applied=style.plate.enabled,
                        shadow_applied=style.shadow.enabled,
                        stroke_applied=style.stroke.enabled,
                    )
                )
<<<<<<< HEAD
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            image.convert("RGB").save(target)
        logger.info(
            "中文后贴字完成，shot_id=%s，输出=%s，实际渲染块数量=%s，preset=%s",
            copy_item.shot_id,
            output_path,
            len(reports),
            self.preset_name,
        )
        return TextRenderReport(output_path=str(output_path), blocks=reports)

    def render_test_image(self, output_path: str) -> TextRenderReport:
        logger.info("开始生成文本渲染测试样图，输出=%s", output_path)
        sample = Image.new("RGB", (1440, 1440), color=(245, 241, 229))
        temp_path = Path(output_path).with_name("text_render_base.png")
        sample.save(temp_path)
=======

            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            image.convert("RGB").save(target)

        final_font_info = active_font_info or self._load_font(
            self.settings.resolve_text_render_min_font_size("title")
        )
        logger.info(
            "Completed text rendering: shot_id=%s, output=%s, rendered_blocks=%s, font_source=%s, resolved_font_path=%s, fallback_used=%s",
            copy_item.shot_id,
            output_path,
            len(reports),
            final_font_info.font_source,
            final_font_info.resolved_font_path,
            final_font_info.fallback_used,
        )
        return TextRenderReport(
            output_path=str(output_path),
            blocks=reports,
            font_source=final_font_info.font_source,
            font_loaded=final_font_info.font_loaded,
            fallback_used=final_font_info.fallback_used,
            requested_font_path=final_font_info.requested_font_path,
            resolved_font_path=final_font_info.resolved_font_path,
            fallback_target=final_font_info.fallback_target,
        )

    def render_test_image(self, output_path: str) -> TextRenderReport:
        """生成专门用于人工检查中文字体与字号的测试图。"""
        logger.info("Start generating text render test artifact: output=%s", output_path)
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        sample = Image.new("RGB", (1440, 1440), color=(243, 239, 229))
        sample_draw = ImageDraw.Draw(sample)
        sample_draw.rounded_rectangle((70, 80, 1370, 1360), radius=44, fill=(233, 225, 210))
        sample_draw.rounded_rectangle((90, 110, 1030, 980), radius=36, fill=(198, 183, 157))
        sample_draw.rounded_rectangle((1000, 220, 1320, 1150), radius=28, fill=(217, 205, 183))

        temp_path = target.with_name("text_render_base.png")
        sample.save(temp_path)

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        layout = LayoutItem(
            shot_id="sample",
            canvas_width=1440,
            canvas_height=1440,
            blocks=[
<<<<<<< HEAD
                LayoutBlock(kind="title", x=90, y=120, width=600, height=220, font_size=96),
                LayoutBlock(kind="subtitle", x=90, y=360, width=560, height=180, font_size=48),
                LayoutBlock(kind="bullets", x=90, y=570, width=520, height=260, font_size=40),
                LayoutBlock(kind="cta", x=90, y=860, width=320, height=90, font_size=32),
=======
                LayoutBlock(kind="title", x=110, y=120, width=880, height=230, font_size=96),
                LayoutBlock(kind="subtitle", x=110, y=380, width=860, height=170, font_size=48),
                LayoutBlock(kind="bullets", x=110, y=590, width=820, height=250, font_size=40),
                LayoutBlock(kind="cta", x=110, y=880, width=360, height=90, font_size=32),
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
            ],
        )
        copy_item = CopyItem(
            shot_id="sample",
<<<<<<< HEAD
            title="高山云雾 原叶鲜香",
            subtitle="自动换行与缩字示例，适合作为测试渲染样图",
            bullets=["标题", "副标题", "卖点条目"],
            cta="立即了解",
        )
        return self.render_copy(
=======
            title="高山云雾鲜爽回甘",
            subtitle="真实中文字体测试图，用来确认字号、字形和换行是否仍然适合电商主图。",
            bullets=[
                "标题不会再无底线缩到极小字号",
                "字体缺失时会明确暴露 fallback 来源",
                "卖点列表便于肉眼检查字重与可读性",
            ],
            cta="立即查看",
        )
        report = self.render_copy(
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
            input_image_path=str(temp_path),
            copy_item=copy_item,
            layout_item=layout,
            output_path=output_path,
        )

<<<<<<< HEAD
    def _resolve_text(self, copy_item: CopyItem, block: LayoutBlock) -> str:
=======
        metadata_path = target.with_suffix(".meta.json")
        metadata = {
            "output_path": report.output_path,
            "font_source": report.font_source,
            "font_loaded": report.font_loaded,
            "fallback_used": report.fallback_used,
            "requested_font_path": report.requested_font_path,
            "resolved_font_path": report.resolved_font_path,
            "fallback_target": report.fallback_target,
            "blocks": [
                {
                    "kind": block.kind,
                    "requested_font_size": block.requested_font_size,
                    "used_font_size": block.used_font_size,
                    "min_font_size_hit": block.min_font_size_hit,
                    "overflow_detected": block.overflow_detected,
                    "line_count": block.line_count,
                }
                for block in report.blocks
            ],
        }
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        report.test_metadata_path = str(metadata_path)
        logger.info(
            "Text render test artifact generated: image=%s, metadata=%s, font_source=%s, fallback_used=%s",
            output_path,
            metadata_path,
            report.font_source,
            report.fallback_used,
        )
        return report

    def _resolve_text(self, copy_item: CopyItem, block: LayoutBlock) -> str:
        """按 block 类型提取当前要渲染的文本。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        if block.kind == "title":
            return copy_item.title
        if block.kind == "subtitle":
            return copy_item.subtitle
        if block.kind == "bullets":
<<<<<<< HEAD
            return "\n".join(f"• {item}" for item in copy_item.bullets)
=======
            return "\n".join(f"- {item}" for item in copy_item.bullets)
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        if block.kind == "cta":
            return copy_item.cta or ""
        return ""

    def _fit_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        block: LayoutBlock,
        token: TypographyToken,
        layout_item: LayoutItem,
<<<<<<< HEAD
    ) -> tuple[list[str], int]:
        font_size = self._requested_font_size(block, token, layout_item)
        min_size = 18
        while font_size >= min_size:
            font = load_font(self.font_path, font_size)
            lines = self._wrap_text(draw, text, font, block.width, token.letter_spacing)
            line_height = max(self._line_height(draw, font), int(font_size * token.line_height))
            total_height = len(lines) * line_height + max(0, len(lines) - 1) * max(4, int(font_size * 0.08))
            if total_height <= block.height:
                return lines, font_size
            font_size -= 2
        font = load_font(self.font_path, min_size)
        return self._wrap_text(draw, text, font, block.width, token.letter_spacing), min_size

    def _wrap_text(self, draw: ImageDraw.ImageDraw, text: str, font, max_width: int, letter_spacing: int) -> list[str]:
=======
    ) -> FitTextResult:
        """按 block 尺寸约束寻找可接受的字号，但不会低于最小可读字号。"""
        requested_font_size = self._requested_font_size(block, token, layout_item)
        min_font_size = self.settings.resolve_text_render_min_font_size(block.kind)
        current_font_size = max(requested_font_size, min_font_size)
        last_result: FitTextResult | None = None

        while current_font_size >= min_font_size:
            font_info = self._load_font(current_font_size)
            lines = self._wrap_text(draw, text, font_info.font, block.width, token.letter_spacing)
            text_width, total_height, _, _ = self._measure_text_block(draw, lines, font_info.font, token)
            overflow_detected = text_width > block.width or total_height > block.height
            fit_result = FitTextResult(
                lines=lines,
                requested_font_size=requested_font_size,
                used_font_size=current_font_size,
                min_font_size_hit=current_font_size == min_font_size,
                overflow_detected=overflow_detected,
                font_info=font_info,
            )
            if not overflow_detected:
                return fit_result
            last_result = fit_result
            if current_font_size == min_font_size:
                break
            current_font_size = max(min_font_size, current_font_size - 2)

        if last_result is None:
            font_info = self._load_font(min_font_size)
            last_result = FitTextResult(
                lines=self._wrap_text(draw, text, font_info.font, block.width, token.letter_spacing),
                requested_font_size=requested_font_size,
                used_font_size=min_font_size,
                min_font_size_hit=True,
                overflow_detected=True,
                font_info=font_info,
            )
        return FitTextResult(
            lines=last_result.lines,
            requested_font_size=last_result.requested_font_size,
            used_font_size=last_result.used_font_size,
            min_font_size_hit=True,
            overflow_detected=True,
            font_info=last_result.font_info,
        )

    def _wrap_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font,
        max_width: int,
        letter_spacing: int,
    ) -> list[str]:
        """按宽度约束逐字换行，保证中文场景稳定。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        lines: list[str] = []
        for raw_line in text.splitlines() or [""]:
            current = ""
            for char in raw_line:
                candidate = f"{current}{char}"
                width = self._measure_text_width(draw, candidate, font, letter_spacing)
                if width <= max_width or not current:
                    current = candidate
                else:
                    lines.append(current)
                    current = char
<<<<<<< HEAD
            lines.append(current)
        return [line for line in lines if line]
=======
            if current:
                lines.append(current)
        return lines
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c

    def _draw_lines(
        self,
        draw: ImageDraw.ImageDraw,
        lines: Iterable[str],
        block: LayoutBlock,
        font,
        token: TypographyToken,
        style: ResolvedTextStyle,
<<<<<<< HEAD
        layout_item: LayoutItem,
    ) -> dict[str, int | float | bool]:
        lines = list(lines)
        if not lines:
=======
    ) -> dict[str, int | float | bool]:
        """将排好版的文本行绘制到图片上，并返回真实占位区域。"""
        resolved_lines = list(lines)
        if not resolved_lines:
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
            return {
                "x": block.x,
                "y": block.y,
                "width": 0,
                "height": 0,
                "density_ratio": 0.0,
                "overflow_detected": False,
            }
<<<<<<< HEAD
        line_height = max(self._line_height(draw, font), int(font.size * token.line_height)) if hasattr(font, "size") else self._line_height(draw, font)
        spacing = max(4, int((font.size if hasattr(font, "size") else 24) * 0.08))
        line_widths = [self._measure_text_width(draw, line, font, token.letter_spacing) for line in lines]
        text_width = max(line_widths) if line_widths else 0
        total_height = len(lines) * line_height + max(0, len(lines) - 1) * spacing
=======

        text_width, total_height, line_height, spacing = self._measure_text_block(draw, resolved_lines, font, token)
        line_widths = [self._measure_text_width(draw, line, font, token.letter_spacing) for line in resolved_lines]

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        plate_x0 = block.x
        plate_x1 = block.x + text_width
        if block.align == "center":
            plate_x0 = block.x + max(0, (block.width - text_width) // 2)
            plate_x1 = plate_x0 + text_width
        plate_y0 = block.y
        plate_y1 = block.y + total_height
<<<<<<< HEAD
=======

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        if style.plate.enabled:
            draw.rounded_rectangle(
                (
                    plate_x0 - style.plate.padding_x,
                    plate_y0 - style.plate.padding_y,
                    plate_x1 + style.plate.padding_x,
                    plate_y1 + style.plate.padding_y,
                ),
                radius=style.plate.radius,
                fill=style.plate.fill,
            )
<<<<<<< HEAD
        y = block.y
        for line, line_width in zip(lines, line_widths):
=======

        current_y = block.y
        for line, line_width in zip(resolved_lines, line_widths):
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
            draw_x = block.x
            if block.align == "center":
                draw_x = block.x + max(0, (block.width - line_width) // 2)
            if style.shadow.enabled:
                self._draw_text(
                    draw,
<<<<<<< HEAD
                    (draw_x + style.shadow.offset_x, y + style.shadow.offset_y),
=======
                    (draw_x + style.shadow.offset_x, current_y + style.shadow.offset_y),
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
                    line,
                    font,
                    token.letter_spacing,
                    style.shadow.fill,
                    stroke_width=0,
                    stroke_fill=None,
                )
            self._draw_text(
                draw,
<<<<<<< HEAD
                (draw_x, y),
=======
                (draw_x, current_y),
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
                line,
                font,
                token.letter_spacing,
                style.text_color,
                stroke_width=style.stroke.width if style.stroke.enabled else 0,
                stroke_fill=style.stroke.fill if style.stroke.enabled else None,
            )
<<<<<<< HEAD
            y += line_height + spacing
=======
            current_y += line_height + spacing

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        density_ratio = max(text_width / max(block.width, 1), total_height / max(block.height, 1))
        return {
            "x": int(plate_x0),
            "y": int(plate_y0),
            "width": int(text_width),
            "height": int(total_height),
            "density_ratio": float(density_ratio),
            "overflow_detected": bool(text_width > block.width or total_height > block.height),
        }

    def _draw_text(
        self,
        draw: ImageDraw.ImageDraw,
        xy: tuple[int, int],
        text: str,
        font,
        letter_spacing: int,
        fill: tuple[int, int, int, int],
        *,
        stroke_width: int,
        stroke_fill: tuple[int, int, int, int] | None,
    ) -> None:
<<<<<<< HEAD
        if letter_spacing <= 0:
            draw.text(xy, text, fill=fill, font=font, stroke_width=stroke_width, stroke_fill=stroke_fill)
            return
        x, y = xy
        for char in text:
            draw.text((x, y), char, fill=fill, font=font, stroke_width=stroke_width, stroke_fill=stroke_fill)
            char_bbox = draw.textbbox((0, 0), char, font=font, stroke_width=stroke_width)
            x += (char_bbox[2] - char_bbox[0]) + letter_spacing

    def _line_height(self, draw: ImageDraw.ImageDraw, font) -> int:
=======
        """按字距设置绘制文本。"""
        if letter_spacing <= 0:
            draw.text(xy, text, fill=fill, font=font, stroke_width=stroke_width, stroke_fill=stroke_fill)
            return

        current_x, current_y = xy
        for char in text:
            draw.text((current_x, current_y), char, fill=fill, font=font, stroke_width=stroke_width, stroke_fill=stroke_fill)
            char_bbox = draw.textbbox((0, 0), char, font=font, stroke_width=stroke_width)
            current_x += (char_bbox[2] - char_bbox[0]) + letter_spacing

    def _line_height(self, draw: ImageDraw.ImageDraw, font) -> int:
        """估算当前字体的实际行高。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        bbox = draw.textbbox((0, 0), "Ag", font=font)
        return bbox[3] - bbox[1]

    def _measure_text_width(self, draw: ImageDraw.ImageDraw, text: str, font, letter_spacing: int) -> int:
<<<<<<< HEAD
=======
        """测量单行文本宽度。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        if not text:
            return 0
        if letter_spacing <= 0:
            bbox = draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0]
<<<<<<< HEAD
=======

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        width = 0
        for index, char in enumerate(text):
            bbox = draw.textbbox((0, 0), char, font=font)
            width += bbox[2] - bbox[0]
            if index < len(text) - 1:
                width += letter_spacing
        return width

<<<<<<< HEAD
    def _requested_font_size(self, block: LayoutBlock, token: TypographyToken, layout_item: LayoutItem) -> int:
=======
    def _measure_text_block(
        self,
        draw: ImageDraw.ImageDraw,
        lines: list[str],
        font,
        token: TypographyToken,
    ) -> tuple[int, int, int, int]:
        """统一计算文本块宽高，避免 fit 阶段和 draw 阶段口径不一致。"""
        font_size = int(getattr(font, "size", token.font_size))
        line_height = max(self._line_height(draw, font), int(font_size * token.line_height))
        spacing = max(4, int(font_size * 0.08))
        line_widths = [self._measure_text_width(draw, line, font, token.letter_spacing) for line in lines]
        text_width = max(line_widths) if line_widths else 0
        total_height = len(lines) * line_height + max(0, len(lines) - 1) * spacing
        return text_width, total_height, line_height, spacing

    def _requested_font_size(self, block: LayoutBlock, token: TypographyToken, layout_item: LayoutItem) -> int:
        """根据画布宽度和 block 配置计算当前块的期望字号。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        scale = max(0.65, min(1.35, layout_item.canvas_width / 1440))
        token_size = int(token.font_size * scale)
        if block.font_size:
            return max(int(block.font_size * 0.9), token_size)
        return token_size

    def _get_typography_token(self, kind: str) -> TypographyToken:
<<<<<<< HEAD
        preset = PRESET_TOKENS.get(self.preset_name) or PRESET_TOKENS["premium_minimal"]
        return preset[kind]

=======
        """读取当前 preset 下对应 block 的 typography token。"""
        preset = PRESET_TOKENS.get(self.preset_name) or PRESET_TOKENS["premium_minimal"]
        return preset[kind]

    def _load_font(self, font_size: int) -> LoadedFont:
        """通过结构化字体候选加载器获取当前字号对应的字体。"""
        return load_font(
            self.font_path,
            font_size,
            project_font_candidates=self.project_font_candidates,
            system_font_candidates=self.system_font_candidates,
        )

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    def _resolve_text_style(
        self,
        image: Image.Image,
        block: LayoutBlock,
        token: TypographyToken,
        layout_item: LayoutItem,
    ) -> ResolvedTextStyle:
<<<<<<< HEAD
=======
        """根据 block 对应背景区域计算自适应文字样式。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        if not self.adaptive_style_enabled:
            default_rgba = (*token.text_color_default, 255)
            return ResolvedTextStyle(
                text_color=default_rgba,
                accent_color=(180, 164, 138, 255),
                shadow=ShadowConfig(enabled=False, offset_x=0, offset_y=0, fill=(0, 0, 0, 0)),
                stroke=StrokeConfig(enabled=False, width=0, fill=(0, 0, 0, 0)),
                plate=PlateConfig(enabled=False, padding_x=0, padding_y=0, radius=0, fill=(0, 0, 0, 0)),
                prefer_light_text=False,
<<<<<<< HEAD
                mean_luminance=0,
                luminance_stddev=0,
                contrast_with_choice=0,
            )
=======
                mean_luminance=0.0,
                luminance_stddev=0.0,
                contrast_with_choice=0.0,
            )

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        crop = self._crop_block_region(image, block, layout_item)
        style = self._resolve_adaptive_style_from_region(crop, token)
        logger.info(
            "Resolved text style: kind=%s, preset=%s, mean_luminance=%.2f, luminance_stddev=%.2f, prefer_light=%s, plate=%s, stroke=%s, shadow=%s",
            token.kind,
            self.preset_name,
            style.mean_luminance,
            style.luminance_stddev,
            style.prefer_light_text,
            style.plate.enabled,
            style.stroke.enabled,
            style.shadow.enabled,
        )
        return style

    def _crop_block_region(self, image: Image.Image, block: LayoutBlock, layout_item: LayoutItem) -> Image.Image:
<<<<<<< HEAD
=======
        """从背景图中裁出 block 周边区域，供自适应样式分析。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        pad_x = max(12, block.width // 10)
        pad_y = max(12, block.height // 10)
        x0 = max(0, block.x - pad_x)
        y0 = max(0, block.y - pad_y)
        x1 = min(layout_item.canvas_width, block.x + block.width + pad_x)
        y1 = min(layout_item.canvas_height, block.y + block.height + pad_y)
        return image.crop((x0, y0, x1, y1))

    def _resolve_adaptive_style_from_region(self, region: Image.Image, token: TypographyToken) -> ResolvedTextStyle:
<<<<<<< HEAD
=======
        """根据局部背景亮度和复杂度选择颜色、描边、底板和阴影。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        region_rgb = region.convert("RGB")
        luminance_image = region_rgb.convert("L")
        stat = ImageStat.Stat(luminance_image)
        mean_luminance = float(stat.mean[0]) if stat.mean else 0.0
        luminance_stddev = float(stat.stddev[0]) if stat.stddev else 0.0
<<<<<<< HEAD
=======

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        light_color = (246, 243, 238)
        dark_color = (34, 42, 48)
        light_contrast = self._contrast_ratio(light_color, (mean_luminance,) * 3)
        dark_contrast = self._contrast_ratio(dark_color, (mean_luminance,) * 3)
        prefer_light = light_contrast >= dark_contrast
        base_color = light_color if prefer_light else dark_color
        accent_color = self._extract_muted_accent_color(region_rgb, prefer_light=prefer_light)
        contrast_with_choice = max(light_contrast, dark_contrast)
<<<<<<< HEAD
        plate_enabled = self._should_enable_plate(token, mean_luminance, luminance_stddev, contrast_with_choice)
        stroke_enabled = self._should_enable_stroke(token, luminance_stddev, contrast_with_choice)
        shadow_enabled = self._should_enable_shadow(token, prefer_light, luminance_stddev, plate_enabled)
=======

        plate_enabled = self._should_enable_plate(token, mean_luminance, luminance_stddev, contrast_with_choice)
        stroke_enabled = self._should_enable_stroke(token, luminance_stddev, contrast_with_choice)
        shadow_enabled = self._should_enable_shadow(token, prefer_light, luminance_stddev, plate_enabled)

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        stroke_fill = (18, 22, 26, 210) if prefer_light else (255, 255, 255, 180)
        plate_fill = (20, 24, 28, 126) if prefer_light else (248, 245, 239, 112)
        if token.kind == "cta" and plate_enabled:
            plate_fill = (*accent_color[:3], 140 if prefer_light else 126)
<<<<<<< HEAD
=======

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        return ResolvedTextStyle(
            text_color=(*base_color, 255),
            accent_color=accent_color,
            shadow=ShadowConfig(
                enabled=shadow_enabled,
                offset_x=0,
                offset_y=2 if token.kind == "title" else 1,
                fill=(0, 0, 0, 120 if prefer_light else 70),
            ),
            stroke=StrokeConfig(
                enabled=stroke_enabled,
                width=1 if token.kind in {"subtitle", "bullets"} else 2,
                fill=stroke_fill,
            ),
            plate=PlateConfig(
                enabled=plate_enabled,
                padding_x=18 if token.kind == "title" else 14,
                padding_y=12 if token.kind == "title" else 10,
                radius=18 if token.kind == "title" else 14,
                fill=plate_fill,
            ),
            prefer_light_text=prefer_light,
            mean_luminance=mean_luminance,
            luminance_stddev=luminance_stddev,
            contrast_with_choice=contrast_with_choice,
        )

    def _should_enable_plate(
        self,
        token: TypographyToken,
        mean_luminance: float,
        luminance_stddev: float,
        contrast_with_choice: float,
    ) -> bool:
<<<<<<< HEAD
=======
        """根据 token 策略和背景复杂度决定是否启用底板。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        strategy = token.background_plate_strategy
        if strategy == "prefer_plate":
            return True
        if strategy == "auto_supportive":
            return contrast_with_choice < 5.2 or luminance_stddev > 40
        if strategy == "auto_minimal":
            return contrast_with_choice < 4.5 or (90 <= mean_luminance <= 170 and luminance_stddev > 48)
        if strategy == "auto_rare":
            return contrast_with_choice < 4.0 and luminance_stddev > 52
        return False

    def _should_enable_stroke(self, token: TypographyToken, luminance_stddev: float, contrast_with_choice: float) -> bool:
<<<<<<< HEAD
=======
        """根据对比度和背景波动决定是否启用描边。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        if token.stroke_strategy == "auto_none":
            return False
        return contrast_with_choice < 5.0 or luminance_stddev > 46

    def _should_enable_shadow(
        self,
        token: TypographyToken,
        prefer_light: bool,
        luminance_stddev: float,
        plate_enabled: bool,
    ) -> bool:
<<<<<<< HEAD
=======
        """根据文字颜色和背景复杂度决定是否启用柔和阴影。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        if plate_enabled:
            return False
        if token.shadow_strategy != "auto_soft":
            return False
        return prefer_light or luminance_stddev > 28 or token.kind == "title"

    def _extract_muted_accent_color(self, image: Image.Image, *, prefer_light: bool) -> tuple[int, int, int, int]:
<<<<<<< HEAD
=======
        """从局部区域中提取一个偏中性的辅助色，用于 CTA 底板。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        thumb = image.resize((1, 1))
        base = thumb.getpixel((0, 0))
        if not isinstance(base, tuple):
            base = (base, base, base)
        neutral = (116, 112, 108) if prefer_light else (156, 148, 138)
        mixed = tuple(int(base[index] * 0.28 + neutral[index] * 0.72) for index in range(3))
        return (*mixed, 255)

    def _contrast_ratio(self, text_rgb: tuple[int, int, int], bg_rgb: tuple[float, float, float]) -> float:
<<<<<<< HEAD
=======
        """计算文字颜色与背景亮度的对比度。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        text_l = self._relative_luminance(text_rgb)
        bg_l = self._relative_luminance(tuple(int(value) for value in bg_rgb))
        lighter = max(text_l, bg_l)
        darker = min(text_l, bg_l)
        return (lighter + 0.05) / (darker + 0.05)

    def _relative_luminance(self, rgb: tuple[int, int, int]) -> float:
<<<<<<< HEAD
=======
        """计算 RGB 颜色的相对亮度。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        channels = []
        for value in rgb:
            normalized = value / 255.0
            if normalized <= 0.03928:
                channels.append(normalized / 12.92)
            else:
                channels.append(((normalized + 0.055) / 1.055) ** 2.4)
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def main() -> None:
<<<<<<< HEAD
    target = Path("outputs/previews/text_render_test.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    TextRenderer().render_test_image(str(target))
    print(target)
=======
    """本地生成文字渲染测试图。"""
    target = Path("outputs/previews/text_render_test.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    report = TextRenderer().render_test_image(str(target))
    print(target)
    if report.test_metadata_path:
        print(report.test_metadata_path)
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c


if __name__ == "__main__":
    main()
