"""详情图规划服务。"""

from __future__ import annotations

import json
from pathlib import Path

from backend.schemas.detail import (
    DetailAssetRole,
    DetailDirectorBrief,
    DetailPageAssetRef,
    DetailPageJobCreatePayload,
    DetailPagePlanPage,
    DetailPagePlanPayload,
    DetailPagePlanScreen,
    DetailPageRole,
    DetailPreflightReport,
    DetailPreflightRoleSummary,
)


class DetailPlannerService:
    """负责生成稳定的 V2 详情图规划。

    这里优先走模板化规划，而不是把页职责完全交给模型自由发挥。
    原因是详情页链路的主要问题并不是“缺少创意”，而是页职责漂移、
    素材绑定错误和计划与最终渲染不可执行。
    """

    screens_per_page = 1
    core_anchor_roles: tuple[DetailAssetRole, ...] = ("main_result", "packaging")
    evidence_anchor_roles: tuple[DetailAssetRole, ...] = ("dry_leaf", "leaf_bottom")
    ai_supplement_roles: tuple[DetailAssetRole, ...] = ("tea_soup", "scene_ref", "bg_ref")
    optional_role_candidates: tuple[DetailPageRole, ...] = (
        "brand_trust",
        "gift_openbox_portable",
        "scene_value_story",
        "brewing_method_info",
        "packaging_structure_value",
        "package_closeup_evidence",
        "brand_closing",
    )

    def __init__(self, template_root: Path) -> None:
        self.template_root = template_root

    def build_preflight_report(
        self,
        payload: DetailPageJobCreatePayload,
        assets: list[DetailPageAssetRef],
    ) -> DetailPreflightReport:
        """根据已上传素材生成预检报告。"""

        role_map = self._group_assets_by_role(assets)
        available_roles = [role for role in role_map if role_map[role]]
        warnings: list[str] = []
        notes: list[str] = []
        missing_required_roles: list[DetailAssetRole] = []
        if not any(role_map.get(role) for role in self.core_anchor_roles):
            missing_required_roles.append("packaging")
            warnings.append("缺少 packaging 或 main_result，无法稳定生成详情页主锚点。")
        missing_optional_roles = [
            role for role in (*self.evidence_anchor_roles, *self.ai_supplement_roles) if not role_map.get(role)
        ]
        if not role_map.get("dry_leaf"):
            warnings.append("缺少 dry_leaf，规划中不会生成干茶证据页。")
        if not role_map.get("leaf_bottom"):
            warnings.append("缺少 leaf_bottom，规划中不会生成叶底证据页。")
        if not role_map.get("tea_soup"):
            notes.append("缺少 tea_soup 时允许模型在茶汤页内补足真实茶汤。")
        if not role_map.get("scene_ref"):
            notes.append("缺少 scene_ref 时允许模型补足茶席、茶园或礼赠氛围。")
        if not role_map.get("bg_ref"):
            notes.append("缺少 bg_ref 时允许模型生成克制背景，但不能改动包装。")
        if payload.brew_suggestion.strip():
            notes.append("冲泡页仅使用用户明确提供的冲泡建议。")
        else:
            notes.append("未提供 brew_suggestion 时，冲泡页仅做结构化信息表达，不补猜水温与时长。")
        report = DetailPreflightReport(
            passed=not missing_required_roles,
            warnings=warnings,
            available_roles=available_roles,
            missing_required_roles=missing_required_roles,
            missing_optional_roles=missing_optional_roles,
            asset_summary=[
                DetailPreflightRoleSummary(
                    role=role,
                    count=len(rows),
                    file_names=[item.file_name for item in rows],
                )
                for role, rows in role_map.items()
                if rows
            ],
            recommended_page_roles=self._select_page_roles(payload.target_slice_count, role_map),
            notes=notes,
        )
        return report

    def build_director_brief(
        self,
        payload: DetailPageJobCreatePayload,
        assets: list[DetailPageAssetRef],
        *,
        preflight_report: DetailPreflightReport | None = None,
    ) -> DetailDirectorBrief:
        """构建供 planner/copy/prompt 共用的导演简报。"""

        template = self._load_template()
        role_map = self._group_assets_by_role(assets)
        preflight = preflight_report or self.build_preflight_report(payload, assets)
        anchor_priority = self._resolve_anchor_priority(payload, role_map)
        selected_roles = self._select_page_roles(payload.target_slice_count, role_map)
        required_page_roles = [role for role in selected_roles if role in {"hero_opening", "tea_soup_evidence", "parameter_and_closing"}]
        optional_page_roles = [role for role in selected_roles if role not in required_page_roles]
        ai_supplement_page_roles = [
            role
            for role in selected_roles
            if template["page_blueprints"][role]["allow_generated_supporting_materials"]
        ]
        material_notes = list(preflight.notes)
        if role_map.get("main_result") and payload.prefer_main_result_first:
            material_notes.append("首屏优先绑定 main_result，其余页优先轮换 packaging。")
        elif role_map.get("packaging"):
            material_notes.append("主锚点以 packaging 为主，必要时局部引入 main_result。")
        constraints = [
            "每页固定为 3:4 单屏竖版海报，不做左右分栏和拼贴。",
            "hero、dry_leaf、leaf_bottom 页面形态忠实优先于装饰构图。",
            "参数、冲泡、品牌页只允许使用输入中明确存在的信息。",
            "tea_soup / scene / bg 缺失时允许 AI 补足，但包装文字、花纹和轮廓不得变化。",
        ]
        planning_notes = [
            f"目标页数固定为 {payload.target_slice_count}，按页职责顺序补齐。",
            "缺少 dry_leaf 或 leaf_bottom 时，改用品牌/场景/结构页填充，不伪造证据页。",
            "文案保持短标题与低文本密度，避免大段说明。",
        ]
        return DetailDirectorBrief(
            template_name=str(template["template_name"]),
            category=payload.category,
            platform=payload.platform,
            style_preset=payload.style_preset,
            global_style_anchor=str(template["global_style_anchor"]),
            page_rhythm=list(template["page_rhythm"]),
            anchor_priority=anchor_priority,
            required_page_roles=required_page_roles,
            optional_page_roles=optional_page_roles,
            ai_supplement_page_roles=ai_supplement_page_roles,
            planning_notes=planning_notes,
            material_notes=material_notes,
            constraints=constraints,
        )

    def build_plan(
        self,
        payload: DetailPageJobCreatePayload,
        assets: list[DetailPageAssetRef],
        *,
        preflight_report: DetailPreflightReport | None = None,
        director_brief: DetailDirectorBrief | None = None,
        planning_provider: object | None = None,
    ) -> DetailPagePlanPayload:
        """生成整套 3:4 单屏详情图规划。"""

        del planning_provider
        template = self._load_template()
        role_map = self._group_assets_by_role(assets)
        preflight = preflight_report or self.build_preflight_report(payload, assets)
        brief = director_brief or self.build_director_brief(payload, assets, preflight_report=preflight)
        selected_roles = preflight.recommended_page_roles or self._select_page_roles(payload.target_slice_count, role_map)
        pages: list[DetailPagePlanPage] = []
        for index, page_role in enumerate(selected_roles, start=1):
            blueprint = template["page_blueprints"][page_role]
            pages.append(self._build_page(index, page_role, blueprint, brief, role_map))
        return DetailPagePlanPayload(
            template_name=str(template["template_name"]),
            category=payload.category,
            platform=payload.platform,
            style_preset=payload.style_preset,
            canvas_aspect_ratio=str(template["canvas"]["aspect_ratio"]),
            screens_per_page=int(template["canvas"]["screens_per_page"]),
            layout_mode=str(template["canvas"]["layout_mode"]),
            global_style_anchor=brief.global_style_anchor,
            narrative=[page.title for page in pages],
            total_screens=len(pages),
            total_pages=len(pages),
            pages=pages,
        )

    def _build_page(
        self,
        page_index: int,
        page_role: DetailPageRole,
        blueprint: dict[str, object],
        brief: DetailDirectorBrief,
        role_map: dict[DetailAssetRole, list[DetailPageAssetRef]],
    ) -> DetailPagePlanPage:
        anchor_roles = self._filter_existing_roles(self._cast_roles(blueprint.get("anchor_roles", [])), role_map)
        preferred_roles = self._filter_existing_roles(self._cast_roles(blueprint.get("preferred_roles", [])), role_map)
        supplement_roles = self._cast_roles(blueprint.get("supplement_roles", []))
        asset_strategy = str(blueprint.get("asset_strategy", "reference_preferred"))
        allow_generated_supporting_materials = bool(blueprint.get("allow_generated_supporting_materials", False))
        material_focus = str(blueprint.get("material_focus", ""))
        reference_roles = anchor_roles or preferred_roles or self._fallback_reference_roles(brief.anchor_priority, role_map)
        screen_id = f"p{page_index:02d}s1"
        screen = DetailPagePlanScreen(
            screen_id=screen_id,
            theme=str(blueprint.get("screen_theme", blueprint.get("title", ""))),
            goal=str(blueprint.get("screen_goal", "")),
            screen_type=str(blueprint.get("screen_type", "visual")),
            suggested_asset_roles=reference_roles[:3] or self._fallback_reference_roles(brief.anchor_priority, role_map)[:1],
            asset_strategy=asset_strategy,  # type: ignore[arg-type]
            anchor_roles=anchor_roles,
            supplement_roles=supplement_roles,
            allow_generated_supporting_materials=allow_generated_supporting_materials,
            material_focus=material_focus,
            notes=self._build_screen_notes(page_role, anchor_roles, supplement_roles, allow_generated_supporting_materials),
        )
        return DetailPagePlanPage(
            page_id=f"page-{page_index:02d}",
            title=str(blueprint.get("title", page_role)),
            page_role=page_role,
            layout_mode="single_screen_vertical_poster",
            primary_headline_screen_id=screen_id,
            style_anchor=brief.global_style_anchor,
            narrative_position=page_index,
            asset_strategy=asset_strategy,  # type: ignore[arg-type]
            anchor_roles=anchor_roles,
            supplement_roles=supplement_roles,
            allow_generated_supporting_materials=allow_generated_supporting_materials,
            review_focus=[str(item) for item in blueprint.get("review_focus", [])],
            screens=[screen],
        )

    def _build_screen_notes(
        self,
        page_role: DetailPageRole,
        anchor_roles: list[DetailAssetRole],
        supplement_roles: list[DetailAssetRole],
        allow_generated_supporting_materials: bool,
    ) -> list[str]:
        notes = [
            "固定为 single_screen_vertical_poster。",
            "每页只允许一个主要标题层级。",
        ]
        if page_role in {"dry_leaf_evidence", "leaf_bottom_process_evidence"}:
            notes.append("形态忠实优先于装饰构图。")
        if anchor_roles:
            notes.append(f"优先锁定锚点素材：{', '.join(anchor_roles)}。")
        if allow_generated_supporting_materials and supplement_roles:
            notes.append(f"可补足辅助素材：{', '.join(supplement_roles)}。")
        return notes

    def _select_page_roles(
        self,
        target_count: int,
        role_map: dict[DetailAssetRole, list[DetailPageAssetRef]],
    ) -> list[DetailPageRole]:
        """按素材可用性选择页职责，不伪造证据页。"""

        template = self._load_template()
        default_sequence = [
            "hero_opening",
            "dry_leaf_evidence",
            "tea_soup_evidence",
            "parameter_and_closing",
            "leaf_bottom_process_evidence",
            "brand_trust",
            "gift_openbox_portable",
            "scene_value_story",
            "brewing_method_info",
            "packaging_structure_value",
            "package_closeup_evidence",
            "brand_closing",
        ]
        sequence = template.get("page_sequences", {}).get(str(target_count), default_sequence)
        selected: list[DetailPageRole] = []
        for candidate in sequence:
            role = str(candidate)
            if not self._role_is_allowed(role, role_map):
                continue
            selected.append(role)  # type: ignore[arg-type]
        for candidate in self.optional_role_candidates:
            if len(selected) >= target_count:
                break
            if candidate in selected:
                continue
            if self._role_is_allowed(candidate, role_map):
                selected.append(candidate)
        if len(selected) < target_count:
            for candidate in default_sequence:
                page_role = str(candidate)
                if page_role in selected:
                    continue
                selected.append(page_role)  # type: ignore[arg-type]
                if len(selected) >= target_count:
                    break
        return selected[:target_count]

    def _role_is_allowed(
        self,
        page_role: str | DetailPageRole,
        role_map: dict[DetailAssetRole, list[DetailPageAssetRef]],
    ) -> bool:
        if page_role == "dry_leaf_evidence":
            return bool(role_map.get("dry_leaf"))
        if page_role == "leaf_bottom_process_evidence":
            return bool(role_map.get("leaf_bottom"))
        if page_role == "hero_opening":
            return any(role_map.get(role) for role in self.core_anchor_roles)
        return True

    def _resolve_anchor_priority(
        self,
        payload: DetailPageJobCreatePayload,
        role_map: dict[DetailAssetRole, list[DetailPageAssetRef]],
    ) -> list[DetailAssetRole]:
        priority: list[DetailAssetRole] = []
        preferred = ["main_result", "packaging"] if payload.prefer_main_result_first else ["packaging", "main_result"]
        for role in preferred + ["dry_leaf", "leaf_bottom", "tea_soup", "scene_ref", "bg_ref"]:
            if role_map.get(role) and role not in priority:
                priority.append(role)  # type: ignore[arg-type]
        for role in self.core_anchor_roles:
            if role not in priority:
                priority.append(role)
        return priority

    def _fallback_reference_roles(
        self,
        anchor_priority: list[DetailAssetRole],
        role_map: dict[DetailAssetRole, list[DetailPageAssetRef]],
    ) -> list[DetailAssetRole]:
        return [role for role in anchor_priority if role_map.get(role)]

    def _group_assets_by_role(self, assets: list[DetailPageAssetRef]) -> dict[DetailAssetRole, list[DetailPageAssetRef]]:
        grouped: dict[DetailAssetRole, list[DetailPageAssetRef]] = {
            "main_result": [],
            "packaging": [],
            "dry_leaf": [],
            "tea_soup": [],
            "leaf_bottom": [],
            "scene_ref": [],
            "bg_ref": [],
        }
        for asset in assets:
            grouped[asset.role].append(asset)
        return grouped

    def _filter_existing_roles(
        self,
        roles: list[DetailAssetRole],
        role_map: dict[DetailAssetRole, list[DetailPageAssetRef]],
    ) -> list[DetailAssetRole]:
        return [role for role in roles if role_map.get(role)]

    def _cast_roles(self, values: object) -> list[DetailAssetRole]:
        roles: list[DetailAssetRole] = []
        for item in values if isinstance(values, list) else []:
            roles.append(str(item))  # type: ignore[arg-type]
        return roles

    def _load_template(self) -> dict[str, object]:
        """读取茶叶详情图 V2 模板。"""

        template_path = self.template_root / "detail_pages" / "tea_tmall_premium_v2.json"
        return json.loads(template_path.read_text(encoding="utf-8"))
