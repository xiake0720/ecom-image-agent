"""图组规划 contract。

文件位置：
- `src/domain/shot_plan.py`

核心职责：
- 定义 `plan_shots` 节点输出的结构化图位规划结果
- 约束每个 shot 至少包含什么信息，便于后续 copy、layout、prompt 节点稳定消费

主要被谁调用：
- `src/workflows/nodes/plan_shots.py`

主要依赖谁：
- `generate_copy`
- `generate_layout`
- `shot_prompt_refiner`

关键输入/输出：
- 输入来自图组规划节点
- 输出落盘为 `shot_plan.json`
"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field


class ShotSpec(BaseModel):
    """单张图位的规划结果。

    为什么需要这个类：
    - `plan_shots` 既要兼容旧链路里 copy/layout 依赖的字段，
      又要承载茶叶类固定五图模板新增的结构化约束。

    典型使用场景：
    - `generate_copy` 读取 `title / purpose / copy_goal`
    - `generate_layout` 读取 `composition_hint` 与 `preferred_text_safe_zone`
    - `shot_prompt_refiner` 读取 `goal / focus / scene_direction / composition_direction`
    """

    shot_id: str
    title: str
    purpose: str
    composition_hint: str
    copy_goal: str
    shot_type: str = "generic_ecommerce"
    goal: str = ""
    focus: str = ""
    scene_direction: str = ""
    composition_direction: str = ""
    preferred_text_safe_zone: str = Field(
        default="",
        validation_alias=AliasChoices("preferred_text_safe_zone", "text_safe_zone_preference"),
    )
    required_subjects: list[str] = Field(default_factory=list)
    optional_props: list[str] = Field(default_factory=list)


class ShotPlan(BaseModel):
    """整组图片的图位规划结果。"""

    shots: list[ShotSpec] = Field(default_factory=list)


class TeaShotEnrichmentSpec(BaseModel):
    """茶叶固定五图模板中，模型允许补充的少量字段。

    这个 schema 不会直接落盘，只用于 real 模式下约束模型：
    它只能补细节，不能重写完整模板。
    """

    shot_id: str
    goal: str = ""
    focus: str = ""
    scene_direction: str = ""
    composition_direction: str = ""
    preferred_text_safe_zone: str = Field(
        default="",
        validation_alias=AliasChoices("preferred_text_safe_zone", "text_safe_zone_preference"),
    )


class TeaShotEnrichmentPlan(BaseModel):
    """茶叶固定五图模板的模型补细节结果集合。"""

    shots: list[TeaShotEnrichmentSpec] = Field(default_factory=list)
