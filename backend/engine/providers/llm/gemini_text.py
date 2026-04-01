from __future__ import annotations

import logging
from typing import Any

from backend.engine.providers.llm.base import BaseTextProvider, StructuredModel

logger = logging.getLogger(__name__)


class GeminiTextProvider(BaseTextProvider):
    def __init__(self) -> None:
        pass

    def generate_structured(
        self,
        prompt: str,
        response_model: type[StructuredModel],
        *,
        system_prompt: str | None = None,
    ) -> StructuredModel:
        logger.info("当前文本 provider 模式为 mock，返回本地结构化占位数据，schema=%s", response_model.__name__)
        # TODO: Replace this mock-only implementation with a real Gemini API call after MVP approval.
        return self._mock_response(response_model)

    def _mock_response(self, response_model: type[StructuredModel]) -> StructuredModel:
        payload = self._mock_payload(response_model)
        return response_model.model_validate(payload)

    def _mock_payload(self, response_model: type[StructuredModel]) -> dict[str, Any]:
        name = response_model.__name__
        if name == "ProductAnalysis":
            return {
                "analysis_scope": "sku_level",
                "intended_for": "all_future_shots",
                "category": "tea",
                "subcategory": "绿茶",
                "product_type": "绿茶",
                "product_form": "packaged_tea",
                "packaging_structure": {
                    "primary_container": "unknown",
                    "has_outer_box": "unknown",
                    "has_visible_lid": "unknown",
                    "container_count": "1",
                },
                "visual_identity": {
                    "dominant_colors": ["绿色", "白色"],
                    "label_position": "front_center",
                    "label_ratio": "medium",
                    "style_impression": ["清透", "自然", "电商清爽"],
                    "must_preserve": ["包装主体轮廓", "正面标签区"],
                },
                "material_guess": {
                    "container_material": "unknown",
                    "label_material": "unknown",
                },
                "visual_constraints": {
                    "recommended_style_direction": ["突出包装主体", "延续原始配色"],
                    "avoid": ["不要虚构包装结构", "不要输出行业通用卖点"],
                },
                "selling_points": [],
                "visual_style_keywords": ["清透", "自然", "包装主体"],
                "recommended_focuses": ["包装主体", "标签区", "材质表现"],
                "source_asset_ids": [],
            }
        if name == "ShotPlan":
            return {
                "shots": [
                    {
                        "shot_id": "shot-01",
                        "title": "主视觉主图",
                        "purpose": "展示品牌和主卖点",
                        "composition_hint": "主体居中，左上留标题区",
                        "copy_goal": "突出品牌与核心卖点",
                    }
                ]
            }
        if name == "CopyPlan":
            return {
                "items": [
                    {
                        "shot_id": "shot-01",
                        "title": "高山原叶 头采鲜香",
                        "subtitle": "清润茶汤，日常自饮与礼赠都合适",
                        "bullets": ["鲜爽回甘", "茶形完整", "轻松冲泡"],
                        "cta": "茶香即刻上新",
                    }
                ]
            }
        if name == "LayoutPlan":
            return {
                "items": [
                    {
                        "shot_id": "shot-01",
                        "canvas_width": 1440,
                        "canvas_height": 1440,
                        "blocks": [
                            {"kind": "title", "x": 100, "y": 120, "width": 580, "height": 220, "font_size": 92, "align": "left"},
                            {"kind": "subtitle", "x": 100, "y": 360, "width": 560, "height": 180, "font_size": 48, "align": "left"},
                            {"kind": "bullets", "x": 100, "y": 570, "width": 520, "height": 250, "font_size": 40, "align": "left"},
                            {"kind": "cta", "x": 100, "y": 860, "width": 420, "height": 100, "font_size": 38, "align": "left"},
                        ],
                    }
                ]
            }
        if name == "ImagePromptPlan":
            return {
                "prompts": [
                    {
                        "shot_id": "shot-01",
                        "prompt": "Premium tea ecommerce hero shot, clean reserved copy space, elegant lighting, natural green palette",
                        "negative_prompt": "text, watermark, clutter",
                        "output_size": "1440x1440",
                    }
                ]
            }
        return {}
