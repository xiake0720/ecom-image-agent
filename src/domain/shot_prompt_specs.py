"""单张结构化 prompt spec contract。

文件位置：
- `src/domain/shot_prompt_specs.py`

核心职责：
- 定义 `shot_prompt_refiner` 节点输出的 `shot_prompt_specs.json`
- 让“单张图 prompt 细化”从一段散文式 prompt，升级为程序可消费的结构化 spec

主要被谁调用：
- `src/workflows/nodes/shot_prompt_refiner.py`

主要依赖谁：
- `build_prompts`
- `render_images`

关键输入/输出：
- 输入来自 `product_analysis + style_architecture + shot_plan + layout_plan`
- 输出落盘为 `shot_prompt_specs.json`
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


SHOT_PROMPT_LAYER_FIELDS = (
    "subject_prompt",
    "package_appearance_prompt",
    "composition_prompt",
    "background_prompt",
    "lighting_prompt",
    "style_prompt",
    "quality_prompt",
    "negative_prompt",
)


def _normalize_string_list(value) -> list[str]:
    """把字符串 / 列表统一归一化成字符串列表。"""
    if value is None:
        return []
    if isinstance(value, str):
        normalized = value.replace("\r", "\n").replace(",", "\n")
        return [item.strip() for item in normalized.splitlines() if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


class ProductLockSpec(BaseModel):
    """单张图需要继承的商品锁定约束。"""

    must_preserve: list[str] = Field(default_factory=list)
    must_preserve_texts: list[str] = Field(default_factory=list)
    editable_regions: list[str] = Field(default_factory=list)
    must_not_change: list[str] = Field(default_factory=list)

    @field_validator("must_preserve", "must_preserve_texts", "editable_regions", "must_not_change", mode="before")
    @classmethod
    def _normalize_list_fields(cls, value):
        return _normalize_string_list(value)

    def flattened_rules(self) -> list[str]:
        """把结构化 product lock 展平成便于日志和 prompt 拼接的规则列表。"""
        rules = [*self.must_preserve]
        if self.must_preserve_texts:
            rules.append(f"must preserve texts: {', '.join(self.must_preserve_texts)}")
        rules.extend(f"must not change: {item}" for item in self.must_not_change)
        return rules


class LayoutConstraintSpec(BaseModel):
    """文字安全区和主体摆位约束。"""

    preferred_text_safe_zone: str = ""
    avoid_overlap_with_subject: bool = True
    max_text_layers: int = 2
    subject_placement_hint: str = ""

    def as_prompt_lines(self) -> list[str]:
        """把布局约束转成便于 prompt 和日志使用的描述列表。"""
        lines: list[str] = []
        if self.preferred_text_safe_zone:
            lines.append(f"preferred_text_safe_zone={self.preferred_text_safe_zone}")
        lines.append(f"avoid_overlap_with_subject={str(self.avoid_overlap_with_subject).lower()}")
        lines.append(f"max_text_layers={self.max_text_layers}")
        if self.subject_placement_hint:
            lines.append(f"subject_placement_hint={self.subject_placement_hint}")
        return lines


class RenderConstraintSpec(BaseModel):
    """渲染执行约束。

    这里不是直接控制 provider 的底层参数，而是表达这张图的目标生成策略，
    便于 `build_prompts` 和调试日志读取。
    """

    generation_mode: str = "t2i"
    reference_image_priority: str = "none"
    consistency_strength: str = "medium"
    product_lock_level: str = "strong_product_lock"
    editable_region_strategy: str = "background_props_only"
    allow_human_presence: bool = False
    allow_hand_only: bool = False

    def as_prompt_lines(self) -> list[str]:
        """把渲染约束转成可拼装的描述列表。"""
        return [
            f"generation_mode={self.generation_mode}",
            f"reference_image_priority={self.reference_image_priority}",
            f"consistency_strength={self.consistency_strength}",
            f"product_lock_level={self.product_lock_level}",
            f"editable_region_strategy={self.editable_region_strategy}",
            f"allow_human_presence={str(self.allow_human_presence).lower()}",
            f"allow_hand_only={str(self.allow_hand_only).lower()}",
        ]


class CopyIntentSpec(BaseModel):
    """说明这张图希望文案各层承担什么角色。"""

    title_role: str = ""
    subtitle_role: str = ""
    bullet_role: str = "optional"
    cta_role: str = "none"

    def summary_text(self) -> str:
        """返回简短摘要，便于写入最终执行 prompt。"""
        return (
            f"title_role={self.title_role}; "
            f"subtitle_role={self.subtitle_role}; "
            f"bullet_role={self.bullet_role}; "
            f"cta_role={self.cta_role}"
        )


class ShotPromptSpec(BaseModel):
    """单张图片的结构化生成说明。

    这份 spec 会被 `build_prompts` 进一步映射成兼容旧链路的 `ImagePromptPlan`，
    因此字段既要方便模型生成，也要方便程序直接消费。
    """

    shot_id: str
    shot_type: str
    goal: str
    product_lock: ProductLockSpec = Field(default_factory=ProductLockSpec)
    subject_prompt: str
    package_appearance_prompt: str
    composition_prompt: str
    background_prompt: str
    lighting_prompt: str
    style_prompt: str
    quality_prompt: str
    negative_prompt: list[str] = Field(default_factory=list)
    layout_constraints: LayoutConstraintSpec = Field(default_factory=LayoutConstraintSpec)
    render_constraints: RenderConstraintSpec = Field(default_factory=RenderConstraintSpec)
    copy_intent: CopyIntentSpec = Field(default_factory=CopyIntentSpec)

    @field_validator("negative_prompt", mode="before")
    @classmethod
    def _normalize_negative_prompt(cls, value):
        return _normalize_string_list(value)

    @field_validator("product_lock", mode="before")
    @classmethod
    def _normalize_product_lock(cls, value):
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        return {"must_preserve": _normalize_string_list(value)}

    @field_validator("layout_constraints", mode="before")
    @classmethod
    def _normalize_layout_constraints(cls, value):
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        lines = _normalize_string_list(value)
        preferred_zone = ""
        for candidate in ("top_left", "top_right", "top", "right_center", "left_center", "bottom_left", "bottom_right"):
            if any(candidate in line for line in lines):
                preferred_zone = candidate
                break
        return {
            "preferred_text_safe_zone": preferred_zone or (lines[0] if lines else ""),
            "avoid_overlap_with_subject": True,
            "max_text_layers": 2,
            "subject_placement_hint": " / ".join(lines),
        }

    @field_validator("render_constraints", mode="before")
    @classmethod
    def _normalize_render_constraints(cls, value):
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        lines = [line.lower() for line in _normalize_string_list(value)]
        generation_mode = "image_edit" if any("image_edit" in line for line in lines) else "t2i"
        reference_image_priority = "main_packshot" if generation_mode == "image_edit" else "none"
        consistency_strength = "high" if any("strict" in line or "high" in line for line in lines) else "medium"
        if any("anchor_only_product_lock" in line for line in lines):
            product_lock_level = "anchor_only_product_lock"
        elif any("medium_product_lock" in line for line in lines):
            product_lock_level = "medium_product_lock"
        else:
            product_lock_level = "strong_product_lock"
        editable_region_strategy = "background_props_only"
        for line in lines:
            if "editable_region_strategy=" in line:
                editable_region_strategy = line.split("editable_region_strategy=", maxsplit=1)[1].strip() or editable_region_strategy
                break
        allow_hand_only = any("hand" in line for line in lines)
        allow_human_presence = allow_hand_only or any("human" in line or "person" in line for line in lines)
        return {
            "generation_mode": generation_mode,
            "reference_image_priority": reference_image_priority,
            "consistency_strength": consistency_strength,
            "product_lock_level": product_lock_level,
            "editable_region_strategy": editable_region_strategy,
            "allow_human_presence": allow_human_presence,
            "allow_hand_only": allow_hand_only,
        }

    @field_validator("copy_intent", mode="before")
    @classmethod
    def _normalize_copy_intent(cls, value):
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        text = str(value).strip()
        if not text:
            return {}
        return {
            "title_role": text,
            "subtitle_role": "",
            "bullet_role": "optional",
            "cta_role": "none",
        }

    def has_complete_prompt_layers(self) -> bool:
        """检查 8 层结构是否完整，便于节点日志快速判断输出质量。"""
        for field_name in SHOT_PROMPT_LAYER_FIELDS:
            value = getattr(self, field_name)
            if isinstance(value, list):
                if not value:
                    return False
                continue
            if not str(value or "").strip():
                return False
        return True


class ShotPromptSpecPlan(BaseModel):
    """整组图片的结构化 spec 集合。"""

    specs: list[ShotPromptSpec] = Field(default_factory=list)
