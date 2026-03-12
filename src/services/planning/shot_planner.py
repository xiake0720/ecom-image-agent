from __future__ import annotations

from src.domain.product_analysis import ProductAnalysis
from src.domain.shot_plan import ShotPlan, ShotSpec


def build_mock_shot_plan(analysis: ProductAnalysis, shot_count: int) -> ShotPlan:
    shot_names = ["品牌主图", "卖点细节", "场景氛围", "茶汤展示", "礼盒展示"]
    shot_types = ["hero", "feature_detail", "lifestyle", "brew_scene", "gift_showcase"]
    scene_directions = [
        "高级棚拍主图场景，背景简洁，品牌感强",
        "突出包装与标签细节的近景静物场景",
        "自然茶席与东方生活方式场景",
        "茶汤与器具搭配的冲泡氛围场景",
        "礼赠陈列与节庆氛围场景",
    ]
    composition_directions = [
        "主体偏中间，右侧或上方保留文案留白",
        "主体靠近镜头，局部细节清晰，侧边留白",
        "主体位于画面中下部，背景层次自然展开",
        "主体与茶具形成前后层次，左上或右上留白",
        "主体稳固居中，背景道具克制，四周层次干净",
    ]
    shots = [
        ShotSpec(
            shot_id=f"shot-{index:02d}",
            title=shot_names[(index - 1) % len(shot_names)],
            purpose=f"围绕{analysis.product_type}输出电商图",
            composition_hint="主体清晰，右侧留白，适合后贴字",
            copy_goal="突出品牌、品类和饮用体验",
            shot_type=shot_types[(index - 1) % len(shot_types)],
            goal=f"突出{analysis.product_type}的核心识别点与商业陈列感",
            focus=(analysis.recommended_focuses[(index - 1) % len(analysis.recommended_focuses)] if analysis.recommended_focuses else "包装主体与标签区"),
            scene_direction=scene_directions[(index - 1) % len(scene_directions)],
            composition_direction=composition_directions[(index - 1) % len(composition_directions)],
        )
        for index in range(1, shot_count + 1)
    ]
    return ShotPlan(shots=shots)
