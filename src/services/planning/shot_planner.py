from __future__ import annotations

from src.domain.product_analysis import ProductAnalysis
from src.domain.shot_plan import ShotPlan, ShotSpec


def build_mock_shot_plan(analysis: ProductAnalysis, shot_count: int) -> ShotPlan:
    shot_names = ["品牌主图", "卖点细节", "场景氛围", "茶汤展示", "礼盒展示"]
    shots = [
        ShotSpec(
            shot_id=f"shot-{index:02d}",
            title=shot_names[(index - 1) % len(shot_names)],
            purpose=f"围绕{analysis.product_type}输出电商图",
            composition_hint="主体清晰，右侧留白，适合后贴字",
            copy_goal="突出品牌、品类和饮用体验",
        )
        for index in range(1, shot_count + 1)
    ]
    return ShotPlan(shots=shots)

