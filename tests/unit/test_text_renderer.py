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


def test_dark_background_prefers_light_text() -> None:
    renderer = TextRenderer()
    token = renderer._get_typography_token("title")
    region = Image.new("RGB", (200, 120), color=(18, 20, 24))

    style = renderer._resolve_adaptive_style_from_region(region, token)

    assert style.prefer_light_text is True
    assert style.text_color[0] > 200


def test_light_background_prefers_dark_text() -> None:
    renderer = TextRenderer()
    token = renderer._get_typography_token("title")
    region = Image.new("RGB", (200, 120), color=(245, 244, 240))

    style = renderer._resolve_adaptive_style_from_region(region, token)

    assert style.prefer_light_text is False
    assert style.text_color[0] < 80


def test_title_requested_font_size_is_larger_than_subtitle() -> None:
    renderer = TextRenderer()
    layout = LayoutItem(
        shot_id="shot-01",
        canvas_width=1440,
        canvas_height=1440,
        blocks=[],
    )
    title_block = LayoutBlock(kind="title", x=0, y=0, width=400, height=120, font_size=64)
    subtitle_block = LayoutBlock(kind="subtitle", x=0, y=140, width=400, height=100, font_size=64)

    title_size = renderer._requested_font_size(title_block, renderer._get_typography_token("title"), layout)
    subtitle_size = renderer._requested_font_size(subtitle_block, renderer._get_typography_token("subtitle"), layout)

    assert title_size > subtitle_size


def test_background_plate_can_be_triggered_on_busy_mid_tone_region() -> None:
    renderer = TextRenderer(preset_name="commercial_balanced")
    token = renderer._get_typography_token("title")
    region = Image.effect_noise((240, 160), 100).convert("RGB")

    style = renderer._resolve_adaptive_style_from_region(region, token)

    assert style.plate.enabled is True
