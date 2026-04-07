"""详情图文案生成服务。"""

from __future__ import annotations

import json

from backend.engine.core.config import get_settings
from backend.engine.providers.llm.base import BaseTextProvider
from backend.engine.providers.router import build_capability_bindings
from backend.schemas.detail import (
    DetailCopyPlanResult,
    DetailPageCopyBlock,
    DetailPageJobCreatePayload,
    DetailPagePlanPayload,
)


class DetailCopyService:
    """负责生成每一屏的结构化中文文案。"""

    def build_copy(
        self,
        payload: DetailPageJobCreatePayload,
        plan: DetailPagePlanPayload,
        *,
        planning_provider: BaseTextProvider | None = None,
    ) -> list[DetailPageCopyBlock]:
        """输出与每个 screen 绑定的 copy plan。"""

        provider = planning_provider or build_capability_bindings(get_settings()).planning_provider
        fallback = self._fallback_copy(payload, plan)
        prompt = self._build_prompt(payload, plan, fallback)
        try:
            result = provider.generate_structured(
                prompt,
                DetailCopyPlanResult,
                system_prompt=(
                    "你是茶叶电商详情图文案导演。"
                    "请只输出严格 JSON，文案必须克制、高级、真实、适合上图，"
                    "控制字数，避免冗长段落和夸张功效表达。"
                ),
            )
            return self._normalize_copy(result.items, plan, fallback)
        except Exception:
            return fallback

    def _normalize_copy(
        self,
        items: list[DetailPageCopyBlock],
        plan: DetailPagePlanPayload,
        fallback: list[DetailPageCopyBlock],
    ) -> list[DetailPageCopyBlock]:
        """确保每个 screen 都有可执行文案。"""

        item_map = {f"{item.page_id}:{item.screen_id}": item for item in items}
        fallback_map = {f"{item.page_id}:{item.screen_id}": item for item in fallback}
        normalized: list[DetailPageCopyBlock] = []
        for page in plan.pages:
            for screen in page.screens:
                key = f"{page.page_id}:{screen.screen_id}"
                source = item_map.get(key) or fallback_map[key]
                normalized.append(
                    DetailPageCopyBlock(
                        page_id=page.page_id,
                        screen_id=screen.screen_id,
                        headline=self._trim(source.headline, 18) or fallback_map[key].headline,
                        subheadline=self._trim(source.subheadline, 28),
                        selling_points=[self._trim(point, 14) for point in source.selling_points if self._trim(point, 14)][:3]
                        or fallback_map[key].selling_points,
                        body_copy=self._trim(source.body_copy, 44),
                        parameter_copy=self._trim(source.parameter_copy, 28),
                        cta_copy=self._trim(source.cta_copy, 18),
                        notes=self._trim(source.notes, 48),
                    )
                )
        return normalized

    def _fallback_copy(
        self,
        payload: DetailPageJobCreatePayload,
        plan: DetailPagePlanPayload,
    ) -> list[DetailPageCopyBlock]:
        """在模型不可用时输出可追踪的基础文案。"""

        rows: list[DetailPageCopyBlock] = []
        default_points = payload.selling_points or ["原叶清香", "汤感顺滑", "适合自饮与礼赠"]
        spec_text = " / ".join([f"{key}:{value}" for key, value in payload.specs.items()][:4])
        for page in plan.pages:
            for screen in page.screens:
                rows.append(
                    DetailPageCopyBlock(
                        page_id=page.page_id,
                        screen_id=screen.screen_id,
                        headline=self._fallback_headline(payload, screen.theme),
                        subheadline=self._fallback_subheadline(payload, screen.theme),
                        selling_points=default_points[:3],
                        body_copy=self._fallback_body(screen.theme, payload),
                        parameter_copy=spec_text,
                        cta_copy="收藏加购，随时开泡",
                        notes="中文排版要清晰克制，避免信息过密；包装文字不可擅改。",
                    )
                )
        return rows

    def _fallback_headline(self, payload: DetailPageJobCreatePayload, theme: str) -> str:
        if "干茶" in theme:
            return "看得见的原叶条索"
        if "茶汤" in theme:
            return "一杯通透，香气舒展"
        if "叶底" in theme:
            return "舒展叶底，真实可见"
        if "参数" in theme or "冲泡" in theme:
            return "参数清楚，冲泡简单"
        return f"{payload.tea_type} · 质感上新"

    def _fallback_subheadline(self, payload: DetailPageJobCreatePayload, theme: str) -> str:
        if "品牌" in theme:
            return f"{payload.brand_name or '茶叶工作台'} 详情图首屏，先建立产品识别。"
        if "卖点" in theme:
            return "把核心卖点拆成适合单屏阅读的信息。"
        return f"{payload.product_name or payload.tea_type}，适合茶叶电商详情图表达。"

    def _fallback_body(self, theme: str, payload: DetailPageJobCreatePayload) -> str:
        if "干茶" in theme:
            return "通过微距与留白表现干茶条索、色泽和等级感。"
        if "茶汤" in theme:
            return "用通透汤色与柔和光感传达香气层次和入口体验。"
        if "叶底" in theme:
            return "叶底舒展状态用于补足真实度与原料信任感。"
        if "参数" in theme or "冲泡" in theme:
            brew = payload.brew_suggestion or "建议按个人口味调整投茶量与水温。"
            return self._trim(brew, 44)
        return "保持高级克制的电商表达，不夸张，不堆砌大字。"

    def _build_prompt(
        self,
        payload: DetailPageJobCreatePayload,
        plan: DetailPagePlanPayload,
        fallback: list[DetailPageCopyBlock],
    ) -> str:
        """拼接文案生成提示词。"""

        screens = [
            {
                "page_id": page.page_id,
                "page_title": page.title,
                "screen_id": screen.screen_id,
                "theme": screen.theme,
                "goal": screen.goal,
                "screen_type": screen.screen_type,
            }
            for page in plan.pages
            for screen in page.screens
        ]
        return (
            "请为茶叶电商详情图每个 screen 生成中文文案。"
            f"品牌名={payload.brand_name or '未提供'}；"
            f"商品名={payload.product_name or '未提供'}；"
            f"茶类={payload.tea_type}；平台={payload.platform}；风格={plan.global_style_anchor}；"
            f"卖点补充={payload.selling_points or ['未提供']}；"
            f"规格参数={payload.specs or {'默认': '未提供'}}；"
            f"冲泡建议={payload.brew_suggestion or '未提供'}；"
            f"额外要求={payload.extra_requirements or '未提供'}；"
            f"screen 清单={json.dumps(screens, ensure_ascii=False)}；"
            "请输出 items 数组，每项包含 page_id、screen_id、headline、subheadline、"
            "selling_points、body_copy、parameter_copy、cta_copy、notes。"
            f"如不确定，可参考这个兜底示例：{json.dumps([item.model_dump(mode='json') for item in fallback[:2]], ensure_ascii=False)}"
        )

    def _trim(self, text: str, max_length: int) -> str:
        value = str(text or "").strip()
        return value[:max_length]
