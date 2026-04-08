"""详情图文案生成服务。"""

from __future__ import annotations

from backend.schemas.detail import (
    DetailPageCopyBlock,
    DetailPageJobCreatePayload,
    DetailPagePlanPage,
    DetailPagePlanPayload,
)


class DetailCopyService:
    """按页职责生成稳定的短文案。

    这里默认走规则化生成，避免模型在参数页、品牌页里发明不存在的信息。
    """

    headline_best_max = 8
    headline_hard_max = 12
    subheadline_best_max = 16
    subheadline_hard_max = 24
    selling_point_max = 6
    selling_point_count = 3

    def build_copy(
        self,
        payload: DetailPageJobCreatePayload,
        plan: DetailPagePlanPayload,
        *,
        planning_provider: object | None = None,
    ) -> list[DetailPageCopyBlock]:
        """输出与每个 screen 绑定的 copy plan。"""

        del planning_provider
        return [self._build_page_copy(payload, page) for page in plan.pages]

    def _build_page_copy(
        self,
        payload: DetailPageJobCreatePayload,
        page: DetailPagePlanPage,
    ) -> DetailPageCopyBlock:
        screen = page.screens[0]
        headline, subheadline = self._resolve_headlines(payload, page)
        selling_points = self._resolve_selling_points(payload, page)
        body_copy = self._resolve_body_copy(payload, page)
        parameter_copy = self._resolve_parameter_copy(payload, page)
        cta_copy = self._resolve_cta(page)
        notes = self._resolve_notes(page)
        return DetailPageCopyBlock(
            page_id=page.page_id,
            screen_id=screen.screen_id,
            headline_level="primary",
            headline=self._trim(headline, self.headline_hard_max),
            subheadline=self._trim(subheadline, self.subheadline_hard_max),
            selling_points=selling_points[: self.selling_point_count],
            body_copy=self._trim(body_copy, 40),
            parameter_copy=self._trim(parameter_copy, 60),
            cta_copy=self._trim(cta_copy, 12),
            notes=self._trim(notes, 80),
        )

    def _resolve_headlines(
        self,
        payload: DetailPageJobCreatePayload,
        page: DetailPagePlanPage,
    ) -> tuple[str, str]:
        display_name = self._display_name(payload)
        if page.page_role == "hero_opening":
            return self._trim(display_name, self.headline_best_max), self._trim(payload.brand_name or payload.tea_type, self.subheadline_best_max)
        if page.page_role == "dry_leaf_evidence":
            return "茶干条索", "看清干茶层次"
        if page.page_role == "tea_soup_evidence":
            return "茶汤通透", "杯中观感更直观"
        if page.page_role == "parameter_and_closing":
            return "参数清晰", "关键信息一屏看完"
        if page.page_role == "leaf_bottom_process_evidence":
            return "叶底可见", "舒展层次更直观"
        if page.page_role == "brand_trust":
            return "礼赠质感", "品牌表达更稳重"
        if page.page_role == "gift_openbox_portable":
            return "开盒层次", "礼赠与收纳兼顾"
        if page.page_role == "scene_value_story":
            return "茶席氛围", "饮用场景更有代入感"
        if page.page_role == "brewing_method_info":
            return "冲泡建议", "按输入信息简明呈现"
        if page.page_role == "packaging_structure_value":
            return "包装细节", "结构与材质更可感"
        if page.page_role == "package_closeup_evidence":
            return "近景质感", "局部细节更清楚"
        if page.page_role == "brand_closing":
            return "品牌收尾", "统一风格完成收束"
        return self._trim(display_name, self.headline_best_max), ""

    def _resolve_selling_points(
        self,
        payload: DetailPageJobCreatePayload,
        page: DetailPagePlanPage,
    ) -> list[str]:
        base_points = [self._trim(point, self.selling_point_max) for point in payload.selling_points if point.strip()]
        if page.page_role == "hero_opening":
            points = base_points[:3] or [payload.tea_type[:4] or "茶叶", "包装稳定", "质感呈现"]
            return self._normalize_points(points)
        if page.page_role == "dry_leaf_evidence":
            return self._normalize_points(["条索清晰", "色泽自然", "纹理可见"])
        if page.page_role == "tea_soup_evidence":
            return self._normalize_points(["汤感通透", "杯中清亮", "氛围克制"])
        if page.page_role == "parameter_and_closing":
            return self._normalize_points(["参数卡片", "信息克制", "便于对比"])
        if page.page_role == "leaf_bottom_process_evidence":
            return self._normalize_points(["舒展可见", "层次自然", "细节真实"])
        if page.page_role == "brand_trust":
            return self._normalize_points(["品牌表达", "礼赠友好", "风格统一"])
        if page.page_role == "gift_openbox_portable":
            return self._normalize_points(["开盒层次", "礼赠友好", "便于收纳"])
        if page.page_role == "scene_value_story":
            return self._normalize_points(["茶席氛围", "场景自然", "节奏舒展"])
        if page.page_role == "brewing_method_info":
            return self._normalize_points(["按输入呈现", "避免猜测", "信息简洁"])
        if page.page_role in {"packaging_structure_value", "package_closeup_evidence"}:
            return self._normalize_points(["结构稳定", "材质可感", "近景清晰"])
        return self._normalize_points(base_points[:3] or ["风格统一", "信息清晰"])

    def _resolve_body_copy(
        self,
        payload: DetailPageJobCreatePayload,
        page: DetailPagePlanPage,
    ) -> str:
        if page.page_role == "hero_opening":
            return "主包装居中稳定，卖点控制在短标签层级。"
        if page.page_role == "dry_leaf_evidence":
            return "以干茶近景建立真实感，不退化成包装陈列页。"
        if page.page_role == "tea_soup_evidence":
            return "茶汤页只讲汤色与饮用氛围，缺素材时可补足真实茶汤。"
        if page.page_role == "parameter_and_closing":
            return "只保留输入里明确存在的信息，参数用短字段卡片表达。"
        if page.page_role == "leaf_bottom_process_evidence":
            return "以叶底与工艺感建立可信度，不重复首屏构图。"
        if page.page_role == "brand_trust":
            return "品牌页只做可信表达，不虚构产地、证书或奖项。"
        if page.page_role == "gift_openbox_portable":
            return "补充礼赠与开盒价值，但仍以真实包装结构为核心。"
        if page.page_role == "scene_value_story":
            return "场景可由模型补足，但包装文字和轮廓必须保持稳定。"
        if page.page_role == "brewing_method_info":
            return payload.brew_suggestion.strip() or "未提供冲泡建议时，仅保留简明信息结构。"
        if page.page_role == "packaging_structure_value":
            return "用包装结构与材质近景补充价值，不改变原包装。"
        if page.page_role == "package_closeup_evidence":
            return "近景强调局部质感与标签细节，不重复首屏大构图。"
        if page.page_role == "brand_closing":
            return "收尾页保持整套风格统一，用克制 CTA 完成收束。"
        return payload.style_notes.strip() or "保持中文清晰、短标题和单主视觉。"

    def _resolve_parameter_copy(
        self,
        payload: DetailPageJobCreatePayload,
        page: DetailPagePlanPage,
    ) -> str:
        if page.page_role not in {"parameter_and_closing", "brewing_method_info"}:
            return ""
        cards: list[str] = []
        if payload.product_name.strip():
            cards.append(f"品名·{self._trim(payload.product_name, 12)}")
        if payload.tea_type.strip():
            cards.append(f"茶类·{self._trim(payload.tea_type, 10)}")
        if payload.brand_name.strip():
            cards.append(f"品牌·{self._trim(payload.brand_name, 10)}")
        for key, value in payload.specs.items():
            clean_key = self._trim(str(key).replace(":", "").strip(), 8)
            clean_value = self._trim(str(value).replace(":", "").strip(), 12)
            if not clean_key or not clean_value:
                continue
            cards.append(f"{clean_key}·{clean_value}")
            if len(cards) >= 4:
                break
        if page.page_role == "brewing_method_info" and payload.brew_suggestion.strip():
            cards.append(f"冲泡·{self._trim(payload.brew_suggestion, 14)}")
        return " / ".join(cards[:4])

    def _resolve_cta(self, page: DetailPagePlanPage) -> str:
        if page.page_role in {"parameter_and_closing", "brand_closing"}:
            return "收藏加购"
        return ""

    def _resolve_notes(self, page: DetailPagePlanPage) -> str:
        if page.page_role in {"dry_leaf_evidence", "leaf_bottom_process_evidence"}:
            return "保持单主标题，形态证据优先，避免文本堆叠。"
        if page.page_role in {"parameter_and_closing", "brewing_method_info"}:
            return "参数用短字段卡片，不做长表格，不写占位值。"
        return "中文短标题，卖点数量控制在 2-3 个，整页保持单主题。"

    def _normalize_points(self, points: list[str]) -> list[str]:
        rows: list[str] = []
        for point in points:
            value = self._trim(point, self.selling_point_max)
            if value and value not in rows:
                rows.append(value)
        return rows[: self.selling_point_count]

    def _display_name(self, payload: DetailPageJobCreatePayload) -> str:
        raw = payload.product_name.strip() or payload.tea_type.strip() or "茶叶详情"
        return self._trim(raw.replace("·", "").replace("/", ""), self.headline_best_max)

    def _trim(self, text: str, max_length: int) -> str:
        value = str(text or "").strip()
        return value[:max_length]
