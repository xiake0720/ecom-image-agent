"""详情图 prompt 规划服务。"""

from __future__ import annotations

from collections import defaultdict

from backend.schemas.detail import (
    DetailPageAssetRef,
    DetailPageCopyBlock,
    DetailPagePlanPayload,
    DetailPagePromptPlanItem,
)


class DetailPromptService:
    """把 plan+copy+素材映射为可执行图像 prompt。"""

    def build_prompt_plan(
        self,
        plan: DetailPagePlanPayload,
        copy_blocks: list[DetailPageCopyBlock],
        assets: list[DetailPageAssetRef],
    ) -> list[DetailPagePromptPlanItem]:
        """输出每张 1:3 长图的完整 prompt 计划。"""

        copy_map = {f"{item.page_id}:{item.screen_id}": item for item in copy_blocks}
        assets_by_role: dict[str, list[DetailPageAssetRef]] = defaultdict(list)
        for asset in assets:
            assets_by_role[asset.role].append(asset)

        items: list[DetailPagePromptPlanItem] = []
        for page in plan.pages:
            references: list[DetailPageAssetRef] = []
            screen_themes: list[str] = []
            layout_notes: list[str] = []
            copy_text_blocks: list[str] = []
            bound_roles: set[str] = set()
            for screen in page.screens:
                screen_themes.append(screen.theme)
                layout_notes.append(f"{screen.screen_id}:{screen.theme} -> {screen.goal}")
                for role in screen.suggested_asset_roles:
                    if role in bound_roles:
                        continue
                    if assets_by_role.get(role):
                        references.append(assets_by_role[role][0])
                        bound_roles.add(role)
                copy = copy_map.get(f"{page.page_id}:{screen.screen_id}")
                if copy:
                    copy_text_blocks.append(f"[{screen.screen_id}] 标题:{copy.headline}; 副标题:{copy.subheadline}; 卖点:{'、'.join(copy.selling_points)}")

            prompt = (
                f"生成一张 1:3 茶叶电商详情长图，统一风格锚点：{plan.global_style_anchor}。"
                f"本图包含两屏主题：{' / '.join(screen_themes)}。"
                "严格保持产品包装形态、品牌文字与识别元素，不可变形、不改字、不乱码。"
                "茶干、茶汤、叶底需真实，中文文案需清晰可读且排版高级。"
                f"页面文案：{' | '.join(copy_text_blocks)}。"
            )
            items.append(
                DetailPagePromptPlanItem(
                    page_id=page.page_id,
                    page_title=page.title,
                    global_style_anchor=plan.global_style_anchor,
                    screen_themes=screen_themes,
                    layout_notes=layout_notes,
                    prompt=prompt,
                    negative_prompt="low quality, deformed packaging, garbled Chinese text, mismatched brand logo",
                    references=references,
                )
            )
        return items

