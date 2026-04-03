"""详情图文案生成服务。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.engine.core.config import get_settings
from backend.engine.providers.router import build_capability_bindings
from backend.schemas.detail import DetailPageCopyBlock, DetailPageJobCreatePayload, DetailPagePlanPayload


class _CopyPlanModel(BaseModel):
    """用于调用结构化模型的文案 Schema。"""

    copy_blocks: list[DetailPageCopyBlock] = Field(default_factory=list)


class DetailCopyService:
    """负责生成每一屏结构化文案，优先走模型，失败时降级。"""

    def build_copy(self, payload: DetailPageJobCreatePayload, plan: DetailPagePlanPayload) -> list[DetailPageCopyBlock]:
        """输出与每个 screen 绑定的 copy plan。"""

        prompt = self._build_prompt(payload, plan)
        try:
            bindings = build_capability_bindings(get_settings())
            result = bindings.planning_provider.generate_structured(
                prompt,
                _CopyPlanModel,
                system_prompt="你是茶叶电商详情图文案策划，请输出严格 JSON，保持高级克制、真实可读。",
            )
            if result.copy_blocks:
                return result.copy_blocks
        except Exception:
            # 模型不可用时保留结构化降级方案，保证链路可运行。
            pass
        return self._fallback_copy(payload, plan)

    def _fallback_copy(self, payload: DetailPageJobCreatePayload, plan: DetailPagePlanPayload) -> list[DetailPageCopyBlock]:
        """在模型不可用时生成可追踪的基础文案。"""

        rows: list[DetailPageCopyBlock] = []
        default_points = payload.selling_points or ["原叶茶香", "口感清润", "场景百搭"]
        for page in plan.pages:
            for screen in page.screens:
                rows.append(
                    DetailPageCopyBlock(
                        page_id=page.page_id,
                        screen_id=screen.screen_id,
                        headline=f"{payload.brand_name or '茶香精选'}｜{screen.theme}",
                        subheadline=f"{payload.product_name or payload.tea_type} · 天猫高端详情版",
                        selling_points=default_points[:3],
                        body_copy=f"围绕{screen.goal}，呈现真实茶叶质感与高级电商版面。",
                        parameter_copy=" / ".join([f"{k}:{v}" for k, v in payload.specs.items()][:4]),
                        cta_copy="收藏加购，随时开泡。",
                        notes="禁止夸大功效，包装文字需保持品牌识别一致。",
                    )
                )
        return rows

    def _build_prompt(self, payload: DetailPageJobCreatePayload, plan: DetailPagePlanPayload) -> str:
        """拼接模型文案生成提示词。"""

        screens = [f"{screen.screen_id}:{screen.theme}" for page in plan.pages for screen in page.screens]
        return (
            f"请为茶叶详情图生成结构化文案。品牌={payload.brand_name}，商品={payload.product_name}，"
            f"茶类={payload.tea_type}，平台={payload.platform}，风格={plan.global_style_anchor}，"
            f"屏幕列表={';'.join(screens)}。每屏输出字段：page_id,screen_id,headline,subheadline,"
            "selling_points,body_copy,parameter_copy,cta_copy,notes。"
        )

