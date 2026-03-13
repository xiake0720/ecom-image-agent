from __future__ import annotations

from src.domain.product_analysis import ProductAnalysis
from src.domain.shot_plan import ShotPlan, ShotSpec
from src.domain.task import Task


TEA_CORE_SLOT_TYPES = [
    "hero",
    "dry_leaf_detail",
    "tea_soup",
    "brewed_leaf_detail",
]

TEA_EXTENSION_SLOT_TYPES = [
    "packaging_display",
    "tea_table_scene",
    "gift_scene_or_multi_can_display",
]


def build_tea_shot_plan(task: Task, analysis: ProductAnalysis) -> ShotPlan:
    return ShotPlan(shots=build_tea_shot_slots(task, analysis))


def build_tea_shot_slots(task: Task, analysis: ProductAnalysis) -> list[ShotSpec]:
    slots = _build_base_slots(analysis)
    requested = max(1, min(task.shot_count, len(slots)))
    return [slot.model_copy(update={"shot_id": f"shot-{index:02d}"}) for index, slot in enumerate(slots[:requested], start=1)]


def get_tea_default_scheme(shot_count: int, analysis: ProductAnalysis) -> list[str]:
    task_stub = Task(
        task_id="tea-default-scheme",
        brand_name="-",
        product_name="-",
        platform="tmall",
        output_size="1440x1440",
        shot_count=shot_count,
        copy_tone="-",
        task_dir="outputs/tasks/tea-default-scheme",
    )
    return [shot.shot_type for shot in build_tea_shot_slots(task_stub, analysis)]


def merge_tea_slot_details(slots: list[ShotSpec], enriched_plan: ShotPlan | None) -> ShotPlan:
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
                }
            )
        )
    return ShotPlan(shots=merged)


def build_tea_enrichment_context(task: Task, analysis: ProductAnalysis, slots: list[ShotSpec], planning_context: dict[str, object]) -> dict[str, object]:
    return {
        "planner_mode": "templated_slots_then_minimal_enrichment",
        "category_family": "tea",
        "editable_fields": [
            "goal",
            "focus",
            "scene_direction",
            "composition_direction",
        ],
        "fixed_rules": [
            "不得新增、删除或替换 shot slots",
            "不得改动 shot_id、title、purpose、composition_hint、copy_goal、shot_type",
            "必须先服务茶叶类目核心图型，再补充扩展图型",
            "不得引入凉席、席面大面积铺陈、喧宾夺主花器等跑偏元素",
        ],
        "task": task,
        "product_analysis": analysis,
        "planning_context": planning_context,
        "fixed_shot_slots": slots,
    }


def _build_base_slots(analysis: ProductAnalysis) -> list[ShotSpec]:
    focuses = analysis.recommended_focuses or ["包装主体", "干茶形态", "茶汤表现", "叶底状态"]
    final_extension = _resolve_final_extension_type(analysis)
    final_extension_title = "礼赠场景" if final_extension == "gift_scene" else "多罐陈列"
    final_extension_purpose = "补充礼赠陈列价值" if final_extension == "gift_scene" else "补充多罐组合与陈列价值"
    final_extension_copy_goal = "强调礼赠感与成套价值" if final_extension == "gift_scene" else "强调组合陈列与购买规格"
    final_extension_goal = "补充茶叶礼赠导向与节庆价值" if final_extension == "gift_scene" else "补充茶叶多罐组合与成套陈列信息"
    final_extension_focus = "礼盒包装关系与赠礼氛围" if final_extension == "gift_scene" else "多罐数量关系与陈列秩序"
    final_extension_scene = "克制礼赠陈列场景，节庆感点到为止，不堆砌装饰" if final_extension == "gift_scene" else "多罐成组陈列场景，统一色调与秩序感"
    final_extension_composition = "主体稳固居中，边缘道具弱化，顶部或右侧保留文字区"

    return [
        ShotSpec(
            shot_id="shot-01",
            title="主图",
            purpose="建立整组统一主视觉与商品识别",
            composition_hint="主体居中偏下，右侧或上方留白",
            copy_goal="突出品牌、茶类与包装主体",
            shot_type="hero",
            goal="先建立茶叶商品的统一商业主视觉与主包装识别",
            focus=focuses[0] if len(focuses) > 0 else "包装主体",
            scene_direction="高级商业棚拍主图，背景干净克制，避免花哨中式堆砌",
            composition_direction="主体占比充分，包装主体清晰稳定，右侧或上方形成干净文字留白",
        ),
        ShotSpec(
            shot_id="shot-02",
            title="干茶细节",
            purpose="补充茶叶条索、干茶形态与包装呼应",
            composition_hint="近景细节，局部特写，顶部留白",
            copy_goal="强调干茶形态与原料质感",
            shot_type="dry_leaf_detail",
            goal="补充茶叶类目的干茶形态信息层",
            focus=focuses[1] if len(focuses) > 1 else "干茶条索与材质",
            scene_direction="同色系静物细节场景，少量茶器辅助，不引入跑题道具",
            composition_direction="主体近景偏左或偏中，细节清晰，顶部或侧边预留干净文字区",
        ),
        ShotSpec(
            shot_id="shot-03",
            title="茶汤图",
            purpose="展示冲泡后的汤色、清透度与饮用氛围",
            composition_hint="杯盏稳定，侧方留白",
            copy_goal="强调汤色、香气联想与饮用体验",
            shot_type="tea_soup",
            goal="完成茶叶类目核心图型中的茶汤表现",
            focus=focuses[2] if len(focuses) > 2 else "茶汤色泽与通透感",
            scene_direction="统一色调的冲泡场景，器具克制，避免复杂席面和舞台化摆设",
            composition_direction="杯盏与包装形成主次关系，右上或侧边留白，避免背景杂乱",
        ),
        ShotSpec(
            shot_id="shot-04",
            title="叶底细节",
            purpose="展示冲泡后叶底状态与品类特征",
            composition_hint="局部近景，主体靠前",
            copy_goal="强调叶底状态与茶叶真实感",
            shot_type="brewed_leaf_detail",
            goal="补充茶叶类目核心图型中的叶底与冲泡细节",
            focus=focuses[3] if len(focuses) > 3 else "叶底状态与茶叶质感",
            scene_direction="克制近景细节场景，茶器退后，画面保持真实自然",
            composition_direction="局部特写清晰稳定，边侧保留规整留白，避免纹理过满",
        ),
        ShotSpec(
            shot_id="shot-05",
            title="包装展示",
            purpose="补充单罐或主包装的完整展示与陈列感",
            composition_hint="包装完整露出，主体稳定",
            copy_goal="强化包装结构、规格与陈列价值",
            shot_type="packaging_display",
            goal="补充茶叶扩展图型中的包装展示信息",
            focus="包装结构、标签关系与规格信息",
            scene_direction="干净商业陈列场景，包装完整可辨，背景色系统一",
            composition_direction="主体完整露出，居中或偏左陈列，右侧预留文字区",
        ),
        ShotSpec(
            shot_id="shot-06",
            title="茶席场景",
            purpose="补充克制生活方式感，但仍服务商品转化",
            composition_hint="商品仍是主角，环境只做辅助",
            copy_goal="传达饮用情境与品质氛围",
            shot_type="tea_table_scene",
            goal="补充茶叶扩展图型中的轻场景氛围",
            focus="商品主体与茶席氛围的平衡",
            scene_direction="轻茶席场景，器具和台面克制，不出现凉席、席面大铺陈或抢戏花器",
            composition_direction="商品主体位于前景主位，场景后退弱化，顶部或右侧保留可用留白",
        ),
        ShotSpec(
            shot_id="shot-07",
            title=final_extension_title,
            purpose=final_extension_purpose,
            composition_hint="主体稳定成组，画面秩序清晰",
            copy_goal=final_extension_copy_goal,
            shot_type=final_extension,
            goal=final_extension_goal,
            focus=final_extension_focus,
            scene_direction=final_extension_scene,
            composition_direction=final_extension_composition,
        ),
    ]


def _resolve_final_extension_type(analysis: ProductAnalysis) -> str:
    packaging = analysis.packaging_structure
    if packaging.has_outer_box == "yes":
        return "gift_scene"
    if packaging.container_count not in {"1", "single", "one"}:
        return "multi_can_display"
    if "gift" in " ".join([analysis.category, analysis.subcategory, analysis.product_type]).lower():
        return "gift_scene"
    return "multi_can_display"
