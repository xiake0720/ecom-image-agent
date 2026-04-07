"""详情图规划服务。"""

from __future__ import annotations

import json
from pathlib import Path

from backend.engine.core.config import get_settings
from backend.engine.providers.llm.base import BaseTextProvider
from backend.engine.providers.router import build_capability_bindings
from backend.schemas.detail import (
    DetailAssetRole,
    DetailPageAssetRef,
    DetailPageJobCreatePayload,
    DetailPagePlanPage,
    DetailPagePlanPayload,
    DetailPagePlanScreen,
)


class DetailPlannerService:
    """负责生成茶叶详情图的结构化规划。"""

    screens_per_page = 1

    def __init__(self, template_root: Path) -> None:
        self.template_root = template_root

    def build_plan(
        self,
        payload: DetailPageJobCreatePayload,
        assets: list[DetailPageAssetRef],
        *,
        planning_provider: BaseTextProvider | None = None,
    ) -> DetailPagePlanPayload:
        """生成整套 3:4 单屏详情图规划。

        V1 优先走统一文本 provider；若模型不可用或结构不完整，再回退到模板化兜底。
        """

        provider = planning_provider or build_capability_bindings(get_settings()).planning_provider
        fallback = self._fallback_plan(payload, assets)
        prompt = self._build_prompt(payload, assets, fallback)
        try:
            result = provider.generate_structured(
                prompt,
                DetailPagePlanPayload,
                system_prompt=(
                    "你是茶叶电商详情图导演 Agent。"
                    "请只输出严格 JSON，面向天猫高端茶叶详情图，"
                    "每张图只规划一个独立 screen，成品比例为 3:4，且只能规划茶叶场景。"
                ),
            )
            return self._normalize_plan(result, payload, assets, fallback)
        except Exception:
            return fallback

    def _normalize_plan(
        self,
        plan: DetailPagePlanPayload,
        payload: DetailPageJobCreatePayload,
        assets: list[DetailPageAssetRef],
        fallback: DetailPagePlanPayload,
    ) -> DetailPagePlanPayload:
        """把模型输出修正为稳定可执行的 detail plan。"""

        normalized_pages: list[DetailPagePlanPage] = []
        source_pages = plan.pages or fallback.pages
        target_pages = payload.target_slice_count
        for page_index in range(target_pages):
            fallback_page = fallback.pages[page_index]
            source_page = source_pages[page_index] if page_index < len(source_pages) else fallback_page
            screens = self._normalize_screens(
                source_page.screens,
                fallback_page.screens,
                page_index=page_index,
                assets=assets,
            )
            normalized_pages.append(
                DetailPagePlanPage(
                    page_id=f"page-{page_index + 1:02d}",
                    title=source_page.title.strip() or fallback_page.title,
                    style_anchor=source_page.style_anchor.strip() or fallback_page.style_anchor,
                    narrative_position=page_index + 1,
                    screens=screens,
                )
            )

        fallback_narrative = fallback.narrative[:target_pages]
        narrative = [item.strip() for item in plan.narrative if item.strip()]
        if len(narrative) < target_pages:
            narrative = fallback_narrative
        total_pages = len(normalized_pages)
        return DetailPagePlanPayload(
            template_name=plan.template_name or fallback.template_name,
            category=payload.category,
            platform=payload.platform,
            style_preset=payload.style_preset,
            global_style_anchor=plan.global_style_anchor.strip() or fallback.global_style_anchor,
            narrative=narrative[:total_pages],
            total_screens=sum(len(page.screens) for page in normalized_pages),
            total_pages=total_pages,
            pages=normalized_pages,
        )

    def _normalize_screens(
        self,
        source_screens: list[DetailPagePlanScreen],
        fallback_screens: list[DetailPagePlanScreen],
        *,
        page_index: int,
        assets: list[DetailPageAssetRef],
    ) -> list[DetailPagePlanScreen]:
        normalized: list[DetailPagePlanScreen] = []
        for screen_index in range(self.screens_per_page):
            fallback_screen = fallback_screens[screen_index]
            source_screen = source_screens[screen_index] if screen_index < len(source_screens) else fallback_screen
            preferred_roles = source_screen.suggested_asset_roles or fallback_screen.suggested_asset_roles
            normalized.append(
                DetailPagePlanScreen(
                    screen_id=f"p{page_index + 1:02d}s{screen_index + 1}",
                    theme=source_screen.theme.strip() or fallback_screen.theme,
                    goal=source_screen.goal.strip() or fallback_screen.goal,
                    screen_type=source_screen.screen_type or fallback_screen.screen_type,
                    suggested_asset_roles=self._filter_roles(preferred_roles, assets, fallback_screen.suggested_asset_roles),
                )
            )
        return normalized

    def _filter_roles(
        self,
        roles: list[DetailAssetRole],
        assets: list[DetailPageAssetRef],
        fallback_roles: list[DetailAssetRole],
    ) -> list[DetailAssetRole]:
        existing_roles = {asset.role for asset in assets}
        matched = [role for role in roles if role in existing_roles]
        return matched or fallback_roles

    def _fallback_plan(
        self,
        payload: DetailPageJobCreatePayload,
        assets: list[DetailPageAssetRef],
    ) -> DetailPagePlanPayload:
        """在模型不可用时，按茶叶详情图模板输出兜底规划。"""

        template = self._load_template()
        blueprint = list(template.get("screen_blueprint", []))
        pages: list[DetailPagePlanPage] = []
        role_order = self._resolve_main_roles(payload)
        for page_index in range(payload.target_slice_count):
            screen_blueprint = blueprint[page_index % len(blueprint)]
            screen = self._build_screen(page_index, 1, screen_blueprint, assets, role_order)
            pages.append(
                DetailPagePlanPage(
                    page_id=f"page-{page_index + 1:02d}",
                    title=screen.theme,
                    style_anchor=str(template.get("global_style_anchor", "")),
                    narrative_position=page_index + 1,
                    screens=[screen],
                )
            )
        return DetailPagePlanPayload(
            template_name=str(template.get("name", "tea_tmall_premium_v1")),
            category=payload.category,
            platform=payload.platform,
            style_preset=payload.style_preset,
            global_style_anchor=str(template.get("global_style_anchor", "天猫高端茶叶详情图，留白克制、材质真实、中文清晰")),
            narrative=[page.title for page in pages],
            total_screens=payload.target_slice_count,
            total_pages=payload.target_slice_count,
            pages=pages,
        )

    def _build_screen(
        self,
        page_index: int,
        screen_index: int,
        blueprint: dict[str, object],
        assets: list[DetailPageAssetRef],
        role_order: list[DetailAssetRole],
    ) -> DetailPagePlanScreen:
        preferred_roles = [str(item) for item in blueprint.get("preferred_roles", [])]
        roles: list[DetailAssetRole] = []
        for role in [*preferred_roles, *role_order]:
            if any(asset.role == role for asset in assets) and role not in roles:
                roles.append(role)  # type: ignore[arg-type]
        if not roles:
            roles = [assets[0].role if assets else role_order[0]]
        return DetailPagePlanScreen(
            screen_id=f"p{page_index + 1:02d}s{screen_index}",
            theme=str(blueprint.get("theme", "茶叶详情图表达")),
            goal=self._build_screen_goal(str(blueprint.get("theme", ""))),
            screen_type=str(blueprint.get("screen_type", "visual")),
            suggested_asset_roles=roles[:3],
        )

    def _build_screen_goal(self, theme: str) -> str:
        if "干茶" in theme:
            return "突出干茶条索、色泽与原叶等级，建立质感认知。"
        if "茶汤" in theme:
            return "表现汤色通透感、香气氛围与饮用欲望。"
        if "叶底" in theme:
            return "说明叶底舒展状态与原料真实度。"
        if "参数" in theme or "冲泡" in theme:
            return "用克制信息表达参数、冲泡建议与购买行动。"
        if "卖点" in theme:
            return "把核心卖点拆成适合单屏阅读的信息表达。"
        return "建立品牌气质与产品主体识别，形成整套详情图的叙事开篇。"

    def _resolve_main_roles(self, payload: DetailPageJobCreatePayload) -> list[DetailAssetRole]:
        if payload.prefer_main_result_first:
            return ["main_result", "packaging", "scene_ref"]
        return ["packaging", "main_result", "scene_ref"]

    def _build_prompt(
        self,
        payload: DetailPageJobCreatePayload,
        assets: list[DetailPageAssetRef],
        fallback: DetailPagePlanPayload,
    ) -> str:
        """拼接规划模型提示词，把所有输入显式收口进去。"""

        asset_manifest = [
            {
                "role": asset.role,
                "file_name": asset.file_name,
                "source_task_id": asset.source_task_id,
                "source_result_file": asset.source_result_file,
            }
            for asset in assets
        ]
        return (
            "请为茶叶电商详情图生成结构化规划。"
            f"品牌名={payload.brand_name or '未提供'}；"
            f"商品名={payload.product_name or '未提供'}；"
            f"茶类={payload.tea_type}；平台={payload.platform}；风格={payload.style_preset}；"
            f"价格带={payload.price_band or '未提供'}；目标屏数={payload.target_slice_count}；"
            f"卖点补充={payload.selling_points or ['未提供']}；"
            f"商品参数={payload.specs or {'默认': '未提供'}}；"
            f"冲泡建议={payload.brew_suggestion or '未提供'}；"
            f"用户额外要求={payload.extra_requirements or '未提供'}；"
            f"优先使用主图结果={payload.prefer_main_result_first}；"
            f"素材清单={json.dumps(asset_manifest, ensure_ascii=False)}；"
            "请只规划天猫风格茶叶详情图，每张图只包含一个 screen，成品为 3:4；"
            "输出字段必须包含 global_style_anchor、narrative、total_pages、total_screens、pages。"
            f"若不确定，请至少参考这个兜底结构：{json.dumps(fallback.model_dump(mode='json'), ensure_ascii=False)}"
        )

    def _load_template(self) -> dict[str, object]:
        """读取茶叶详情图模板。"""

        template_path = self.template_root / "detail_pages" / "tea_tmall_premium_v1.json"
        return json.loads(template_path.read_text(encoding="utf-8"))
