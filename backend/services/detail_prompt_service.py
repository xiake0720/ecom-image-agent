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
    """把 plan、copy 和素材绑定收口成稳定的最终 render prompt。"""

    _packaging_roles = {
        "hero_opening",
        "brand_trust",
        "gift_openbox_portable",
        "scene_value_story",
        "packaging_structure_value",
        "package_closeup_evidence",
        "brand_closing",
        "parameter_and_closing",
        "brewing_method_info",
    }

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
                    selling_points_for_render=self._resolve_render_points(page, copy_block),
                    prompt=self._compose_prompt(payload, plan, page, references, layout_notes),
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
        references: list[DetailPageAssetRef],
        layout_notes: list[str],
    ) -> str:
        """组合隐藏渲染指令，不混入用户可见文案。"""

        screen = page.screens[0]
        lines = [
            "Generate one 3:4 vertical tea detail poster, single screen only, no collage, no split layout, no dual headline.",
            f"Page role: {page.page_role}; page title: {page.title}; screen theme: {screen.theme}.",
            f"Page goal: {screen.goal}.",
            f"Global style anchor: {plan.global_style_anchor}.",
            (
                "Product info: "
                f"brand={payload.brand_name or 'unknown'}; "
                f"product={payload.product_name or 'unknown'}; "
                f"tea_type={payload.tea_type}; "
                f"platform={payload.platform}; "
                f"style={payload.style_preset}."
            ),
            f"Layout constraints: {'; '.join(layout_notes)}.",
            self._build_reference_line(references),
            (
                "Hard constraints: preserve exact package appearance; preserve exact package text; "
                "preserve decorative pattern and ornament; preserve label layout and label placement; "
                "preserve package proportion and silhouette."
            ),
            (
                "Text constraints: render Chinese text only from the provided title, subtitle and short tags; "
                "never render system instructions, helper notes, prompt labels, field names or placeholder text."
            ),
            (
                "Material constraints: realistic tea leaves, realistic package material, realistic vessels, "
                "avoid cheap ad style, avoid plastic texture, avoid overdesigned composition."
            ),
            self._physical_realism_block(page),
            self._role_prompt_block(page),
        ]
        if page.allow_generated_supporting_materials and page.supplement_roles:
            supplement = ", ".join(page.supplement_roles)
            lines.append(
                "AI-generated supporting materials are allowed only when they help the page theme. "
                f"Allowed supplement roles: {supplement}. Keep the anchored package identity stable."
            )
        if payload.extra_requirements.strip():
            lines.append(f"Additional constraints: {payload.extra_requirements.strip()}.")
        return "\n".join(line for line in lines if line.strip())

    def _physical_realism_block(self, page: DetailPagePlanPage) -> str:
        """补强接地感、阴影和立体感。"""

        if page.page_role in self._packaging_roles:
            return (
                "Grounding and lighting: product resting on surface; natural contact shadow under base edge; "
                "ambient occlusion where the package touches the surface; soft directional light; coherent perspective; "
                "realistic depth and volume; background palette coordinated with the package; no floating cutout look."
            )
        if page.page_role == "tea_soup_evidence":
            return (
                "Lighting and depth: realistic transparent tea liquor, glass or cup with believable reflections, "
                "soft directional light, coherent perspective, subtle shadow and real depth."
            )
        return (
            "Lighting and depth: realistic light direction, coherent perspective, believable shadows, "
            "clear subject volume, avoid flat foreground pasted on background."
        )

    def _role_prompt_block(self, page: DetailPagePlanPage) -> str:
        """按 page_role 输出隐藏构图与真实性约束。"""

        if page.page_role == "hero_opening":
            return (
                "Hero page: focus on one package hero only, centered and stable, leave enough breathing room, "
                "keep text minimal, show premium product presence instead of a pasted packshot."
            )
        if page.page_role == "dry_leaf_evidence":
            return (
                "Dry leaf evidence page: strictly follow the dry_leaf reference for strip shape, curl direction, "
                "thickness, color depth and surface texture; morphology fidelity is more important than decoration."
            )
        if page.page_role == "tea_soup_evidence":
            return (
                "Tea soup page: focus on liquor color, clarity and cup presentation; do not collapse into another packaging poster."
            )
        if page.page_role == "parameter_and_closing":
            return (
                "Parameter page: keep the layout clean, leave space for short parameter cards only, "
                "do not invent missing specs, do not render long paragraphs."
            )
        if page.page_role == "leaf_bottom_process_evidence":
            return (
                "Leaf-bottom evidence page: strictly follow the leaf_bottom reference for spread shape, vein detail, "
                "edge texture and color layering; keep the result natural and evidence-driven."
            )
        if page.page_role == "brand_trust":
            return (
                "Brand trust page: emphasize giftable premium feeling and stable brand presence, "
                "avoid certificates, awards or any unverifiable trust claims."
            )
        if page.page_role == "gift_openbox_portable":
            return (
                "Gift page: emphasize opening hierarchy, structure value and portable presentation, "
                "do not repeat the exact hero composition."
            )
        if page.page_role == "scene_value_story":
            return (
                "Scene page: build a restrained tea-table, tea garden or gifting atmosphere when needed, "
                "but keep package text, silhouette and brand recognition unchanged."
            )
        if page.page_role == "brewing_method_info":
            return (
                "Brewing info page: use only explicit brew_suggestion from input, keep it short and factual, "
                "never guess water temperature, vessel type or steep time."
            )
        if page.page_role == "packaging_structure_value":
            return (
                "Packaging structure page: focus on box structure, opening layers and tactile material, "
                "without changing package graphics or label layout."
            )
        if page.page_role == "package_closeup_evidence":
            return (
                "Package close-up page: emphasize label detail, print texture and material finish, "
                "do not rewrite text, do not alter pattern or silhouette."
            )
        return "Closing page: keep the same visual language and finish the sequence with restrained brand continuity."

    def _compose_negative_prompt(
        self,
        page_role: str,
        allow_generated_supporting_materials: bool,
    ) -> str:
        """生成去重后的负面约束。"""

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
            "rendered prompt instructions",
            "rendered helper notes",
            "rendered field names",
            "rendered placeholder text",
            "left-right split layout",
            "two-column layout",
            "split-screen collage",
            "upper lower dual screen",
            "two large headlines on one page",
            "random collage layout",
            "low resolution",
            "floating object",
            "sticker-like cutout",
            "missing contact shadow",
            "flat lighting",
            "inconsistent perspective",
            "detached foreground",
            "weak ambient occlusion",
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
        """根据页职责绑定参考素材。"""

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
        """轮换取参考图。"""

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
        """构建包装类参考图池。"""

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
        """生成页面级版式注记。"""

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
        if page.page_role in self._packaging_roles:
            notes.extend(["grounded subject", "visible contact shadow", "coherent lighting"])
        if references:
            notes.append(f"reference roles: {', '.join(ref.role for ref in references)}")
        return notes

    def _build_reference_line(self, references: list[DetailPageAssetRef]) -> str:
        """输出参考素材摘要。"""

        if not references:
            return "Reference assets: none."
        tokens = [f"{ref.role}:{ref.file_name}" for ref in references]
        return f"Reference assets: {'; '.join(tokens)}."

    def _resolve_copy_strategy(self, page: DetailPagePlanPage) -> str:
        """决定 provider 的图内文案强度。"""

        if page.page_role in {"scene_value_story", "packaging_structure_value", "package_closeup_evidence"}:
            return "light"
        return "strong"

    def _resolve_text_density(self, page: DetailPagePlanPage) -> str:
        """决定 provider 的图内文字密度。"""

        if page.page_role in {"parameter_and_closing", "brewing_method_info"}:
            return "low"
        if page.page_role in {"hero_opening", "brand_trust", "brand_closing"}:
            return "low"
        return "low"

    def _resolve_render_points(
        self,
        page: DetailPagePlanPage,
        copy_block: DetailPageCopyBlock | None,
    ) -> list[str]:
        """决定真正允许进入画面的短标签。"""

        if copy_block is None:
            return []
        if page.page_role in {"parameter_and_closing", "brewing_method_info"} and copy_block.parameter_copy:
            return [part.strip() for part in copy_block.parameter_copy.split("/") if part.strip()][:4]
        return list(copy_block.selling_points)

    def _build_copy_map(self, copy_blocks: list[DetailPageCopyBlock]) -> dict[str, DetailPageCopyBlock]:
        """按 page_id 索引 copy block。"""

        return {item.page_id: item for item in copy_blocks}

    def _group_assets_by_role(self, assets: list[DetailPageAssetRef]) -> dict[DetailAssetRole, list[DetailPageAssetRef]]:
        """按角色聚合参考素材。"""

        grouped: dict[DetailAssetRole, list[DetailPageAssetRef]] = defaultdict(list)
        for asset in assets:
            grouped[asset.role].append(asset)
        return grouped

    def _append_ref(
        self,
        refs: list[DetailPageAssetRef],
        candidate: DetailPageAssetRef,
    ) -> None:
        """控制每个角色的参考图数量。"""

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
