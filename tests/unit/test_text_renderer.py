from __future__ import annotations

from pathlib import Path

from PIL import Image

from src.domain.copy_plan import CopyItem
from src.domain.layout_plan import LayoutBlock, LayoutItem
from src.services.rendering.text_renderer import TextRenderer


def test_text_renderer_outputs_image_and_shrinks_text(tmp_path: Path) -> None:
    base_path = tmp_path / "base.png"
    Image.new("RGB", (800, 800), color=(255, 255, 255)).save(base_path)

    layout = LayoutItem(
        shot_id="shot-01",
        canvas_width=800,
        canvas_height=800,
        blocks=[
            LayoutBlock(kind="title", x=40, y=40, width=220, height=80, font_size=72),
            LayoutBlock(kind="subtitle", x=40, y=150, width=280, height=120, font_size=36),
        ],
    )
    copy_item = CopyItem(
        shot_id="shot-01",
        title="This title is intentionally long enough to trigger font shrinking",
        subtitle="Subtitle line for wrapping.",
    )
    output_path = tmp_path / "rendered.png"
    report = TextRenderer().render_copy(
        input_image_path=str(base_path),
        copy_item=copy_item,
        layout_item=layout,
        output_path=str(output_path),
    )

    assert output_path.exists()
    assert report.blocks[0].used_font_size <= report.blocks[0].requested_font_size

