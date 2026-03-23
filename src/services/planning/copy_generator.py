<<<<<<< HEAD
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

=======
"""本地 mock 文案生成器。

文件位置：
- `src/services/planning/copy_generator.py`

核心职责：
- 在 mock 模式下为每个 shot 生成短版贴图文案
- 复用 fallback 规则，保证 mock 输出也符合后续叠字长度约束
"""

from __future__ import annotations

from src.domain.copy_plan import CopyPlan
from src.domain.shot_plan import ShotPlan
from src.domain.task import Task
from src.services.fallbacks.copy_fallback import build_default_copy_item_for_shot


def build_mock_copy_plan(task: Task, shot_plan: ShotPlan) -> CopyPlan:
    """构建适合中文贴图的 mock CopyPlan。"""
    return CopyPlan(
        items=[
            build_default_copy_item_for_shot(shot, task=task)
            for shot in shot_plan.shots
        ]
    )
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
