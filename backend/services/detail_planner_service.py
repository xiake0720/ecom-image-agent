"""详情图规划服务。"""

from __future__ import annotations

import json
from pathlib import Path

from backend.schemas.detail import DetailPageAssetRef, DetailPageJobCreatePayload, DetailPagePlanPage, DetailPagePlanPayload, DetailPagePlanScreen


class DetailPlannerService:
    """负责根据输入与模板生成详情图结构化规划。"""

    def __init__(self, template_root: Path) -> None:
        self.template_root = template_root

    def build_plan(self, payload: DetailPageJobCreatePayload, assets: list[DetailPageAssetRef]) -> DetailPagePlanPayload:
        """生成整套 1:3 长图规划。"""

        template = self._load_template()
        target_pages = payload.target_slice_count
        total_screens = target_pages * 2
        tea_focus = self._resolve_tea_focus(payload.tea_type)
        narrative = [
            "品牌首屏与产品主体",
            "核心卖点展开",
            "茶干条索细节",
            "茶汤质感与香气表达",
            "叶底与工艺说明",
            "参数/冲泡/场景/发货信息",
        ]
        screen_defs = template.get("screen_blueprint", [])
        pages: list[DetailPagePlanPage] = []
        for page_index in range(target_pages):
            first = screen_defs[(page_index * 2) % len(screen_defs)]
            second = screen_defs[(page_index * 2 + 1) % len(screen_defs)]
            screens = [
                self._build_screen(page_index, 1, first, tea_focus, assets),
                self._build_screen(page_index, 2, second, tea_focus, assets),
            ]
            pages.append(
                DetailPagePlanPage(
                    page_id=f"page-{page_index+1:02d}",
                    title=f"详情长图 {page_index+1:02d}",
                    style_anchor=template.get("global_style_anchor", "天猫茶叶高端统一风格"),
                    narrative_position=page_index + 1,
                    screens=screens,
                )
            )
        return DetailPagePlanPayload(
            template_name=str(template.get("name", "tea_tmall_premium_v1")),
            category=payload.category,
            platform=payload.platform,
            style_preset=payload.style_preset,
            global_style_anchor=str(template.get("global_style_anchor", "高级克制、统一材质、中文排版清晰")),
            narrative=narrative,
            total_screens=total_screens,
            total_pages=target_pages,
            pages=pages,
        )

    def _build_screen(
        self,
        page_index: int,
        screen_index: int,
        blueprint: dict[str, object],
        tea_focus: list[str],
        assets: list[DetailPageAssetRef],
    ) -> DetailPagePlanScreen:
        """构建单屏规划，确保素材角色可追踪。"""

        preferred_roles = [str(item) for item in blueprint.get("preferred_roles", [])]
        matched_roles = [role for role in preferred_roles if any(asset.role == role for asset in assets)]
        fallback_roles = preferred_roles if preferred_roles else ["packaging"]
        return DetailPagePlanScreen(
            screen_id=f"p{page_index+1:02d}s{screen_index}",
            theme=str(blueprint.get("theme", "茶叶卖点展示")),
            goal=f"强调{tea_focus[(page_index + screen_index - 1) % len(tea_focus)]}，并保持全套视觉统一",
            screen_type=str(blueprint.get("screen_type", "visual")),
            suggested_asset_roles=matched_roles or fallback_roles,
        )

    def _resolve_tea_focus(self, tea_type: str) -> list[str]:
        """按茶类返回默认卖点语义。"""

        normalized = tea_type.lower()
        if any(item in normalized for item in ["乌龙", "单丛", "凤凰"]):
            return ["香气层次", "回甘", "山韵", "耐泡"]
        if any(item in normalized for item in ["红茶", "金骏眉", "正山小种"]):
            return ["甜润", "蜜香果香", "顺口", "早餐下午茶"]
        if any(item in normalized for item in ["花茶", "茉莉", "桂花"]):
            return ["鲜灵花香", "清爽", "办公室友好", "新手友好"]
        if any(item in normalized for item in ["白茶", "陈皮"]):
            return ["清润", "柔和", "回甘", "日常轻饮"]
        return ["香气", "回甘", "质感", "日常适饮"]

    def _load_template(self) -> dict[str, object]:
        """读取茶叶详情图模板。"""

        template_path = self.template_root / "detail_pages" / "tea_tmall_premium_v1.json"
        return json.loads(template_path.read_text(encoding="utf-8"))

