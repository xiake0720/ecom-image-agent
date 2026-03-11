from __future__ import annotations

from src.domain.layout_plan import LayoutBlock, LayoutItem, LayoutPlan
from src.domain.shot_plan import ShotPlan


def build_mock_layout_plan(shot_plan: ShotPlan, output_size: str) -> LayoutPlan:
    width, height = [int(value) for value in output_size.split("x", maxsplit=1)]
    items = []
    for shot in shot_plan.shots:
        items.append(
            LayoutItem(
                shot_id=shot.shot_id,
                canvas_width=width,
                canvas_height=height,
                blocks=[
                    LayoutBlock(kind="title", x=96, y=100, width=620, height=220, font_size=92),
                    LayoutBlock(kind="subtitle", x=96, y=330, width=560, height=180, font_size=48),
                    LayoutBlock(kind="bullets", x=96, y=530, width=520, height=280, font_size=40),
                    LayoutBlock(kind="cta", x=96, y=840 if height == 1440 else 1180, width=400, height=100, font_size=38),
                ],
            )
        )
    return LayoutPlan(items=items)

