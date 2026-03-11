from __future__ import annotations

from pathlib import Path

from PIL import ImageFont


def load_font(font_path: Path, font_size: int) -> ImageFont.ImageFont:
    if font_path.exists():
        return ImageFont.truetype(str(font_path), font_size)
    return ImageFont.load_default()

