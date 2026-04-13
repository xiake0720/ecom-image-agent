from __future__ import annotations

import logging
from typing import Any

from backend.engine.domain.usage import ProviderUsageSnapshot
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
        self.last_usage = ProviderUsageSnapshot.empty()
        logger.info("当前文本 provider 处于 mock 模式，返回本地结构化占位数据，schema=%s", response_model.__name__)
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
        if name == "DetailPagePlanPayload":
            return {
                "template_name": "tea_tmall_premium_v1",
                "category": "tea",
                "platform": "tmall",
                "style_preset": "tea_tmall_premium_light",
                "global_style_anchor": "天猫高端茶叶详情图，米白留白、深茶墨绿、材质克制、中文排版清晰",
                "narrative": ["品牌主视觉", "核心卖点", "干茶细节", "茶汤氛围"],
                "total_screens": 4,
                "total_pages": 4,
                "pages": [
                    {
                        "page_id": "page-01",
                        "title": "品牌与产品主视觉",
                        "style_anchor": "高级留白",
                        "narrative_position": 1,
                        "screens": [
                            {
                                "screen_id": "p01s1",
                                "theme": "品牌与产品主体",
                                "goal": "建立品牌识别与产品高级感",
                                "screen_type": "visual",
                                "suggested_asset_roles": ["main_result", "packaging"],
                            },
                        ],
                    },
                    {
                        "page_id": "page-02",
                        "title": "干茶与工艺细节",
                        "style_anchor": "质感微距",
                        "narrative_position": 2,
                        "screens": [
                            {
                                "screen_id": "p02s1",
                                "theme": "干茶条索与色泽",
                                "goal": "突出原叶质感与等级",
                                "screen_type": "visual",
                                "suggested_asset_roles": ["dry_leaf", "packaging"],
                            },
                        ],
                    },
                    {
                        "page_id": "page-03",
                        "title": "茶汤表现与香气氛围",
                        "style_anchor": "光感通透",
                        "narrative_position": 3,
                        "screens": [
                            {
                                "screen_id": "p03s1",
                                "theme": "茶汤色泽与通透感",
                                "goal": "强调汤色、清澈度与高级感",
                                "screen_type": "visual",
                                "suggested_asset_roles": ["tea_soup", "scene_ref"],
                            },
                        ],
                    },
                    {
                        "page_id": "page-04",
                        "title": "叶底与参数说明",
                        "style_anchor": "真实档案感",
                        "narrative_position": 4,
                        "screens": [
                            {
                                "screen_id": "p04s1",
                                "theme": "叶底舒展状态",
                                "goal": "体现叶底完整度与鲜活度",
                                "screen_type": "visual",
                                "suggested_asset_roles": ["leaf_bottom", "scene_ref"],
                            },
                        ],
                    },
                ],
            }
        if name == "DetailCopyPlanResult":
            return {
                "items": [
                    {
                        "page_id": "page-01",
                        "screen_id": "p01s1",
                        "headline": "山场原叶，杯中见真章",
                        "subheadline": "品牌首屏先立住包装与气质",
                        "selling_points": ["包装识别统一", "高端留白", "主体明确"],
                        "body_copy": "以品牌主视觉建立第一印象，强调真实包装与克制氛围。",
                        "parameter_copy": "",
                        "cta_copy": "",
                        "notes": "标题控制在 10 字内。",
                    }
                ]
            }
        if name == "DetailPromptPlanResult":
            return {
                "items": [
                    {
                        "page_id": "page-01",
                        "page_title": "品牌与产品主视觉",
                        "screen_themes": ["品牌与产品主体"],
                        "layout_notes": ["单屏构图，包装正面保留完整识别", "主体与文案分区清晰"],
                        "prompt": "高端茶叶电商详情单屏图，包装主体稳定，留白大气，材质真实，中文排版清晰。",
                        "negative_prompt": "garbled Chinese text, deformed packaging, replaced logo, cluttered layout",
                        "reference_roles": ["main_result", "packaging"],
                    }
                ]
            }
        return {}
