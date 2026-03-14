"""商品锁定分析 contract。

文件位置：
- `src/domain/product_analysis.py`

核心职责：
- 定义 `analyze_product` 节点输出的数据结构
- 为后续 `style_director / plan_shots / shot_prompt_refiner / render_images`
  提供统一的商品锁定信息

主要调用方：
- `src/workflows/nodes/analyze_product.py`

主要依赖方：
- `style_director`
- `shot_prompt_refiner`
- `build_prompts`
- `render_images`

关键输入/输出：
- 输入是视觉分析 provider 或 mock 分析逻辑产出的结果
- 输出是 `product_analysis.json` 对应的 Pydantic schema
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PackagingStructure(BaseModel):
    """包装结构描述。

    用于表达商品是盒装、罐装还是多件组合，以及是否有外盒、盖子等结构信息。
    """

    primary_container: str
    has_outer_box: str
    has_visible_lid: str
    container_count: str


class VisualIdentity(BaseModel):
    """商品视觉识别信息。

    这部分信息主要服务于“后续哪些元素必须保留”的判断。
    """

    dominant_colors: list[str] = Field(default_factory=list)
    label_position: str
    label_ratio: str
    style_impression: list[str] = Field(default_factory=list)
    must_preserve: list[str] = Field(default_factory=list)


class MaterialGuess(BaseModel):
    """商品与标签材质的轻量推断结果。"""

    container_material: str
    label_material: str


class VisualConstraints(BaseModel):
    """视觉约束与规避项。

    典型用途：
    - 给后续 prompt 规划阶段提供风格建议
    - 告诉生成链路哪些方向应该避免
    """

    recommended_style_direction: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)


class ProductAnalysis(BaseModel):
    """商品锁定分析结果。

    这是当前项目最重要的上游 contract 之一。
    它既承载传统的商品分析信息，也承载当前图生图链路需要的 product_lock 信息。
    """

    analysis_scope: Literal["sku_level"] = "sku_level"
    intended_for: Literal["all_future_shots"] = "all_future_shots"
    category: str
    subcategory: str
    product_type: str
    product_form: str
    packaging_structure: PackagingStructure
    visual_identity: VisualIdentity
    material_guess: MaterialGuess
    visual_constraints: VisualConstraints
    selling_points: list[str] = Field(default_factory=list)
    visual_style_keywords: list[str] = Field(default_factory=list)
    recommended_focuses: list[str] = Field(default_factory=list)
    source_asset_ids: list[str] = Field(default_factory=list)
    locked_elements: list[str] = Field(default_factory=list)
    must_preserve_texts: list[str] = Field(default_factory=list)
    editable_elements: list[str] = Field(default_factory=list)
    package_type: str = ""
    package_template_family: str = ""
    primary_color: str = ""
    material: str = ""
    label_structure: str = ""
