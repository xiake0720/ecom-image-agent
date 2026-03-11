from __future__ import annotations

from src.domain.copy_plan import CopyItem, CopyPlan
from src.domain.shot_plan import ShotPlan
from src.domain.task import Task


def build_mock_copy_plan(task: Task, shot_plan: ShotPlan) -> CopyPlan:
    items = []
    for shot in shot_plan.shots:
        items.append(
            CopyItem(
                shot_id=shot.shot_id,
                title=f"{task.brand_name} {task.product_name}",
                subtitle=f"{task.copy_tone}风格表达，适配{task.platform}主图展示",
                bullets=["茶香鲜爽", "电商主图适配", "支持中文后贴字"],
                cta="立即查看",
            )
        )
    return CopyPlan(items=items)

