"""v2 schema 与 workflow state 兼容性测试。"""

from __future__ import annotations

from src.domain.copy_plan import CopyItem, CopyPlan
from src.domain.director_output import DirectorOutput, DirectorShot
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from src.domain.layout_plan import LayoutBlock, LayoutItem, LayoutPlan
from src.domain.product_analysis import (
    MaterialGuess,
    PackagingStructure,
    ProductAnalysis,
    VisualConstraints,
    VisualIdentity,
)
from src.domain.prompt_plan_v2 import PromptPlanV2, PromptShot
from src.domain.qc_report import QCCheck, QCReport
from src.domain.shot_plan import ShotPlan, ShotSpec
from src.domain.style_architecture import StyleArchitecture
from src.domain.task import Task
from src.workflows.state import WorkflowState, build_connected_contract_summary


def _build_task() -> Task:
    """构造最小可用任务对象。"""
    return Task(
        task_id="task-v2-001",
        brand_name="醒千峰",
        product_name="高山乌龙礼盒",
        category="tea",
        platform="tmall",
        output_size="2048x2048",
        shot_count=8,
        copy_tone="高级克制",
        task_dir="outputs/tasks/task-v2-001",
    )


def _build_product_analysis() -> ProductAnalysis:
    """构造最小可用商品分析对象。"""
    return ProductAnalysis(
        analysis_scope="sku_level",
        intended_for="all_future_shots",
        category="tea",
        subcategory="乌龙茶",
        product_type="茶礼盒",
        product_form="packaged_tea",
        packaging_structure=PackagingStructure(
            primary_container="box",
            has_outer_box="yes",
            has_visible_lid="yes",
            container_count="1",
        ),
        visual_identity=VisualIdentity(
            dominant_colors=["白色", "金色"],
            label_position="front_center",
            label_ratio="medium",
            style_impression=["高级", "简洁"],
            must_preserve=["品牌名", "主标签区"],
        ),
        material_guess=MaterialGuess(
            container_material="paper_box",
            label_material="matte_paper",
        ),
        visual_constraints=VisualConstraints(
            recommended_style_direction=["保留白金主色调"],
            avoid=["不要改动品牌识别"],
        ),
    )


def test_director_output_schema_accepts_basic_tea_plan() -> None:
    director_output = DirectorOutput(
        product_summary="白金简约风格的高山乌龙礼盒，强调送礼质感与茶叶品质。",
        category="tea",
        platform="tmall",
        visual_style="高级克制、白金礼赠、电商转化导向、整套视觉统一",
        shots=[
            DirectorShot(
                shot_id="shot-01",
                shot_role="hero",
                objective="建立品牌第一视觉和礼盒高级感",
                audience="天猫送礼与自饮兼顾用户",
                selling_points=["礼盒质感", "品牌识别", "高端送礼"],
                scene="高级白底棚拍主图场景，局部金色反光控制在弱范围",
                composition="主体居中偏下，顶部和右侧留文案安全区",
                visual_focus="礼盒正面包装、品牌标识、整体立体结构",
                copy_direction="强调高端送礼、品牌质感与茶礼体面感",
                compliance_notes=["不要虚构功效", "不要改写包装品牌文字"],
            )
        ],
    )

    dumped = director_output.model_dump()

    assert dumped["platform"] == "tmall"
    assert dumped["shots"][0]["shot_role"] == "hero"
    assert dumped["shots"][0]["selling_points"][0] == "礼盒质感"


def test_prompt_plan_v2_schema_accepts_basic_render_plan() -> None:
    prompt_plan_v2 = PromptPlanV2(
        shots=[
            PromptShot(
                shot_id="shot-01",
                shot_role="hero",
                render_prompt="天猫茶叶礼盒主图，高级白底棚拍，保留真实包装结构与品牌标识，文案融入画面顶部留白区域。",
                title_copy="高山乌龙",
                subtitle_copy="礼赠自饮皆宜",
                layout_hint="标题放左上，副标题放标题下方，右下保留产品主体完整展示区",
            )
        ]
    )

    dumped = prompt_plan_v2.model_dump()

    assert dumped["shots"][0]["title_copy"] == "高山乌龙"
    assert dumped["shots"][0]["subtitle_copy"] == "礼赠自饮皆宜"
    assert dumped["shots"][0]["aspect_ratio"] == "1:1"
    assert dumped["shots"][0]["image_size"] == "2K"


def test_workflow_state_accepts_v1_and_v2_fields_together() -> None:
    task = _build_task()
    product_analysis = _build_product_analysis()
    style_architecture = StyleArchitecture(
        platform="tmall",
        style_theme="高级白金礼赠风",
        color_strategy=["白金主色", "局部暖金点缀"],
        lighting_strategy=["柔和顶部主光"],
        lens_strategy=["中焦产品商业摄影"],
        prop_system=["简洁茶席元素"],
        background_strategy=["干净浅色背景"],
        text_strategy=["顶部和右侧留文案空间"],
        global_negative_rules=["不要虚构包装结构", "不要出现廉价促销视觉"],
    )
    shot_plan = ShotPlan(
        shots=[
            ShotSpec(
                shot_id="shot-01",
                title="主图",
                purpose="建立第一视觉",
                composition_hint="主体居中，顶部留白",
                copy_goal="品牌感",
                shot_type="hero",
                goal="突出礼盒品牌识别",
                focus="礼盒正面包装",
                scene_direction="高级棚拍",
                composition_direction="主体居中偏下",
                preferred_text_safe_zone="top_right",
            )
        ]
    )
    copy_plan = CopyPlan(items=[CopyItem(shot_id="shot-01", title="高山乌龙", subtitle="礼赠自饮皆宜", bullets=["礼盒质感"])])
    layout_plan = LayoutPlan(
        items=[
            LayoutItem(
                shot_id="shot-01",
                canvas_width=2048,
                canvas_height=2048,
                text_safe_zone="top_right",
                blocks=[LayoutBlock(kind="title", x=120, y=120, width=420, height=120)],
            )
        ]
    )
    image_prompt_plan = ImagePromptPlan(
        prompts=[ImagePrompt(shot_id="shot-01", shot_type="hero", prompt="tea hero", output_size="2048x2048")]
    )
    director_output = DirectorOutput(
        product_summary="白金高山乌龙礼盒，强调送礼高级感。",
        category="tea",
        platform="tmall",
        visual_style="高级克制、礼赠导向、全套统一",
        shots=[
            DirectorShot(
                shot_id="shot-01",
                shot_role="hero",
                objective="建立品牌主视觉",
                audience="天猫礼盒茶购买人群",
                selling_points=["高级礼盒", "品牌识别"],
                scene="高级白底主图",
                composition="主体居中，顶部留白",
                visual_focus="礼盒正面与品牌标识",
                copy_direction="突出品牌感和送礼体面",
                compliance_notes=["不要夸大功效"],
            )
        ],
    )
    prompt_plan_v2 = PromptPlanV2(
        shots=[
            PromptShot(
                shot_id="shot-01",
                shot_role="hero",
                render_prompt="保留真实礼盒包装结构和品牌标识，统一高级白金商业摄影风格，标题副标题融入顶部留白。",
                title_copy="高山乌龙",
                subtitle_copy="礼赠自饮皆宜",
                layout_hint="左上标题，标题下副标题，右下保留产品主体区",
            )
        ]
    )
    generation_result = GenerationResult(
        images=[
            GeneratedImage(
                shot_id="shot-01",
                image_path="outputs/tasks/task-v2-001/finals/shot-01.png",
                preview_path="outputs/tasks/task-v2-001/previews/shot-01.png",
                width=2048,
                height=2048,
            )
        ]
    )
    qc_report = QCReport(
        passed=True,
        checks=[QCCheck(shot_id="shot-01", check_name="basic", passed=True, details="ok")],
    )

    state: WorkflowState = {
        "task": task,
        "workflow_version": "v2",
        "product_analysis": product_analysis,
        "product_lock": product_analysis,
        "style_architecture": style_architecture,
        "shot_plan": shot_plan,
        "copy_plan": copy_plan,
        "layout_plan": layout_plan,
        "image_prompt_plan": image_prompt_plan,
        "director_output": director_output,
        "prompt_plan_v2": prompt_plan_v2,
        "generation_result": generation_result,
        "generation_result_v2": generation_result,
        "qc_report": qc_report,
        "qc_report_v2": qc_report,
    }

    summary = build_connected_contract_summary(state)

    assert state["workflow_version"] == "v2"
    assert state["style_architecture"].style_theme == "高级白金礼赠风"
    assert state["image_prompt_plan"].prompts[0].shot_type == "hero"
    assert state["director_output"].shots[0].shot_role == "hero"
    assert state["prompt_plan_v2"].shots[0].layout_hint.startswith("左上标题")
    assert state["generation_result_v2"].images[0].width == 2048
    assert state["qc_report_v2"].passed is True
    assert summary["style_architecture_connected"] is True
    assert summary["product_lock_connected"] is True
