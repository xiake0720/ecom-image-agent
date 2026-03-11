from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw

from src.core.config import get_settings
from src.domain.copy_plan import CopyItem
from src.domain.layout_plan import LayoutBlock, LayoutItem
from src.services.rendering.font_utils import load_font


@dataclass
class PlacedTextBlock:
    kind: str
    requested_font_size: int
    used_font_size: int
    line_count: int


@dataclass
class TextRenderReport:
    output_path: str
    blocks: list[PlacedTextBlock]


class TextRenderer:
    def __init__(self, font_path: Path | None = None) -> None:
        self.font_path = font_path or get_settings().default_font_path

    def render_copy(
        self,
        *,
        input_image_path: str,
        copy_item: CopyItem,
        layout_item: LayoutItem,
        output_path: str,
    ) -> TextRenderReport:
        with Image.open(input_image_path).convert("RGBA") as image:
            draw = ImageDraw.Draw(image)
            reports: list[PlacedTextBlock] = []
            for block in layout_item.blocks:
                text = self._resolve_text(copy_item, block)
                if not text:
                    continue
                lines, font_size = self._fit_text(draw, text, block)
                font = load_font(self.font_path, font_size)
                self._draw_lines(draw, lines, block, font)
                reports.append(
                    PlacedTextBlock(
                        kind=block.kind,
                        requested_font_size=block.font_size,
                        used_font_size=font_size,
                        line_count=len(lines),
                    )
                )
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            image.convert("RGB").save(target)
        return TextRenderReport(output_path=str(output_path), blocks=reports)

    def render_test_image(self, output_path: str) -> TextRenderReport:
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
            ],
        )
        copy_item = CopyItem(
            shot_id="sample",
            title="高山云雾 原叶鲜香",
            subtitle="自动换行与缩字示例，适合作为测试渲染样图",
            bullets=["标题", "副标题", "卖点条目"],
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

    def _fit_text(self, draw: ImageDraw.ImageDraw, text: str, block: LayoutBlock) -> tuple[list[str], int]:
        font_size = block.font_size
        min_size = 18
        while font_size >= min_size:
            font = load_font(self.font_path, font_size)
            lines = self._wrap_text(draw, text, font, block.width)
            line_height = self._line_height(draw, font)
            total_height = len(lines) * line_height + max(0, len(lines) - 1) * max(6, font_size // 4)
            if total_height <= block.height:
                return lines, font_size
            font_size -= 2
        font = load_font(self.font_path, min_size)
        return self._wrap_text(draw, text, font, block.width), min_size

    def _wrap_text(self, draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
        lines: list[str] = []
        for raw_line in text.splitlines() or [""]:
            current = ""
            for char in raw_line:
                candidate = f"{current}{char}"
                bbox = draw.textbbox((0, 0), candidate, font=font)
                if bbox[2] - bbox[0] <= max_width or not current:
                    current = candidate
                else:
                    lines.append(current)
                    current = char
            lines.append(current)
        return [line for line in lines if line]

    def _draw_lines(self, draw: ImageDraw.ImageDraw, lines: Iterable[str], block: LayoutBlock, font) -> None:
        y = block.y
        fill = (34, 54, 41)
        line_height = self._line_height(draw, font)
        spacing = max(6, font.size // 4) if hasattr(font, "size") else 8
        for line in lines:
            if block.align == "center":
                bbox = draw.textbbox((0, 0), line, font=font)
                draw_x = block.x + max(0, (block.width - (bbox[2] - bbox[0])) // 2)
            else:
                draw_x = block.x
            draw.text((draw_x, y), line, fill=fill, font=font)
            y += line_height + spacing

    def _line_height(self, draw: ImageDraw.ImageDraw, font) -> int:
        bbox = draw.textbbox((0, 0), "Ag", font=font)
        return bbox[3] - bbox[1]


def main() -> None:
    target = Path("outputs/previews/text_render_test.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    TextRenderer().render_test_image(str(target))
    print(target)


if __name__ == "__main__":
    main()

