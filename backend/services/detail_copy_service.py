"""详情图文案生成服务。"""

from __future__ import annotations

from backend.schemas.detail import (
    DetailPageCopyBlock,
    DetailPageJobCreatePayload,
    DetailPagePlanPage,
    DetailPagePlanPayload,
)


class DetailCopyService:
    """按页职责生成稳定、可见、可消费的中文短文案。"""

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
        """构建单页文案块。"""

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
        """按 page_role 生成主副标题。"""

        display_name = self._display_name(payload)
        if page.page_role == "hero_opening":
            subheadline = payload.brand_name or payload.tea_type
            return self._trim(display_name, self.headline_best_max), self._trim(subheadline, self.subheadline_best_max)
        if page.page_role == "dry_leaf_evidence":
            return "茶干条索", "看清干茶层次"
        if page.page_role == "tea_soup_evidence":
            return "茶汤透亮", "杯中观感更直观"
        if page.page_role == "parameter_and_closing":
            return "参数清晰", "关键信息一屏看完"
        if page.page_role == "leaf_bottom_process_evidence":
            return "叶底可见", "舒展层次更直观"
        if page.page_role == "brand_trust":
            return "礼盒质感", "品牌表达更稳重"
        if page.page_role == "gift_openbox_portable":
            return "开盒层次", "礼赠与收纳兼顾"
        if page.page_role == "scene_value_story":
            return "茶席氛围", "饮用场景更有代入"
        if page.page_role == "brewing_method_info":
            return "冲泡建议", "已知信息简明呈现"
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
        """生成图内可见的短标签。"""

        base_points = [self._trim(point, self.selling_point_max) for point in payload.selling_points if point.strip()]
        if page.page_role == "hero_opening":
            points = base_points[:3] or [payload.tea_type[:4] or "茶叶", "包装稳定", "质感呈现"]
            return self._normalize_points(points)
        if page.page_role == "dry_leaf_evidence":
            return self._normalize_points(["条索清晰", "色泽自然", "纹理可见"])
        if page.page_role == "tea_soup_evidence":
            return self._normalize_points(["汤色透亮", "杯中清亮", "入口观感"])
        if page.page_role == "parameter_and_closing":
            return []
        if page.page_role == "leaf_bottom_process_evidence":
            return self._normalize_points(["舒展可见", "层次自然", "细节真实"])
        if page.page_role == "brand_trust":
            return self._normalize_points(["礼盒体面", "陈列稳重", "送礼友好"])
        if page.page_role == "gift_openbox_portable":
            return self._normalize_points(["开盒顺手", "礼赠友好", "收纳整齐"])
        if page.page_role == "scene_value_story":
            return self._normalize_points(["茶席氛围", "场景自然", "静享片刻"])
        if page.page_role == "brewing_method_info":
            return self._normalize_points(["冲泡简明", "信息清楚", "上手轻松"])
        if page.page_role in {"packaging_structure_value", "package_closeup_evidence"}:
            return self._normalize_points(["结构稳定", "材质可感", "近景清楚"])
        return self._normalize_points(base_points[:3] or ["风格统一", "信息清晰"])

    def _resolve_body_copy(
        self,
        payload: DetailPageJobCreatePayload,
        page: DetailPagePlanPage,
    ) -> str:
        """生成非规则句的用户可见短说明。"""

        if page.page_role == "hero_opening":
            return "主包装居中稳定，卖点控制在短标签层级。"
        if page.page_role == "dry_leaf_evidence":
            return "条索紧结乌润，干茶状态一眼可辨。"
        if page.page_role == "tea_soup_evidence":
            return "杯中汤色透亮，观感干净利落。"
        if page.page_role == "parameter_and_closing":
            return ""
        if page.page_role == "leaf_bottom_process_evidence":
            return "叶底舒展自然，层次与活性更直观。"
        if page.page_role == "brand_trust":
            return "礼盒陈列稳重，自饮送礼都更得体。"
        if page.page_role == "gift_openbox_portable":
            return "开盒层次清晰，拿取与收纳更顺手。"
        if page.page_role == "scene_value_story":
            return "适合茶席、小聚与静享时刻。"
        if page.page_role == "brewing_method_info":
            suggestion = payload.brew_suggestion.strip()
            return self._trim(suggestion, 24) if suggestion else "冲泡信息简洁清楚。"
        if page.page_role == "packaging_structure_value":
            return "盒型与材质细节更清楚，触感更有层次。"
        if page.page_role == "package_closeup_evidence":
            return "局部近景更能看清标签与材质细节。"
        if page.page_role == "brand_closing":
            return "整套风格收束干净，品牌记忆点更集中。"
        return payload.style_notes.strip() or "保持中文清晰、短标题和单主视觉。"

    def _resolve_parameter_copy(
        self,
        payload: DetailPageJobCreatePayload,
        page: DetailPagePlanPage,
    ) -> str:
        """将真实商品信息整理为短字段卡片。"""

        if page.page_role not in {"parameter_and_closing", "brewing_method_info"}:
            return ""
        cards: list[str] = []
        if payload.product_name.strip():
            cards.append(f"品名·{self._trim(payload.product_name, 12)}")
        if payload.tea_type.strip():
            cards.append(f"茶类·{self._trim(payload.tea_type, 10)}")
        if payload.brand_name.strip():
            cards.append(f"品牌·{self._trim(payload.brand_name, 10)}")
        for key, value in self._normalized_spec_items(payload.specs):
            cards.append(f"{key}·{value}")
            if len(cards) >= 4:
                break
        if page.page_role == "brewing_method_info" and payload.brew_suggestion.strip():
            cards.append(f"冲泡·{self._trim(payload.brew_suggestion, 14)}")
        return " / ".join(cards[:4])

    def _resolve_cta(self, page: DetailPagePlanPage) -> str:
        """按页职责生成 CTA。"""

        if page.page_role in {"parameter_and_closing", "brand_closing"}:
            return "收藏加购"
        return ""

    def _resolve_notes(self, page: DetailPagePlanPage) -> str:
        """输出仅供预览的内部备注。"""

        if page.page_role in {"dry_leaf_evidence", "leaf_bottom_process_evidence"}:
            return "保持单主标题，形态证据优先，避免文本堆叠。"
        if page.page_role in {"parameter_and_closing", "brewing_method_info"}:
            return "参数用短字段卡片，不做长表格，不写占位值。"
        return "中文短标题，卖点数量控制在 2-3 个，整页保持单主题。"

    def _normalized_spec_items(self, specs: dict[str, str]) -> list[tuple[str, str]]:
        """把 specs 的英文 key 规整成中文参数字段。"""

        key_map = {
            "net_content": "净含量",
            "origin": "产地",
            "ingredients": "配料",
            "shelf_life": "保质期",
            "storage": "储存方式",
        }
        rows: list[tuple[str, str]] = []
        for raw_key, raw_value in specs.items():
            key = str(raw_key).strip()
            value = str(raw_value).strip()
            if not value:
                continue
            display_key = key_map.get(key, self._trim(key.replace("_", ""), 8))
            if display_key == "保质期" and value.isdigit():
                continue
            rows.append((display_key, self._trim(value, 12)))
        return rows

    def _normalize_points(self, points: list[str]) -> list[str]:
        """去重并压缩卖点短标签。"""

        rows: list[str] = []
        for point in points:
            value = self._trim(point, self.selling_point_max)
            if value and value not in rows:
                rows.append(value)
        return rows[: self.selling_point_count]

    def _display_name(self, payload: DetailPageJobCreatePayload) -> str:
        """生成首屏展示名。"""

        raw = payload.product_name.strip() or payload.tea_type.strip() or "茶叶详情"
        return self._trim(raw.replace("·", "").replace("/", ""), self.headline_best_max)

    def _trim(self, text: str, max_length: int) -> str:
        """截断字符串。"""

        value = str(text or "").strip()
        return value[:max_length]
