from __future__ import annotations

from pathlib import Path

from PIL import Image


def save_preview(image_path: str, preview_path: Path, max_side: int = 480) -> None:
    with Image.open(image_path) as image:
        image.thumbnail((max_side, max_side))
        image.save(preview_path)

