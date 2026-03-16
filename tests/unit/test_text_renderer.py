from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
import pytest

from src.core.config import get_settings
from src.domain.copy_plan import CopyItem
from src.domain.layout_plan import LayoutBlock, LayoutItem
from src.services.rendering.text_renderer import TextRenderer


def test_text_renderer_outputs_image_and_records_font_metadata(tmp_path: Path) -> None:
    renderer = TextRenderer(font_path=_find_available_cjk_font())
    base_path = tmp_path / "base.png"
    Image.new("RGB", (800, 800), color=(255, 255, 255)).save(base_path)

    layout = LayoutItem(
        shot_id="shot-01",
        canvas_width=800,
        canvas_height=800,
        blocks=[
            LayoutBlock(kind="title", x=40, y=40, width=280, height=90, font_size=72),
            LayoutBlock(kind="subtitle", x=40, y=150, width=320, height=120, font_size=36),
        ],
    )
    copy_item = CopyItem(
        shot_id="shot-01",
        title="高山云雾鲜爽回甘",
        subtitle="中文副标题换行测试。",
    )
    output_path = tmp_path / "rendered.png"
    report = renderer.render_copy(
        input_image_path=str(base_path),
        copy_item=copy_item,
        layout_item=layout,
        output_path=str(output_path),
    )

    assert output_path.exists()
    assert report.font_loaded is True
    assert report.font_source
    assert report.resolved_font_path
    assert report.blocks[0].used_font_size <= report.blocks[0].requested_font_size


def test_missing_configured_font_uses_structured_fallback_metadata(tmp_path: Path) -> None:
    fallback_font = _find_available_cjk_font()
    renderer = TextRenderer(font_path=tmp_path / "missing-font.otf")
    renderer.project_font_candidates = (renderer.font_path,)
    renderer.system_font_candidates = (fallback_font,)

    base_path = tmp_path / "base.png"
    Image.new("RGB", (800, 800), color=(240, 240, 240)).save(base_path)
    layout = LayoutItem(
        shot_id="shot-01",
        canvas_width=800,
        canvas_height=800,
        blocks=[LayoutBlock(kind="title", x=40, y=40, width=320, height=120, font_size=72)],
    )
    copy_item = CopyItem(shot_id="shot-01", title="中文字体 fallback 可见", subtitle="")

    report = renderer.render_copy(
        input_image_path=str(base_path),
        copy_item=copy_item,
        layout_item=layout,
        output_path=str(tmp_path / "rendered.png"),
    )

    assert report.font_loaded is True
    assert report.fallback_used is True
    assert report.font_source in {"windows_system_font", "macos_system_font", "linux_system_font"}
    assert report.fallback_target == str(fallback_font)


def test_text_renderer_hits_min_font_size_and_flags_overflow(tmp_path: Path) -> None:
    renderer = TextRenderer(font_path=_find_available_cjk_font())
    base_path = tmp_path / "base.png"
    Image.new("RGB", (800, 800), color=(255, 255, 255)).save(base_path)

    layout = LayoutItem(
        shot_id="shot-01",
        canvas_width=800,
        canvas_height=800,
        blocks=[LayoutBlock(kind="title", x=40, y=40, width=160, height=90, font_size=72)],
    )
    copy_item = CopyItem(
        shot_id="shot-01",
        title="这是一个非常非常长而且必须触发最小字号限制的中文标题测试",
        subtitle="",
    )
    output_path = tmp_path / "rendered.png"
    report = renderer.render_copy(
        input_image_path=str(base_path),
        copy_item=copy_item,
        layout_item=layout,
        output_path=str(output_path),
    )

    title_block = report.blocks[0]
    assert title_block.used_font_size == get_settings().text_render_min_title_font_size
    assert title_block.min_font_size_hit is True
    assert title_block.overflow_detected is True


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


def test_render_test_image_writes_font_metadata_sidecar(tmp_path: Path) -> None:
    output_path = tmp_path / "text_render_test.png"

    report = TextRenderer(font_path=_find_available_cjk_font()).render_test_image(str(output_path))

    metadata_path = Path(report.test_metadata_path or "")
    assert output_path.exists()
    assert metadata_path.exists()
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["font_source"]
    assert payload["font_loaded"] is True
    assert "fallback_used" in payload


def _find_available_cjk_font() -> Path:
    settings = get_settings()
    for candidate in (
        *settings.resolve_project_font_candidates(),
        *settings.resolve_system_chinese_font_candidates(),
    ):
        if candidate.exists():
            return candidate
    pytest.skip("No CJK font candidate available in current environment.")
