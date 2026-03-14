from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont


@lru_cache(maxsize=32)
def load_font(font_path: Path, font_size: int) -> ImageFont.ImageFont:
    if font_path.exists():
        return ImageFont.truetype(str(font_path), font_size)
    try:
        return ImageFont.truetype("DejaVuSans.ttf", font_size)
    except OSError:
        pass
    return ImageFont.load_default()
