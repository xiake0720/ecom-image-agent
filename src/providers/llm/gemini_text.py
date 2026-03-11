from __future__ import annotations

from typing import Any
from src.providers.llm.base import BaseTextProvider, StructuredModel


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
        # TODO: Replace this mock-only implementation with a real Gemini API call after MVP approval.
        return self._mock_response(response_model)

    def _mock_response(self, response_model: type[StructuredModel]) -> StructuredModel:
        payload = self._mock_payload(response_model)
        return response_model.model_validate(payload)

    def _mock_payload(self, response_model: type[StructuredModel]) -> dict[str, Any]:
        name = response_model.__name__
        if name == "ProductAnalysis":
            return {
                "category": "tea",
                "product_type": "绿茶",
                "selling_points": ["茶形完整", "香气清新", "适合礼赠"],
                "visual_style_keywords": ["清透", "自然", "高端电商"],
                "recommended_focuses": ["茶叶干茶", "茶汤色泽", "礼盒质感"],
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
