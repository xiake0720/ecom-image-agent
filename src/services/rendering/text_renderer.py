from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageStat

from src.core.config import get_settings
from src.domain.copy_plan import CopyItem
from src.domain.layout_plan import LayoutBlock, LayoutItem
from src.services.rendering.font_utils import load_font

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShadowConfig:
    enabled: bool
    offset_x: int
    offset_y: int
    fill: tuple[int, int, int, int]


@dataclass(frozen=True)
class StrokeConfig:
    enabled: bool
    width: int
    fill: tuple[int, int, int, int]


@dataclass(frozen=True)
class PlateConfig:
    enabled: bool
    padding_x: int
    padding_y: int
    radius: int
    fill: tuple[int, int, int, int]


@dataclass(frozen=True)
class TypographyToken:
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
    text_color: tuple[int, int, int, int]
    accent_color: tuple[int, int, int, int]
    shadow: ShadowConfig
    stroke: StrokeConfig
    plate: PlateConfig
    prefer_light_text: bool
    mean_luminance: float
    luminance_stddev: float
    contrast_with_choice: float


@dataclass
class PlacedTextBlock:
    kind: str
    requested_font_size: int
    used_font_size: int
    line_count: int
    typography_preset: str
    text_color: tuple[int, int, int, int]
    background_plate_applied: bool
    shadow_applied: bool
    stroke_applied: bool


@dataclass
class TextRenderReport:
    output_path: str
    blocks: list[PlacedTextBlock]


PRESET_TOKENS: dict[str, dict[str, TypographyToken]] = {
    "premium_minimal": {
        "title": TypographyToken("title", 96, 1.12, 1, "semi_bold", (244, 241, 236), "auto_soft", "auto_subtle", "auto_minimal"),
        "subtitle": TypographyToken("subtitle", 46, 1.24, 0, "regular", (235, 232, 227), "auto_soft", "auto_none", "auto_rare"),
        "bullets": TypographyToken("bullets", 38, 1.32, 0, "regular", (232, 229, 224), "auto_soft", "auto_none", "auto_rare"),
        "cta": TypographyToken("cta", 32, 1.1, 1, "medium", (245, 244, 241), "auto_soft", "auto_subtle", "prefer_plate"),
    },
    "commercial_balanced": {
        "title": TypographyToken("title", 102, 1.14, 1, "semi_bold", (244, 241, 236), "auto_soft", "auto_subtle", "auto_supportive"),
        "subtitle": TypographyToken("subtitle", 50, 1.26, 0, "regular", (236, 232, 228), "auto_soft", "auto_subtle", "auto_supportive"),
        "bullets": TypographyToken("bullets", 40, 1.34, 0, "regular", (234, 230, 226), "auto_soft", "auto_none", "auto_supportive"),
        "cta": TypographyToken("cta", 34, 1.12, 1, "medium", (245, 244, 241), "auto_soft", "auto_subtle", "prefer_plate"),
    },
}


class TextRenderer:
    def __init__(self, font_path: Path | None = None, *, preset_name: str | None = None) -> None:
        settings = get_settings()
        self.font_path = font_path or settings.default_font_path
        self.preset_name = preset_name or settings.resolve_text_render_preset()
        self.adaptive_style_enabled = bool(settings.text_render_adaptive_style_enabled)

    def render_copy(
        self,
        *,
        input_image_path: str,
        copy_item: CopyItem,
        layout_item: LayoutItem,
        output_path: str,
    ) -> TextRenderReport:
        logger.info(
            "开始执行中文后贴字，shot_id=%s，输入=%s，输出=%s，布局块数量=%s，preset=%s",
            copy_item.shot_id,
            input_image_path,
            output_path,
            len(layout_item.blocks),
            self.preset_name,
        )
        with Image.open(input_image_path).convert("RGBA") as image:
            analysis_image = image.copy()
            draw = ImageDraw.Draw(image)
            reports: list[PlacedTextBlock] = []
            for block in layout_item.blocks:
                text = self._resolve_text(copy_item, block)
                if not text:
                    continue
                token = self._get_typography_token(block.kind)
                lines, font_size = self._fit_text(draw, text, block, token, layout_item)
                font = load_font(self.font_path, font_size)
                style = self._resolve_text_style(analysis_image, block, token, layout_item)
                self._draw_lines(draw, lines, block, font, token, style, layout_item)
                reports.append(
                    PlacedTextBlock(
                        kind=block.kind,
                        requested_font_size=self._requested_font_size(block, token, layout_item),
                        used_font_size=font_size,
                        line_count=len(lines),
                        typography_preset=self.preset_name,
                        text_color=style.text_color,
                        background_plate_applied=style.plate.enabled,
                        shadow_applied=style.shadow.enabled,
                        stroke_applied=style.stroke.enabled,
                    )
                )
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
        layout = LayoutItem(
            shot_id="sample",
            canvas_width=1440,
            canvas_height=1440,
            blocks=[
                LayoutBlock(kind="title", x=90, y=120, width=600, height=220, font_size=96),
                LayoutBlock(kind="subtitle", x=90, y=360, width=560, height=180, font_size=48),
                LayoutBlock(kind="bullets", x=90, y=570, width=520, height=260, font_size=40),
                LayoutBlock(kind="cta", x=90, y=860, width=320, height=90, font_size=32),
            ],
        )
        copy_item = CopyItem(
            shot_id="sample",
            title="高山云雾 原叶鲜香",
            subtitle="自动换行与缩字示例，适合作为测试渲染样图",
            bullets=["标题", "副标题", "卖点条目"],
            cta="立即了解",
        )
        return self.render_copy(
            input_image_path=str(temp_path),
            copy_item=copy_item,
            layout_item=layout,
            output_path=output_path,
        )

    def _resolve_text(self, copy_item: CopyItem, block: LayoutBlock) -> str:
        if block.kind == "title":
            return copy_item.title
        if block.kind == "subtitle":
            return copy_item.subtitle
        if block.kind == "bullets":
            return "\n".join(f"• {item}" for item in copy_item.bullets)
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
            lines.append(current)
        return [line for line in lines if line]

    def _draw_lines(
        self,
        draw: ImageDraw.ImageDraw,
        lines: Iterable[str],
        block: LayoutBlock,
        font,
        token: TypographyToken,
        style: ResolvedTextStyle,
        layout_item: LayoutItem,
    ) -> None:
        lines = list(lines)
        if not lines:
            return
        line_height = max(self._line_height(draw, font), int(font.size * token.line_height)) if hasattr(font, "size") else self._line_height(draw, font)
        spacing = max(4, int((font.size if hasattr(font, "size") else 24) * 0.08))
        line_widths = [self._measure_text_width(draw, line, font, token.letter_spacing) for line in lines]
        text_width = max(line_widths) if line_widths else 0
        total_height = len(lines) * line_height + max(0, len(lines) - 1) * spacing
        plate_x0 = block.x
        plate_x1 = block.x + text_width
        if block.align == "center":
            plate_x0 = block.x + max(0, (block.width - text_width) // 2)
            plate_x1 = plate_x0 + text_width
        plate_y0 = block.y
        plate_y1 = block.y + total_height
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
        y = block.y
        for line, line_width in zip(lines, line_widths):
            draw_x = block.x
            if block.align == "center":
                draw_x = block.x + max(0, (block.width - line_width) // 2)
            if style.shadow.enabled:
                self._draw_text(
                    draw,
                    (draw_x + style.shadow.offset_x, y + style.shadow.offset_y),
                    line,
                    font,
                    token.letter_spacing,
                    style.shadow.fill,
                    stroke_width=0,
                    stroke_fill=None,
                )
            self._draw_text(
                draw,
                (draw_x, y),
                line,
                font,
                token.letter_spacing,
                style.text_color,
                stroke_width=style.stroke.width if style.stroke.enabled else 0,
                stroke_fill=style.stroke.fill if style.stroke.enabled else None,
            )
            y += line_height + spacing

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
        if letter_spacing <= 0:
            draw.text(xy, text, fill=fill, font=font, stroke_width=stroke_width, stroke_fill=stroke_fill)
            return
        x, y = xy
        for char in text:
            draw.text((x, y), char, fill=fill, font=font, stroke_width=stroke_width, stroke_fill=stroke_fill)
            char_bbox = draw.textbbox((0, 0), char, font=font, stroke_width=stroke_width)
            x += (char_bbox[2] - char_bbox[0]) + letter_spacing

    def _line_height(self, draw: ImageDraw.ImageDraw, font) -> int:
        bbox = draw.textbbox((0, 0), "Ag", font=font)
        return bbox[3] - bbox[1]

    def _measure_text_width(self, draw: ImageDraw.ImageDraw, text: str, font, letter_spacing: int) -> int:
        if not text:
            return 0
        if letter_spacing <= 0:
            bbox = draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0]
        width = 0
        for index, char in enumerate(text):
            bbox = draw.textbbox((0, 0), char, font=font)
            width += bbox[2] - bbox[0]
            if index < len(text) - 1:
                width += letter_spacing
        return width

    def _requested_font_size(self, block: LayoutBlock, token: TypographyToken, layout_item: LayoutItem) -> int:
        scale = max(0.65, min(1.35, layout_item.canvas_width / 1440))
        token_size = int(token.font_size * scale)
        if block.font_size:
            return max(int(block.font_size * 0.9), token_size)
        return token_size

    def _get_typography_token(self, kind: str) -> TypographyToken:
        preset = PRESET_TOKENS.get(self.preset_name) or PRESET_TOKENS["premium_minimal"]
        return preset[kind]

    def _resolve_text_style(
        self,
        image: Image.Image,
        block: LayoutBlock,
        token: TypographyToken,
        layout_item: LayoutItem,
    ) -> ResolvedTextStyle:
        if not self.adaptive_style_enabled:
            default_rgba = (*token.text_color_default, 255)
            return ResolvedTextStyle(
                text_color=default_rgba,
                accent_color=(180, 164, 138, 255),
                shadow=ShadowConfig(enabled=False, offset_x=0, offset_y=0, fill=(0, 0, 0, 0)),
                stroke=StrokeConfig(enabled=False, width=0, fill=(0, 0, 0, 0)),
                plate=PlateConfig(enabled=False, padding_x=0, padding_y=0, radius=0, fill=(0, 0, 0, 0)),
                prefer_light_text=False,
                mean_luminance=0,
                luminance_stddev=0,
                contrast_with_choice=0,
            )
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
        pad_x = max(12, block.width // 10)
        pad_y = max(12, block.height // 10)
        x0 = max(0, block.x - pad_x)
        y0 = max(0, block.y - pad_y)
        x1 = min(layout_item.canvas_width, block.x + block.width + pad_x)
        y1 = min(layout_item.canvas_height, block.y + block.height + pad_y)
        return image.crop((x0, y0, x1, y1))

    def _resolve_adaptive_style_from_region(self, region: Image.Image, token: TypographyToken) -> ResolvedTextStyle:
        region_rgb = region.convert("RGB")
        luminance_image = region_rgb.convert("L")
        stat = ImageStat.Stat(luminance_image)
        mean_luminance = float(stat.mean[0]) if stat.mean else 0.0
        luminance_stddev = float(stat.stddev[0]) if stat.stddev else 0.0
        light_color = (246, 243, 238)
        dark_color = (34, 42, 48)
        light_contrast = self._contrast_ratio(light_color, (mean_luminance,) * 3)
        dark_contrast = self._contrast_ratio(dark_color, (mean_luminance,) * 3)
        prefer_light = light_contrast >= dark_contrast
        base_color = light_color if prefer_light else dark_color
        accent_color = self._extract_muted_accent_color(region_rgb, prefer_light=prefer_light)
        contrast_with_choice = max(light_contrast, dark_contrast)
        plate_enabled = self._should_enable_plate(token, mean_luminance, luminance_stddev, contrast_with_choice)
        stroke_enabled = self._should_enable_stroke(token, luminance_stddev, contrast_with_choice)
        shadow_enabled = self._should_enable_shadow(token, prefer_light, luminance_stddev, plate_enabled)
        stroke_fill = (18, 22, 26, 210) if prefer_light else (255, 255, 255, 180)
        plate_fill = (20, 24, 28, 126) if prefer_light else (248, 245, 239, 112)
        if token.kind == "cta" and plate_enabled:
            plate_fill = (*accent_color[:3], 140 if prefer_light else 126)
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
        if plate_enabled:
            return False
        if token.shadow_strategy != "auto_soft":
            return False
        return prefer_light or luminance_stddev > 28 or token.kind == "title"

    def _extract_muted_accent_color(self, image: Image.Image, *, prefer_light: bool) -> tuple[int, int, int, int]:
        thumb = image.resize((1, 1))
        base = thumb.getpixel((0, 0))
        if not isinstance(base, tuple):
            base = (base, base, base)
        neutral = (116, 112, 108) if prefer_light else (156, 148, 138)
        mixed = tuple(int(base[index] * 0.28 + neutral[index] * 0.72) for index in range(3))
        return (*mixed, 255)

    def _contrast_ratio(self, text_rgb: tuple[int, int, int], bg_rgb: tuple[float, float, float]) -> float:
        text_l = self._relative_luminance(text_rgb)
        bg_l = self._relative_luminance(tuple(int(value) for value in bg_rgb))
        lighter = max(text_l, bg_l)
        darker = min(text_l, bg_l)
        return (lighter + 0.05) / (darker + 0.05)

    def _relative_luminance(self, rgb: tuple[int, int, int]) -> float:
        channels = []
        for value in rgb:
            normalized = value / 255.0
            if normalized <= 0.03928:
                channels.append(normalized / 12.92)
            else:
                channels.append(((normalized + 0.055) / 1.055) ** 2.4)
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def main() -> None:
    target = Path("outputs/previews/text_render_test.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    TextRenderer().render_test_image(str(target))
    print(target)


if __name__ == "__main__":
    main()
