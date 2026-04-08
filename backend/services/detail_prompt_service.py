"""详情图最终渲染 prompt 服务。"""

from __future__ import annotations

from collections import defaultdict

from backend.schemas.detail import (
    DetailAssetRole,
    DetailPageAssetRef,
    DetailPageCopyBlock,
    DetailPageJobCreatePayload,
    DetailPagePlanPage,
    DetailPagePlanPayload,
    DetailPagePromptPlanItem,
)


class DetailPromptService:
    """把 plan、copy 和素材绑定收口成稳定的最终 prompt。"""

    def build_prompt_plan(
        self,
        payload: DetailPageJobCreatePayload,
        plan: DetailPagePlanPayload,
        copy_blocks: list[DetailPageCopyBlock],
        assets: list[DetailPageAssetRef],
        *,
        planning_provider: object | None = None,
    ) -> list[DetailPagePromptPlanItem]:
        """输出每张 3:4 单屏详情图的最终 render prompt。"""

        del planning_provider
        copy_map = self._build_copy_map(copy_blocks)
        assets_by_role = self._group_assets_by_role(assets)
        role_indices: dict[DetailAssetRole, int] = defaultdict(int)
        packaging_pool = self._build_packaging_pool(payload, assets_by_role)
        prompt_rows: list[DetailPagePromptPlanItem] = []
        for page in plan.pages:
            copy_block = copy_map.get(page.page_id)
            references = self._resolve_references(page, assets_by_role, role_indices, packaging_pool)
            layout_notes = self._build_layout_notes(page, references)
            prompt_rows.append(
                DetailPagePromptPlanItem(
                    page_id=page.page_id,
                    page_title=page.title,
                    page_role=page.page_role,
                    layout_mode=page.layout_mode,
                    primary_headline_screen_id=page.primary_headline_screen_id,
                    global_style_anchor=plan.global_style_anchor,
                    screen_themes=[screen.theme for screen in page.screens],
                    layout_notes=layout_notes,
                    title_copy=copy_block.headline if copy_block is not None else "",
                    subtitle_copy=copy_block.subheadline if copy_block is not None else "",
                    selling_points_for_render=list(copy_block.selling_points if copy_block is not None else []),
                    prompt=self._compose_prompt(payload, plan, page, copy_block, references, layout_notes),
                    negative_prompt=self._compose_negative_prompt(page.page_role, page.allow_generated_supporting_materials),
                    references=references,
                    asset_strategy=page.asset_strategy,
                    allow_generated_supporting_materials=page.allow_generated_supporting_materials,
                    copy_strategy=self._resolve_copy_strategy(page),
                    text_density=self._resolve_text_density(page),
                    should_render_text=True,
                    retryable=True,
                )
            )
        return prompt_rows

    def _compose_prompt(
        self,
        payload: DetailPageJobCreatePayload,
        plan: DetailPagePlanPayload,
        page: DetailPagePlanPage,
        copy_block: DetailPageCopyBlock | None,
        references: list[DetailPageAssetRef],
        layout_notes: list[str],
    ) -> str:
        screen = page.screens[0]
        lines = [
            "生成 1 张 3:4 单屏竖版茶叶详情图海报，不做拼贴，不做左右分栏，不做双标题。",
            f"页面角色：{page.page_role}；页面标题：{page.title}；主题：{screen.theme}。",
            f"页面目标：{screen.goal}",
            f"全局风格：{plan.global_style_anchor}",
            f"商品信息：品牌={payload.brand_name or '未提供'}；商品={payload.product_name or '未提供'}；茶类={payload.tea_type}；平台={payload.platform}；风格={payload.style_preset}。",
            f"版式要求：{'；'.join(layout_notes)}",
            self._build_reference_line(references),
            "硬性约束：preserve exact package appearance; preserve exact package text; preserve decorative pattern and ornament; preserve label layout and label placement; preserve package proportion and silhouette.",
            "中文约束：所有中文需清晰可读，避免乱码，避免长段堆字，整页只保留一个主要标题层级。",
            "画面约束：真实茶叶质感，真实包装，真实器物，不做廉价广告风，不做塑料感材质。",
            self._role_prompt_block(page),
        ]
        if page.allow_generated_supporting_materials and page.supplement_roles:
            supplement = "、".join(page.supplement_roles)
            lines.append(f"允许在保持锚点稳定的前提下补足辅助素材：{supplement}。辅助素材只能服务页面主题，不能抢主视觉。")
        if copy_block is not None:
            lines.extend(self._copy_lines(copy_block))
        if payload.extra_requirements.strip():
            lines.append(f"额外要求：{payload.extra_requirements.strip()}")
        return "\n".join(line for line in lines if line.strip())

    def _copy_lines(self, copy_block: DetailPageCopyBlock) -> list[str]:
        lines = [f"主标题：{copy_block.headline}"]
        if copy_block.subheadline:
            lines.append(f"副标题：{copy_block.subheadline}")
        if copy_block.selling_points:
            lines.append(f"卖点标签：{' / '.join(copy_block.selling_points)}")
        if copy_block.parameter_copy:
            lines.append(f"参数卡：{copy_block.parameter_copy}")
        if copy_block.body_copy:
            lines.append(f"辅助说明：{copy_block.body_copy}")
        if copy_block.cta_copy:
            lines.append(f"CTA：{copy_block.cta_copy}")
        return lines

    def _role_prompt_block(self, page: DetailPagePlanPage) -> str:
        if page.page_role == "hero_opening":
            return "首屏只讲包装主体与品牌识别，主体居中稳定，卖点标签数量控制在 2-3 个，不要左右双主体。"
        if page.page_role == "dry_leaf_evidence":
            return "必须严格参考 dry_leaf 的条索形态、粗细、卷曲走向、颜色深浅和表面纹理，不能生成成别的茶类条索。"
        if page.page_role == "tea_soup_evidence":
            return "茶汤页只讲汤色、透亮度与杯中观感，不要退化成包装陈列海报。"
        if page.page_role == "parameter_and_closing":
            return "参数页必须以短字段卡片为主，缺失的克重、产地、保质期等信息直接省略，不要猜测。"
        if page.page_role == "leaf_bottom_process_evidence":
            return "必须严格参考 leaf_bottom 的叶片舒展状态、颜色层次、叶脉与边缘细节，不能生成成别的茶类叶底。"
        if page.page_role == "brand_trust":
            return "品牌页只表达可信感和礼赠质感，不虚构产地、奖项、证书或企业背书。"
        if page.page_role == "gift_openbox_portable":
            return "礼赠页强调开盒层次和结构价值，不重复首屏大包装海报。"
        if page.page_role == "scene_value_story":
            return "场景页可以补足茶席、茶园或礼赠氛围，但包装文字、轮廓和品牌识别必须保持稳定。"
        if page.page_role == "brewing_method_info":
            return "冲泡页只能使用输入中明确提供的 brew_suggestion，不要猜测水温、器具或出汤时长。"
        if page.page_role == "packaging_structure_value":
            return "包装结构页强调盒型、材质和层次，不可修改包装花纹、标签布局与比例。"
        if page.page_role == "package_closeup_evidence":
            return "包装近景页强调标签和材质细节，不可改字、改纹理、改轮廓。"
        return "收尾页保持同一风格体系，用克制信息完成整套详情图收束。"

    def _compose_negative_prompt(
        self,
        page_role: str,
        allow_generated_supporting_materials: bool,
    ) -> str:
        parts = [
            "package deformation",
            "changed package text",
            "changed decorative pattern",
            "changed label layout",
            "changed package proportion",
            "label drift",
            "brand drift",
            "garbled Chinese",
            "dense text blocks",
            "left-right split layout",
            "two-column layout",
            "split-screen collage",
            "upper lower dual screen",
            "two large headlines on one page",
            "random collage layout",
            "low resolution",
        ]
        if page_role == "dry_leaf_evidence":
            parts.extend(["different tea cultivar morphology", "wrong strip shape", "wrong tea leaf color", "wrong leaf texture"])
        if page_role == "leaf_bottom_process_evidence":
            parts.extend(["wrong leaf-bottom shape", "different tea cultivar morphology", "wrong tea leaf color", "wrong leaf texture"])
        if page_role == "tea_soup_evidence":
            parts.extend(["package hero poster", "opaque tea soup", "muddy tea liquor"])
        if not allow_generated_supporting_materials:
            parts.append("invented background story")
        return ", ".join(dict.fromkeys(parts))

    def _resolve_references(
        self,
        page: DetailPagePlanPage,
        assets_by_role: dict[DetailAssetRole, list[DetailPageAssetRef]],
        role_indices: dict[DetailAssetRole, int],
        packaging_pool: list[DetailPageAssetRef],
    ) -> list[DetailPageAssetRef]:
        refs: list[DetailPageAssetRef] = []
        for role in page.anchor_roles:
            ref = self._next_asset(role, assets_by_role, role_indices)
            if ref is not None:
                self._append_ref(refs, ref)
        for role in page.supplement_roles:
            if role in {"tea_soup", "scene_ref", "bg_ref"}:
                ref = self._next_asset(role, assets_by_role, role_indices)
                if ref is not None:
                    self._append_ref(refs, ref)
        if packaging_pool:
            packaging_ref = packaging_pool[role_indices["packaging"] % len(packaging_pool)]
            role_indices["packaging"] += 1
            self._append_ref(refs, packaging_ref)
        for screen in page.screens:
            for role in screen.suggested_asset_roles:
                ref = self._next_asset(role, assets_by_role, role_indices)
                if ref is not None:
                    self._append_ref(refs, ref)
        return refs[:5]

    def _next_asset(
        self,
        role: DetailAssetRole,
        assets_by_role: dict[DetailAssetRole, list[DetailPageAssetRef]],
        role_indices: dict[DetailAssetRole, int],
    ) -> DetailPageAssetRef | None:
        rows = assets_by_role.get(role, [])
        if not rows:
            return None
        index = role_indices[role] % len(rows)
        role_indices[role] += 1
        return rows[index]

    def _build_packaging_pool(
        self,
        payload: DetailPageJobCreatePayload,
        assets_by_role: dict[DetailAssetRole, list[DetailPageAssetRef]],
    ) -> list[DetailPageAssetRef]:
        pool: list[DetailPageAssetRef] = []
        if payload.prefer_main_result_first:
            pool.extend(assets_by_role.get("main_result", []))
            pool.extend(assets_by_role.get("packaging", []))
        else:
            pool.extend(assets_by_role.get("packaging", []))
            pool.extend(assets_by_role.get("main_result", []))
        return pool

    def _build_layout_notes(
        self,
        page: DetailPagePlanPage,
        references: list[DetailPageAssetRef],
    ) -> list[str]:
        notes = [
            "single screen vertical poster",
            "one visual theme only",
            "one primary display headline",
            "no split layout",
            "no collage layout",
            "3:4 vertical canvas",
        ]
        if page.page_role in {"dry_leaf_evidence", "leaf_bottom_process_evidence"}:
            notes.append("morphology fidelity over decoration")
        if references:
            notes.append(f"reference roles: {', '.join(ref.role for ref in references)}")
        return notes

    def _build_reference_line(self, references: list[DetailPageAssetRef]) -> str:
        if not references:
            return "参考素材：无。"
        tokens = [f"{ref.role}:{ref.file_name}" for ref in references]
        return f"参考素材：{'；'.join(tokens)}"

    def _resolve_copy_strategy(self, page: DetailPagePlanPage) -> str:
        if page.page_role in {"scene_value_story", "packaging_structure_value", "package_closeup_evidence"}:
            return "light"
        return "strong"

    def _resolve_text_density(self, page: DetailPagePlanPage) -> str:
        if page.page_role in {"parameter_and_closing", "brewing_method_info"}:
            return "low"
        if page.page_role in {"hero_opening", "brand_trust", "brand_closing"}:
            return "low"
        return "low"

    def _build_copy_map(self, copy_blocks: list[DetailPageCopyBlock]) -> dict[str, DetailPageCopyBlock]:
        return {item.page_id: item for item in copy_blocks}

    def _group_assets_by_role(self, assets: list[DetailPageAssetRef]) -> dict[DetailAssetRole, list[DetailPageAssetRef]]:
        grouped: dict[DetailAssetRole, list[DetailPageAssetRef]] = defaultdict(list)
        for asset in assets:
            grouped[asset.role].append(asset)
        return grouped

    def _append_ref(
        self,
        refs: list[DetailPageAssetRef],
        candidate: DetailPageAssetRef,
    ) -> None:
        if candidate in refs:
            return
        max_per_role = {
            "packaging": 2,
            "main_result": 1,
            "dry_leaf": 1,
            "tea_soup": 1,
            "leaf_bottom": 1,
            "scene_ref": 1,
            "bg_ref": 1,
        }
        current_count = sum(1 for item in refs if item.role == candidate.role)
        if current_count >= max_per_role.get(candidate.role, 1):
            return
        refs.append(candidate)
