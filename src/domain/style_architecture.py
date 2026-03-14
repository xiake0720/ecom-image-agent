"""整组视觉架构 contract。

文件位置：
- `src/domain/style_architecture.py`

核心职责：
- 定义 `style_director` 节点输出的数据结构
- 表达整组图片共享的视觉世界观，而不是单张 prompt

主要调用方：
- `src/workflows/nodes/style_director.py`

主要依赖方：
- `plan_shots`
- `shot_prompt_refiner`
- 后续所有需要读取整组统一风格约束的节点

关键输入/输出：
- 输入来自整组视觉总导演节点
- 输出到 `style_architecture.json`
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class StyleArchitecture(BaseModel):
    """整组图统一视觉规则。

    字段设计原则：
    - `style_theme` 负责给出整组图的总气质
    - 各类 `*_strategy` 负责把总气质拆成程序和模型都能消费的规则列表
    - `global_negative_rules` 负责定义全局不允许发生的视觉偏差
    """

    platform: str
    user_preferences: list[str] = Field(default_factory=list)
    style_theme: str
    main_light_direction: str = "upper-left"
    color_strategy: list[str] = Field(default_factory=list)
    lighting_strategy: list[str] = Field(default_factory=list)
    lens_strategy: list[str] = Field(default_factory=list)
    prop_system: list[str] = Field(default_factory=list)
    background_strategy: list[str] = Field(default_factory=list)
    text_strategy: list[str] = Field(default_factory=list)
    global_negative_rules: list[str] = Field(default_factory=list)
