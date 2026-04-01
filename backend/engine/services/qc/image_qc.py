from __future__ import annotations

from PIL import Image

from backend.engine.domain.generation_result import GeneratedImage
from backend.engine.domain.qc_report import QCCheck


def build_dimension_check(image: GeneratedImage) -> QCCheck:
    with Image.open(image.image_path) as payload:
        width, height = payload.size
    passed = width == image.width and height == image.height
    return QCCheck(
        shot_id=image.shot_id,
        check_name="dimension",
        passed=passed,
        details=f"expected={image.width}x{image.height}, actual={width}x{height}",
    )

