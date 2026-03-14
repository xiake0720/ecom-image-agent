"""茶叶 Phase 1 固定模板规划工具。

文件位置：
- `src/services/planning/tea_shot_planner.py`

核心职责：
- 为茶叶类商品提供固定五图模板，但不再把所有茶叶强制视为礼盒。
- 根据 `ProductAnalysis` 中的包装结构、材质、包型关键词推断模板族。
- 输出仍然是兼容下游 copy/layout/prompt 节点的 `ShotSpec` 列表。

主要被谁调用：
- `src/workflows/nodes/plan_shots.py`
- `src/services/qc/task_qc.py`
- 对应的单元测试

关键输入/输出：
- 输入：`Task`、`ProductAnalysis`
- 输出：固定五图的 `ShotPlan` / `ShotSpec` 列表，以及用于 real 模式“只补细节”的上下文
"""

from __future__ import annotations

from src.domain.product_analysis import ProductAnalysis
from src.domain.shot_plan import ShotPlan, ShotSpec, TeaShotEnrichmentPlan
from src.domain.task import Task


TEA_GIFT_BOX_PHASE1_SHOTS: tuple[tuple[str, str], ...] = (
    ("shot_01", "hero_brand"),
    ("shot_02", "carry_action"),
    ("shot_03", "open_box_structure"),
    ("shot_04", "dry_leaf_detail"),
    ("shot_05", "tea_soup_experience"),
)

TEA_TIN_CAN_PHASE1_SHOTS: tuple[tuple[str, str], ...] = (
    ("shot_01", "hero_brand"),
    ("shot_02", "package_detail"),
    ("shot_03", "dry_leaf_detail"),
    ("shot_04", "tea_soup_experience"),
    ("shot_05", "lifestyle_or_brewing_context"),
)

TEA_POUCH_PHASE1_SHOTS: tuple[tuple[str, str], ...] = (
    ("shot_01", "hero_brand"),
    ("shot_02", "package_detail"),
    ("shot_03", "dry_leaf_detail"),
    ("shot_04", "tea_soup_experience"),
    ("shot_05", "lifestyle_or_brewing_context"),
)

# 兼容历史调用方：旧常量名继续保留，默认指向礼盒模板。
TEA_PHASE1_SHOTS: tuple[tuple[str, str], ...] = TEA_GIFT_BOX_PHASE1_SHOTS


def build_tea_shot_plan(task: Task, analysis: ProductAnalysis) -> ShotPlan:
    """构建茶叶类 Phase 1 固定五图规划结果。"""
    return ShotPlan(shots=build_tea_shot_slots(task, analysis))


def build_tea_shot_slots(task: Task, analysis: ProductAnalysis) -> list[ShotSpec]:
    """根据包装模板族返回固定五图模板。

    这里仍然忽略 `task.shot_count`，因为 Phase 1 的目标是先固定主链路的标准图位。
    变化点只在于：礼盒、金属罐、袋装不再共用同一套图位。
    """
    del task
    template_family = resolve_tea_package_template_family(analysis)
    if template_family == "tea_tin_can":
        return _build_tea_tin_can_slots(analysis)
    if template_family == "tea_pouch":
        return _build_tea_pouch_slots(analysis)
    return _build_tea_gift_box_slots(analysis)


def resolve_tea_package_template_family(analysis: ProductAnalysis) -> str:
    """根据商品分析结果判断茶叶模板族。

    规则优先级：
    1. 如果 `product_analysis.package_template_family` 已明确给出，直接使用。
    2. 再根据 `package_type / material / primary_container / product_type` 等关键词推断。
    3. 默认回退到礼盒模板。
    """
    explicit_family = str(getattr(analysis, "package_template_family", "") or "").strip().lower()
    if explicit_family in {"tea_tin_can", "tea_gift_box", "tea_pouch"}:
        return explicit_family

    package_signals = " ".join(
        filter(
            None,
            [
                str(getattr(analysis, "package_type", "") or ""),
                str(getattr(analysis, "material", "") or ""),
                str(getattr(analysis.packaging_structure, "primary_container", "") or ""),
                str(getattr(analysis.material_guess, "container_material", "") or ""),
                str(getattr(analysis, "product_type", "") or ""),
                str(getattr(analysis, "subcategory", "") or ""),
            ],
        )
    ).lower()

    if any(token in package_signals for token in ("tin", "can", "metal tin", "cylind", "cylinder", "罐", "金属罐", "铁罐")):
        return "tea_tin_can"
    if any(token in package_signals for token in ("pouch", "bag", "sachet", "stand-up", "袋", "袋装", "自立袋")):
        return "tea_pouch"
    return "tea_gift_box"


def get_tea_template_shot_pairs(analysis: ProductAnalysis) -> tuple[tuple[str, str], ...]:
    """返回当前茶叶商品应该使用的固定五图顺序。

    这个函数给 planner、QC、测试共用，避免某处仍然写死礼盒模板。
    """
    template_family = resolve_tea_package_template_family(analysis)
    if template_family == "tea_tin_can":
        return TEA_TIN_CAN_PHASE1_SHOTS
    if template_family == "tea_pouch":
        return TEA_POUCH_PHASE1_SHOTS
    return TEA_GIFT_BOX_PHASE1_SHOTS


def get_tea_default_scheme(shot_count: int, analysis: ProductAnalysis) -> list[str]:
    """返回茶叶类默认图型顺序。

    `shot_count` 在茶叶 Phase 1 中不会改变结果，保留这个参数只是为了兼容旧调用方。
    """
    del shot_count
    return [shot.shot_type for shot in build_tea_shot_slots(_build_task_stub(), analysis)]


def merge_tea_slot_details(slots: list[ShotSpec], enriched_plan: TeaShotEnrichmentPlan | None) -> ShotPlan:
    """把模型补充的细节字段合并回固定五图模板。

    这里只允许覆盖少数字段，避免模型把细节图改成主图，或者擅自改模板结构。
    """
    if enriched_plan is None:
        return ShotPlan(shots=slots)
    enriched_map = {shot.shot_id: shot for shot in enriched_plan.shots}
    merged: list[ShotSpec] = []
    for slot in slots:
        enriched = enriched_map.get(slot.shot_id)
        if enriched is None:
            merged.append(slot)
            continue
        merged.append(
            slot.model_copy(
                update={
                    "goal": enriched.goal or slot.goal,
                    "focus": enriched.focus or slot.focus,
                    "scene_direction": enriched.scene_direction or slot.scene_direction,
                    "composition_direction": enriched.composition_direction or slot.composition_direction,
                    "preferred_text_safe_zone": enriched.preferred_text_safe_zone or slot.preferred_text_safe_zone,
                }
            )
        )
    return ShotPlan(shots=merged)


def build_tea_enrichment_context(
    task: Task,
    analysis: ProductAnalysis,
    slots: list[ShotSpec],
    planning_context: dict[str, object],
) -> dict[str, object]:
    """构建茶叶固定五图的模型补细节上下文。"""
    return {
        "planner_mode": "fixed_phase1_five_shots",
        "category_family": "tea",
        "package_template_family": resolve_tea_package_template_family(analysis),
        "editable_fields": [
            "goal",
            "focus",
            "scene_direction",
            "composition_direction",
            "text_safe_zone_preference",
        ],
        "fixed_rules": [
            "must keep all five fixed shot slots",
            "must not add or remove shots",
            "must keep shot_id and shot_type unchanged",
            "must not rewrite title, purpose, composition_hint, or copy_goal",
            "text_safe_zone_preference may only refine the provided upper-area safe-zone tendency",
        ],
        "task": task,
        "product_analysis": analysis,
        "planning_context": planning_context,
        "fixed_shot_slots": slots,
    }


def _build_tea_gift_box_slots(analysis: ProductAnalysis) -> list[ShotSpec]:
    """礼盒模板：保留送礼动作图和开盒结构图。"""
    primary_color = analysis.primary_color or "red"
    package_type = analysis.package_type or "gift_box"
    package_label = analysis.label_structure or "front label layout"
    return [
        ShotSpec(
            shot_id="shot_01",
            title="Brand Hero",
            purpose="Establish the premium gift box as the brand-defining hero image.",
            composition_hint="Product centered or slightly lower, leave a clean upper text zone.",
            copy_goal="Show brand recognition and premium tea gift box value.",
            shot_type="hero_brand",
            goal="Make the package the only saturated hero subject in the frame.",
            focus="full package hero view",
            scene_direction=f"restrained premium tabletop scene with desaturated background tones around the {primary_color} package",
            composition_direction="Keep the product stable, front-facing or 3/4, and reserve a clean upper-right safe zone for copy.",
            preferred_text_safe_zone="top_right",
            required_subjects=[f"{package_type} package hero", package_label],
            optional_props=["muted linen", "neutral tea tray"],
        ),
        ShotSpec(
            shot_id="shot_02",
            title="Carry Action",
            purpose="Show a natural hand-carry or gift handoff moment without losing product lock.",
            composition_hint="Action direction determines the opposite-side text safe zone.",
            copy_goal="Convey real-life portability, gifting, and premium usability.",
            shot_type="carry_action",
            goal="Show restrained human interaction while keeping the package clearly recognizable.",
            focus="package carried by hand",
            scene_direction="clean lifestyle moment with muted background and restrained wardrobe colors",
            composition_direction="Let the action move in one direction and leave clean negative space on the opposite side for text.",
            preferred_text_safe_zone="top_left",
            required_subjects=[f"{package_type} package", "hand carry or gifting gesture"],
            optional_props=["neutral gift bag", "soft fabric sleeve"],
        ),
        ShotSpec(
            shot_id="shot_03",
            title="Open Box Structure",
            purpose="Explain the package opening logic and internal structure.",
            composition_hint="Open box angle with safe zone at top or top_right.",
            copy_goal="Highlight gift-box structure, opening experience, and material value.",
            shot_type="open_box_structure",
            goal="Reveal the opening structure clearly without redesigning any internal layout.",
            focus="box opening and internal structure",
            scene_direction="controlled premium tabletop with minimal props and clean structural read",
            composition_direction="Use a stable top or 3/4 angle and keep a clean safe zone above or top_right.",
            preferred_text_safe_zone="top_right",
            required_subjects=["opened package structure", "inner tray or inner contents layout"],
            optional_props=["tissue paper", "insert card"],
        ),
        ShotSpec(
            shot_id="shot_04",
            title="Dry Leaf Detail",
            purpose="Show tea leaf quality and texture while keeping package linkage.",
            composition_hint="Detail composition with a background clean area for copy.",
            copy_goal="Convey dry leaf quality, texture, and authenticity.",
            shot_type="dry_leaf_detail",
            goal="Connect the tea leaf detail with the same world as the package hero.",
            focus="dry leaf texture and package relationship",
            scene_direction="macro-friendly detail scene with muted surfaces and one or two restrained tea props",
            composition_direction="Place the dry leaf detail near the product or packaging cue and preserve a clear background safe zone.",
            preferred_text_safe_zone="top_right",
            required_subjects=["dry tea leaves", "package cue or label fragment"],
            optional_props=["small tea scoop", "neutral ceramic dish"],
        ),
        ShotSpec(
            shot_id="shot_05",
            title="Tea Soup Experience",
            purpose="Show brewed tea experience with a calm premium feeling.",
            composition_hint="Tea soup vessel stable, text safe zone at top.",
            copy_goal="Convey aroma, warmth, and tea drinking experience.",
            shot_type="tea_soup_experience",
            goal="Show tea soup color and drinking mood with the package still tied to the scene.",
            focus="tea soup vessel and package cue",
            scene_direction="premium brewed tea setting with desaturated background and unified prop family",
            composition_direction="Keep the tea vessel stable, maintain a clean upper safe zone, and avoid clutter behind the liquid.",
            preferred_text_safe_zone="top",
            required_subjects=["tea soup vessel", "brewed tea visual", "package cue"],
            optional_props=["gaiwan or teacup", "tea tray"],
        ),
    ]


def _build_tea_tin_can_slots(analysis: ProductAnalysis) -> list[ShotSpec]:
    """金属罐模板：突出罐体识别、工艺细节和冲泡场景。"""
    primary_color = analysis.primary_color or "red"
    package_type = analysis.package_type or "cylindrical tea tin"
    package_label = analysis.label_structure or "front label layout"
    return [
        ShotSpec(
            shot_id="shot_01",
            title="Brand Hero",
            purpose="Establish the tea tin as the hero subject with stable front branding.",
            composition_hint="Tin centered or slightly lower, leave a clean upper text zone.",
            copy_goal="Show brand identity and premium tin packaging value.",
            shot_type="hero_brand",
            goal="Make the tea tin the clear hero subject and preserve the original cylindrical identity.",
            focus="full tin can hero view",
            scene_direction=f"restrained premium tabletop scene with desaturated background around the {primary_color} tin",
            composition_direction="Keep the tin front-facing or 3/4 and reserve a clean upper-right safe zone for copy.",
            preferred_text_safe_zone="top_right",
            required_subjects=[f"{package_type} hero", package_label],
            optional_props=["muted linen", "neutral stone base"],
        ),
        ShotSpec(
            shot_id="shot_02",
            title="Package Detail",
            purpose="Show lid, label, material and cylindrical structure details of the tea tin.",
            composition_hint="Detail crop with stable upper text safe zone.",
            copy_goal="Convey material quality, printing detail, and package craftsmanship.",
            shot_type="package_detail",
            goal="Highlight the tin surface, lid, label, and edge details without changing the original structure.",
            focus="label, lid, and material details",
            scene_direction="controlled detail scene with muted background and commercial product lighting",
            composition_direction="Use a close 3/4 angle or detail crop, keep a clean top-right safe zone for copy.",
            preferred_text_safe_zone="top_right",
            required_subjects=["tin lid detail", package_label, "cylindrical sidewall structure"],
            optional_props=["neutral tray", "soft shadow base"],
        ),
        ShotSpec(
            shot_id="shot_03",
            title="Dry Leaf Detail",
            purpose="Show dry tea leaves with a subtle package cue from the same tin product.",
            composition_hint="Macro detail with a clear background safe zone.",
            copy_goal="Convey tea leaf quality, texture, and origin feel.",
            shot_type="dry_leaf_detail",
            goal="Connect dry leaf texture to the same tea tin product world without losing packaging linkage.",
            focus="dry leaf texture and package relationship",
            scene_direction="macro-friendly detail scene with restrained surfaces and minimal tea props",
            composition_direction="Place dry leaf detail near a tin cue and preserve a clear background safe zone for copy.",
            preferred_text_safe_zone="top_right",
            required_subjects=["dry tea leaves", "tin package cue"],
            optional_props=["tea scoop", "neutral ceramic dish"],
        ),
        ShotSpec(
            shot_id="shot_04",
            title="Tea Soup Experience",
            purpose="Show brewed tea color and cup experience while keeping the tin product connected.",
            composition_hint="Cup or gaiwan stable, text safe zone above.",
            copy_goal="Convey aroma, warmth, and tea drinking experience.",
            shot_type="tea_soup_experience",
            goal="Show brewed tea experience with a clear package cue from the same tea tin product.",
            focus="tea soup vessel and tin cue",
            scene_direction="premium brewed tea setting with desaturated background and unified props",
            composition_direction="Keep the vessel stable, maintain a clean upper safe zone, and avoid clutter behind the liquid.",
            preferred_text_safe_zone="top",
            required_subjects=["tea soup vessel", "brewed tea visual", "tin package cue"],
            optional_props=["gaiwan or teacup", "tea tray"],
        ),
        ShotSpec(
            shot_id="shot_05",
            title="Lifestyle Or Brewing Context",
            purpose="Show the tea tin in a restrained brewing or desktop lifestyle context.",
            composition_hint="Scene stays clean, leave safe zone on the upper side away from the main object cluster.",
            copy_goal="Convey daily premium usage and brewing atmosphere.",
            shot_type="lifestyle_or_brewing_context",
            goal="Place the tea tin into a believable brewing context without introducing a full human subject.",
            focus="tin within brewing context",
            scene_direction="quiet lifestyle brewing scene with neutral surfaces and one coherent prop family",
            composition_direction="Keep the tin and brewing tools readable, leave clean upper-left or upper-right negative space for copy.",
            preferred_text_safe_zone="top_left",
            required_subjects=["tea tin", "brewing context props"],
            optional_props=["kettle", "tea cloth", "cup set"],
        ),
    ]


def _build_tea_pouch_slots(analysis: ProductAnalysis) -> list[ShotSpec]:
    """袋装模板：延续轻量生活化展示，但围绕袋装结构而不是礼盒结构。"""
    primary_color = analysis.primary_color or "green"
    package_type = analysis.package_type or "tea pouch"
    package_label = analysis.label_structure or "front label layout"
    return [
        ShotSpec(
            shot_id="shot_01",
            title="Brand Hero",
            purpose="Establish the tea pouch as the hero subject with stable front branding.",
            composition_hint="Pouch centered or slightly lower, leave a clean upper text zone.",
            copy_goal="Show brand identity and pouch packaging value.",
            shot_type="hero_brand",
            goal="Make the tea pouch the only saturated hero subject in the frame.",
            focus="full pouch hero view",
            scene_direction=f"restrained premium tabletop scene with desaturated background around the {primary_color} pouch",
            composition_direction="Keep the pouch front-facing or 3/4 and reserve a clean upper-right safe zone for copy.",
            preferred_text_safe_zone="top_right",
            required_subjects=[f"{package_type} hero", package_label],
            optional_props=["muted linen", "neutral tray"],
        ),
        ShotSpec(
            shot_id="shot_02",
            title="Package Detail",
            purpose="Show zipper, gusset, label and material details of the tea pouch.",
            composition_hint="Detail crop with stable upper text safe zone.",
            copy_goal="Convey package material quality and portable structure.",
            shot_type="package_detail",
            goal="Highlight pouch material, seal structure, and label details without redesigning the package.",
            focus="zipper, gusset, and label details",
            scene_direction="controlled detail scene with muted background and product lighting",
            composition_direction="Use a close 3/4 angle or detail crop, keep a clean top-right safe zone for copy.",
            preferred_text_safe_zone="top_right",
            required_subjects=["pouch detail", package_label],
            optional_props=["neutral tray", "soft shadow base"],
        ),
        ShotSpec(
            shot_id="shot_03",
            title="Dry Leaf Detail",
            purpose="Show dry tea leaves with a subtle pouch cue from the same product.",
            composition_hint="Macro detail with a clear background safe zone.",
            copy_goal="Convey tea leaf quality and authenticity.",
            shot_type="dry_leaf_detail",
            goal="Connect dry leaf texture to the same tea pouch world without losing packaging linkage.",
            focus="dry leaf texture and package relationship",
            scene_direction="macro-friendly detail scene with restrained surfaces and minimal props",
            composition_direction="Place dry leaf detail near a pouch cue and preserve a clear background safe zone for copy.",
            preferred_text_safe_zone="top_right",
            required_subjects=["dry tea leaves", "pouch package cue"],
            optional_props=["tea scoop", "neutral ceramic dish"],
        ),
        ShotSpec(
            shot_id="shot_04",
            title="Tea Soup Experience",
            purpose="Show brewed tea color and cup experience while keeping the pouch product connected.",
            composition_hint="Cup or gaiwan stable, text safe zone above.",
            copy_goal="Convey aroma, warmth, and tea drinking experience.",
            shot_type="tea_soup_experience",
            goal="Show brewed tea experience with a clear package cue from the same tea pouch product.",
            focus="tea soup vessel and pouch cue",
            scene_direction="premium brewed tea setting with desaturated background and unified props",
            composition_direction="Keep the vessel stable and maintain a clean upper safe zone.",
            preferred_text_safe_zone="top",
            required_subjects=["tea soup vessel", "brewed tea visual", "pouch package cue"],
            optional_props=["gaiwan or teacup", "tea tray"],
        ),
        ShotSpec(
            shot_id="shot_05",
            title="Lifestyle Or Brewing Context",
            purpose="Show the pouch product in a restrained daily brewing context.",
            composition_hint="Scene stays clean, leave safe zone on the upper side away from the main object cluster.",
            copy_goal="Convey daily premium usage and brewing atmosphere.",
            shot_type="lifestyle_or_brewing_context",
            goal="Place the tea pouch into a believable brewing context without introducing a full human subject.",
            focus="pouch within brewing context",
            scene_direction="quiet lifestyle brewing scene with neutral surfaces and one coherent prop family",
            composition_direction="Keep the pouch and brewing tools readable, leave clean upper negative space for copy.",
            preferred_text_safe_zone="top_left",
            required_subjects=["tea pouch", "brewing context props"],
            optional_props=["kettle", "tea cloth", "cup set"],
        ),
    ]


def _build_task_stub() -> Task:
    return Task(
        task_id="tea-phase1",
        brand_name="-",
        product_name="-",
        platform="taobao",
        output_size="1440x1440",
        shot_count=5,
        copy_tone="-",
        task_dir="outputs/tasks/tea-phase1",
    )
