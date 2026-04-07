"""详情图最终渲染 prompt 服务。"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from backend.engine.core.config import get_settings
from backend.engine.providers.llm.base import BaseTextProvider
from backend.engine.providers.router import build_capability_bindings
from backend.schemas.detail import (
    DetailPageAssetRef,
    DetailPageCopyBlock,
    DetailPageJobCreatePayload,
    DetailPagePlanPayload,
    DetailPagePromptPlanItem,
    DetailPromptDraftItem,
    DetailPromptPlanResult,
)


class DetailPromptService:
    """把 plan、copy、用户参数和参考图收口成 Banana2 最终执行 prompt。"""

    def build_prompt_plan(
        self,
        payload: DetailPageJobCreatePayload,
        plan: DetailPagePlanPayload,
        copy_blocks: list[DetailPageCopyBlock],
        assets: list[DetailPageAssetRef],
        *,
        planning_provider: BaseTextProvider | None = None,
    ) -> list[DetailPagePromptPlanItem]:
        """输出每张 3:4 单屏详情图的最终 render prompt。"""

        provider = planning_provider or build_capability_bindings(get_settings()).planning_provider
        fallback = self._fallback_prompt_plan(payload, plan, copy_blocks, assets)
        prompt = self._build_prompt(payload, plan, copy_blocks, assets, fallback)
        try:
            result = provider.generate_structured(
                prompt,
                DetailPromptPlanResult,
                system_prompt=(
                    "你是茶叶详情图 Prompt Agent。"
                    "请只输出严格 JSON，生成适合 Banana2 的最终渲染 prompt 草案，"
                    "必须强调包装保护、中文清晰、不乱码、版式自然。"
                ),
            )
            return self._normalize_prompt_plan(result.items, payload, plan, copy_blocks, assets, fallback)
        except Exception:
            return fallback

    def _normalize_prompt_plan(
        self,
        draft_items: list[DetailPromptDraftItem],
        payload: DetailPageJobCreatePayload,
        plan: DetailPagePlanPayload,
        copy_blocks: list[DetailPageCopyBlock],
        assets: list[DetailPageAssetRef],
        fallback: list[DetailPagePromptPlanItem],
    ) -> list[DetailPagePromptPlanItem]:
        draft_map = {item.page_id: item for item in draft_items}
        fallback_map = {item.page_id: item for item in fallback}
        copy_map = self._build_copy_map(copy_blocks)
        assets_by_role = self._group_assets_by_role(assets)
        normalized: list[DetailPagePromptPlanItem] = []
        for page in plan.pages:
            draft = draft_map.get(page.page_id)
            fallback_item = fallback_map[page.page_id]
            reference_roles = list(dict.fromkeys((draft.reference_roles if draft else []) or [ref.role for ref in fallback_item.references]))
            references = self._resolve_references(reference_roles, page.screens, assets_by_role, fallback_item.references)
            layout_notes = draft.layout_notes if draft and draft.layout_notes else fallback_item.layout_notes
            normalized.append(
                DetailPagePromptPlanItem(
                    page_id=page.page_id,
                    page_title=(draft.page_title if draft and draft.page_title.strip() else page.title),
                    global_style_anchor=plan.global_style_anchor,
                    screen_themes=(draft.screen_themes if draft and draft.screen_themes else [screen.theme for screen in page.screens]),
                    layout_notes=layout_notes,
                    prompt=self._compose_final_prompt(
                        payload=payload,
                        page=page,
                        copy_blocks=copy_map.get(page.page_id, []),
                        references=references,
                        prompt_seed=draft.prompt if draft else fallback_item.prompt,
                        layout_notes=layout_notes,
                        plan=plan,
                    ),
                    negative_prompt=self._compose_negative_prompt(draft.negative_prompt if draft else fallback_item.negative_prompt),
                    references=references,
                    target_aspect_ratio=fallback_item.target_aspect_ratio,
                    target_width=fallback_item.target_width,
                    target_height=fallback_item.target_height,
                )
            )
        return normalized

    def _fallback_prompt_plan(
        self,
        payload: DetailPageJobCreatePayload,
        plan: DetailPagePlanPayload,
        copy_blocks: list[DetailPageCopyBlock],
        assets: list[DetailPageAssetRef],
    ) -> list[DetailPagePromptPlanItem]:
        """模型不可用时输出可执行的 prompt plan。"""

        copy_map = self._build_copy_map(copy_blocks)
        assets_by_role = self._group_assets_by_role(assets)
        rows: list[DetailPagePromptPlanItem] = []
        for page in plan.pages:
            references = self._resolve_references([], page.screens, assets_by_role, [])
            primary_screen = page.screens[0]
            layout_notes = [
                f"{primary_screen.screen_id} 为独立单屏，主题为 {primary_screen.theme}",
                "画面按 3:4 详情页单屏组织信息，主体与文案分区清晰。",
                "保留清晰文字区，避免信息挤压主体。",
            ]
            rows.append(
                DetailPagePromptPlanItem(
                    page_id=page.page_id,
                    page_title=page.title,
                    global_style_anchor=plan.global_style_anchor,
                    screen_themes=[screen.theme for screen in page.screens],
                    layout_notes=layout_notes,
                    prompt=self._compose_final_prompt(
                        payload=payload,
                        page=page,
                        copy_blocks=copy_map.get(page.page_id, []),
                        references=references,
                        prompt_seed="高级茶叶电商详情单屏图，真实材质、留白克制、产品主体稳定。",
                        layout_notes=layout_notes,
                        plan=plan,
                    ),
                    negative_prompt=self._compose_negative_prompt(
                        "garbled Chinese text, deformed packaging, replaced logo, cluttered layout"
                    ),
                    references=references,
                )
            )
        return rows

    def _compose_final_prompt(
        self,
        *,
        payload: DetailPageJobCreatePayload,
        page: Any,
        copy_blocks: list[DetailPageCopyBlock],
        references: list[DetailPageAssetRef],
        prompt_seed: str,
        layout_notes: list[str],
        plan: DetailPagePlanPayload,
    ) -> str:
        """把所有用户输入与页面上下文强制收口到最终生图指令。"""

        reference_desc = [
            (
                f"{ref.role}:{ref.file_name}"
                if ref.source_type != "main_task"
                else f"{ref.role}:{ref.file_name}(source_task_id={ref.source_task_id}, source_result_file={ref.source_result_file})"
            )
            for ref in references
        ]
        copy_desc = [
            json.dumps(
                {
                    "screen_id": block.screen_id,
                    "headline": block.headline,
                    "subheadline": block.subheadline,
                    "selling_points": block.selling_points,
                    "body_copy": block.body_copy,
                    "parameter_copy": block.parameter_copy,
                    "cta_copy": block.cta_copy,
                    "notes": block.notes,
                },
                ensure_ascii=False,
            )
            for block in copy_blocks
        ]
        user_specs = json.dumps(payload.specs or {}, ensure_ascii=False)
        user_points = json.dumps(payload.selling_points or [], ensure_ascii=False)
        lines = [
            "使用 Banana2 生成一张 3:4 茶叶电商详情单屏图，一次请求只输出一张图，不做本地拼接。",
            f"平台={payload.platform}；类目={payload.category}；茶类={payload.tea_type}；品牌名={payload.brand_name or '未提供'}；商品名={payload.product_name or '未提供'}。",
            f"风格 preset={payload.style_preset}；全局风格锚点={plan.global_style_anchor}；价格带={payload.price_band or '未提供'}。",
            f"页面标题={page.title}；单屏主题={[screen.theme for screen in page.screens]}。",
            f"页面目标={[screen.goal for screen in page.screens]}。",
            f"用户卖点补充={user_points}；商品参数={user_specs}；冲泡建议={payload.brew_suggestion or '未提供'}；额外要求={payload.extra_requirements or '未提供'}。",
            f"参考图绑定={reference_desc or ['无']}",
            f"版式提示={layout_notes}",
            f"图中文字内容={copy_desc}",
            "包装保护约束：不改包装、不改包装上的文字、不变形、不替换品牌识别、不杜撰标签细节。",
            "中文约束：中文必须清晰、可读、不乱码、字重自然、排版层级明确、不要拥挤。",
            "画面约束：真实茶叶质感、真实茶汤与叶底，不要塑料感，不要廉价广告风，不要低幼装饰。",
            "执行风格：天猫高端茶叶详情图，克制留白、材质真实、配色稳重、适合电商单屏阅读。",
            f"Prompt 草案={prompt_seed.strip() or '高级茶叶详情图，单屏表达明确。'}",
        ]
        return "\n".join(lines).strip()

    def _compose_negative_prompt(self, seed: str) -> str:
        parts = [
            "deformed packaging",
            "replaced brand logo",
            "changed package text",
            "garbled Chinese text",
            "messy layout",
            "low resolution",
            "extra products",
            "childish ecommerce style",
        ]
        normalized_seed = str(seed or "").strip()
        if normalized_seed:
            parts.insert(0, normalized_seed)
        return ", ".join(dict.fromkeys(parts))

    def _resolve_references(
        self,
        reference_roles: list[str],
        screens: list[Any],
        assets_by_role: dict[str, list[DetailPageAssetRef]],
        fallback_refs: list[DetailPageAssetRef],
    ) -> list[DetailPageAssetRef]:
        ordered_roles = list(dict.fromkeys(reference_roles))
        if not ordered_roles:
            for screen in screens:
                ordered_roles.extend([role for role in screen.suggested_asset_roles if role not in ordered_roles])
        refs: list[DetailPageAssetRef] = []
        for role in ordered_roles:
            candidates = assets_by_role.get(role, [])
            if candidates:
                refs.append(candidates[0])
        if refs:
            return refs[:5]
        if fallback_refs:
            return fallback_refs
        # 页面完全没有命中的情况下，至少保留 packaging/main_result 中可用的一项。
        for role in ["packaging", "main_result", "scene_ref"]:
            candidates = assets_by_role.get(role, [])
            if candidates:
                return [candidates[0]]
        return []

    def _build_copy_map(self, copy_blocks: list[DetailPageCopyBlock]) -> dict[str, list[DetailPageCopyBlock]]:
        grouped: dict[str, list[DetailPageCopyBlock]] = defaultdict(list)
        for item in copy_blocks:
            grouped[item.page_id].append(item)
        return grouped

    def _group_assets_by_role(self, assets: list[DetailPageAssetRef]) -> dict[str, list[DetailPageAssetRef]]:
        grouped: dict[str, list[DetailPageAssetRef]] = defaultdict(list)
        for asset in assets:
            grouped[asset.role].append(asset)
        return grouped

    def _build_prompt(
        self,
        payload: DetailPageJobCreatePayload,
        plan: DetailPagePlanPayload,
        copy_blocks: list[DetailPageCopyBlock],
        assets: list[DetailPageAssetRef],
        fallback: list[DetailPagePromptPlanItem],
    ) -> str:
        """拼接 prompt 规划模型提示词。"""

        return (
            "请把茶叶详情图 plan + copy 转成 Banana2 渲染 prompt 草案。"
            f"品牌名={payload.brand_name or '未提供'}；商品名={payload.product_name or '未提供'}；"
            f"茶类={payload.tea_type}；平台={payload.platform}；风格={payload.style_preset}；"
            f"卖点补充={payload.selling_points or ['未提供']}；参数={payload.specs or {'默认': '未提供'}}；"
            f"冲泡建议={payload.brew_suggestion or '未提供'}；额外要求={payload.extra_requirements or '未提供'}；"
            f"plan={json.dumps(plan.model_dump(mode='json'), ensure_ascii=False)}；"
            f"copy={json.dumps([item.model_dump(mode='json') for item in copy_blocks], ensure_ascii=False)}；"
            f"assets={json.dumps([item.model_dump(mode='json') for item in assets], ensure_ascii=False)}；"
            "请输出 items 数组，每项包含 page_id、page_title、screen_themes、layout_notes、prompt、negative_prompt、reference_roles。"
            f"如不确定，可参考兜底结构：{json.dumps([item.model_dump(mode='json') for item in fallback[:2]], ensure_ascii=False)}"
        )
