from __future__ import annotations

import math
from dataclasses import dataclass

from src.domain.layout_plan import LayoutBlock, LayoutItem, LayoutPlan, SafeZoneScore, TextSafeZone
from src.domain.product_analysis import ProductAnalysis
from src.domain.shot_plan import ShotPlan, ShotSpec


SAFE_ZONES: tuple[TextSafeZone, ...] = (
    "top_left",
    "top_right",
    "right_center",
    "left_center",
    "bottom_left",
    "bottom_right",
)


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2


def build_mock_layout_plan(
    shot_plan: ShotPlan,
    output_size: str,
    *,
    product_analysis: ProductAnalysis | None = None,
) -> LayoutPlan:
    width, height = [int(value) for value in output_size.split("x", maxsplit=1)]
    items: list[LayoutItem] = []
    for shot in shot_plan.shots:
        selection = _select_text_safe_zone(
            shot=shot,
            canvas_width=width,
            canvas_height=height,
            label_position=(product_analysis.visual_identity.label_position if product_analysis else ""),
        )
        items.append(
            LayoutItem(
                shot_id=shot.shot_id,
                canvas_width=width,
                canvas_height=height,
                text_safe_zone=selection["zone"],
                safe_zone_score_breakdown=selection["score_breakdown"],
                rejected_zones=selection["rejected_zones"],
                selection_reason=selection["selection_reason"],
                blocks=_build_blocks_for_zone(
                    zone=selection["zone"],
                    canvas_width=width,
                    canvas_height=height,
                ),
            )
        )
    return LayoutPlan(items=items)


def _select_text_safe_zone(
    *,
    shot: ShotSpec,
    canvas_width: int,
    canvas_height: int,
    label_position: str,
) -> dict[str, object]:
    subject_rect = _estimate_subject_rect(shot, canvas_width=canvas_width, canvas_height=canvas_height)
    label_rect = _estimate_label_rect(subject_rect, label_position)
    scores: list[SafeZoneScore] = []
    for zone in SAFE_ZONES:
        zone_rect = _zone_rect(zone, canvas_width=canvas_width, canvas_height=canvas_height)
        distance_score = _distance_from_subject_score(zone_rect, subject_rect, canvas_width, canvas_height)
        uniformity_score = _background_uniformity_score(zone, shot)
        readability_score = _text_readability_score(zone, shot)
        composition_bias = _composition_bias_score(zone, shot)
        label_penalty = _label_overlap_penalty(zone_rect, label_rect)
        total = max(
            0.0,
            round(
                (distance_score * 0.42)
                + (uniformity_score * 0.2)
                + (readability_score * 0.18)
                + (composition_bias * 0.2)
                - (label_penalty * 0.3),
                4,
            ),
        )
        rejection_reason = ""
        if label_penalty >= 0.18:
            rejection_reason = "label_overlap_risk"
        elif distance_score <= 0.35:
            rejection_reason = "too_close_to_subject"
        elif composition_bias < 0:
            rejection_reason = "weak_composition_fit"
        scores.append(
            SafeZoneScore(
                zone=zone,
                total_score=total,
                distance_from_subject_score=round(distance_score, 4),
                background_uniformity_score=round(uniformity_score, 4),
                text_readability_score=round(readability_score, 4),
                label_overlap_penalty=round(label_penalty, 4),
                composition_bias_score=round(composition_bias, 4),
                rejection_reason=rejection_reason,
            )
        )

    ordered_scores = sorted(scores, key=lambda item: item.total_score, reverse=True)
    selected = ordered_scores[0]
    rejected = [
        f"{item.zone}:{item.rejection_reason or 'score_ranked_lower'}:{item.total_score:.2f}"
        for item in ordered_scores[1:]
    ]
    return {
        "zone": selected.zone,
        "score_breakdown": ordered_scores,
        "rejected_zones": rejected,
        "selection_reason": _build_selection_reason(selected),
    }


def _build_blocks_for_zone(*, zone: TextSafeZone, canvas_width: int, canvas_height: int) -> list[LayoutBlock]:
    zone_rect = _zone_rect(zone, canvas_width=canvas_width, canvas_height=canvas_height)
    scale = min(canvas_width / 1440, canvas_height / 1440)
    padding_x = int(zone_rect.width * 0.06)
    title_y = int(zone_rect.y)
    title_height = int(zone_rect.height * 0.17)
    subtitle_y = title_y + title_height + int(zone_rect.height * 0.03)
    subtitle_height = int(zone_rect.height * 0.12)
    bullets_y = subtitle_y + subtitle_height + int(zone_rect.height * 0.035)
    bullets_height = int(zone_rect.height * 0.24)
    cta_y = bullets_y + bullets_height + int(zone_rect.height * 0.055)
    cta_height = int(zone_rect.height * 0.09)
    block_width = max(220, int(zone_rect.width) - (padding_x * 2))
    align = "left"
    title_x = int(zone_rect.x) + padding_x

    return [
        LayoutBlock(
            kind="title",
            x=title_x,
            y=title_y,
            width=block_width,
            height=title_height,
            font_size=max(54, int(92 * scale)),
            align=align,
        ),
        LayoutBlock(
            kind="subtitle",
            x=title_x,
            y=subtitle_y,
            width=max(200, int(block_width * 0.92)),
            height=subtitle_height,
            font_size=max(28, int(48 * scale)),
            align=align,
        ),
        LayoutBlock(
            kind="bullets",
            x=title_x,
            y=bullets_y,
            width=max(200, int(block_width * 0.88)),
            height=bullets_height,
            font_size=max(24, int(40 * scale)),
            align=align,
        ),
        LayoutBlock(
            kind="cta",
            x=title_x,
            y=cta_y,
            width=max(180, int(block_width * 0.62)),
            height=cta_height,
            font_size=max(24, int(36 * scale)),
            align=align,
        ),
    ]


def _zone_rect(zone: TextSafeZone, *, canvas_width: int, canvas_height: int) -> Rect:
    margin_x = canvas_width * 0.07
    width = canvas_width * 0.36
    top_height = canvas_height * 0.7
    center_height = canvas_height * 0.6
    bottom_height = canvas_height * 0.54
    zones: dict[TextSafeZone, Rect] = {
        "top_left": Rect(margin_x, canvas_height * 0.08, width, top_height),
        "top_right": Rect(canvas_width - margin_x - width, canvas_height * 0.08, width, top_height),
        "left_center": Rect(margin_x, canvas_height * 0.2, width, center_height),
        "right_center": Rect(canvas_width - margin_x - width, canvas_height * 0.2, width, center_height),
        "bottom_left": Rect(margin_x, canvas_height * 0.34, width, bottom_height),
        "bottom_right": Rect(canvas_width - margin_x - width, canvas_height * 0.34, width, bottom_height),
    }
    return zones[zone]


def _estimate_subject_rect(shot: ShotSpec, *, canvas_width: int, canvas_height: int) -> Rect:
    composition = _normalize_text(" ".join([shot.title, shot.purpose, shot.composition_hint, shot.composition_direction, shot.focus]))
    shot_type = _normalize_text(shot.shot_type)
    center_x = canvas_width * 0.5
    center_y = canvas_height * 0.52
    if _contains_any(composition, ("主体居中", "居中", "centered", "center")):
        center_x = canvas_width * 0.5
    elif _contains_any(composition, ("主体靠左", "主体偏左", "主体在左", "product on left", "left aligned")):
        center_x = canvas_width * 0.34
    elif _contains_any(composition, ("主体靠右", "主体偏右", "主体在右", "product on right", "right aligned")):
        center_x = canvas_width * 0.66
    if _contains_any(composition, ("偏上", "靠上", "top", "upper")):
        center_y = canvas_height * 0.4
    elif _contains_any(composition, ("偏下", "靠下", "bottom", "lower", "底部")):
        center_y = canvas_height * 0.64

    width_ratio = 0.42
    height_ratio = 0.56
    if _contains_any(shot_type, ("detail", "closeup", "macro", "feature")) or _contains_any(composition, ("近景", "特写", "细节")):
        width_ratio = 0.5
        height_ratio = 0.62
    elif _contains_any(shot_type, ("hero", "packshot")):
        width_ratio = 0.4
        height_ratio = 0.54

    width = canvas_width * width_ratio
    height = canvas_height * height_ratio
    return Rect(center_x - width / 2, center_y - height / 2, width, height)


def _estimate_label_rect(subject_rect: Rect, label_position: str) -> Rect:
    normalized = _normalize_text(label_position)
    center_x = subject_rect.center_x
    center_y = subject_rect.center_y
    if _contains_any(normalized, ("left", "左")):
        center_x = subject_rect.x + (subject_rect.width * 0.3)
    elif _contains_any(normalized, ("right", "右")):
        center_x = subject_rect.x + (subject_rect.width * 0.7)
    if _contains_any(normalized, ("top", "上")):
        center_y = subject_rect.y + (subject_rect.height * 0.3)
    elif _contains_any(normalized, ("bottom", "下")):
        center_y = subject_rect.y + (subject_rect.height * 0.7)
    width = subject_rect.width * 0.4
    height = subject_rect.height * 0.34
    return Rect(center_x - width / 2, center_y - height / 2, width, height)


def _distance_from_subject_score(zone_rect: Rect, subject_rect: Rect, canvas_width: int, canvas_height: int) -> float:
    distance = math.dist((zone_rect.center_x, zone_rect.center_y), (subject_rect.center_x, subject_rect.center_y))
    max_distance = math.dist((0, 0), (canvas_width, canvas_height))
    return min(1.0, distance / (max_distance * 0.58))


def _background_uniformity_score(zone: TextSafeZone, shot: ShotSpec) -> float:
    base_scores = {
        "top_left": 0.84,
        "top_right": 0.84,
        "left_center": 0.76,
        "right_center": 0.76,
        "bottom_left": 0.68,
        "bottom_right": 0.68,
    }
    score = base_scores[zone]
    shot_type = _normalize_text(shot.shot_type)
    if _contains_any(shot_type, ("detail", "feature", "closeup")) and zone in {"left_center", "right_center"}:
        score += 0.06
    if _contains_any(_normalize_text(shot.composition_direction), ("留白", "blank", "negative space")):
        hinted_side = _hinted_side(shot)
        if hinted_side and _zone_side(zone) == hinted_side:
            score += 0.08
    return min(1.0, score)


def _text_readability_score(zone: TextSafeZone, shot: ShotSpec) -> float:
    score = {
        "top_left": 0.82,
        "top_right": 0.82,
        "left_center": 0.75,
        "right_center": 0.75,
        "bottom_left": 0.7,
        "bottom_right": 0.7,
    }[zone]
    shot_type = _normalize_text(shot.shot_type)
    if _contains_any(shot_type, ("hero", "packshot")) and zone in {"top_left", "top_right"}:
        score += 0.05
    return min(1.0, score)


def _composition_bias_score(zone: TextSafeZone, shot: ShotSpec) -> float:
    composition = _normalize_text(" ".join([shot.composition_hint, shot.composition_direction, shot.goal]))
    zone_side = "left" if "left" in zone else "right"
    hinted_side = _hinted_side(shot)
    if hinted_side is not None:
        if zone_side == hinted_side:
            return 0.26 if "center" not in zone else 0.22
        return -0.08
    if _contains_any(_normalize_text(shot.shot_type), ("hero", "packshot")) and zone in {"top_left", "top_right"}:
        return 0.1
    if _contains_any(composition, ("detail", "细节", "closeup")) and zone in {"left_center", "right_center"}:
        return 0.08
    return 0.03


def _hinted_side(shot: ShotSpec) -> str | None:
    composition = _normalize_text(" ".join([shot.composition_hint, shot.composition_direction]))
    if not _contains_any(composition, ("留白", "blank", "negative space", "text space", "文字区", "贴字", "copy area", "copy zone")):
        return None
    if _contains_any(composition, ("left", "左", "左侧")):
        return "left"
    if _contains_any(composition, ("right", "右", "右侧")):
        return "right"
    return None


def _label_overlap_penalty(zone_rect: Rect, label_rect: Rect) -> float:
    overlap_area = _intersection_area(zone_rect, label_rect)
    if overlap_area <= 0:
        return 0.0
    zone_area = max(zone_rect.width * zone_rect.height, 1.0)
    return min(1.0, overlap_area / zone_area)


def _intersection_area(a: Rect, b: Rect) -> float:
    left = max(a.x, b.x)
    top = max(a.y, b.y)
    right = min(a.x + a.width, b.x + b.width)
    bottom = min(a.y + a.height, b.y + b.height)
    if right <= left or bottom <= top:
        return 0.0
    return (right - left) * (bottom - top)


def _build_selection_reason(score: SafeZoneScore) -> str:
    drivers: list[str] = []
    if score.distance_from_subject_score >= 0.7:
        drivers.append("far_from_subject")
    if score.background_uniformity_score >= 0.82:
        drivers.append("clean_background")
    if score.text_readability_score >= 0.8:
        drivers.append("text_readable")
    if score.composition_bias_score > 0.15:
        drivers.append("matches_composition_hint")
    if not drivers:
        drivers.append("best_overall_balance")
    return ",".join(drivers[:3])


def _zone_side(zone: TextSafeZone) -> str:
    return "left" if "left" in zone else "right"


def _normalize_text(value: str) -> str:
    return " ".join(str(value).lower().split())


def _contains_any(value: str, needles: tuple[str, ...]) -> bool:
    return any(needle in value for needle in needles)
