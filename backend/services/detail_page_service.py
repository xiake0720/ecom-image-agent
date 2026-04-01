"""详情页结构化生成服务。"""

from __future__ import annotations

import json
from pathlib import Path

from backend.core.config import get_settings
from backend.core.exceptions import AppException
from backend.repositories.task_repository import TaskRepository
from backend.schemas.task import DetailPageGenerateRequest, DetailPageGenerateResponse
from backend.services.template_service import TemplateService
from backend.engine.services.storage.local_storage import LocalStorageService


class DetailPageService:
    """根据模板和商品数据生成详情页模块。

    设计意图：
    - 第一阶段输出结构化 JSON 与可预览模块数组；
    - 模块组装逻辑与模板文件解耦，避免写死在前端。
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.template_service = TemplateService()
        self.storage = LocalStorageService()
        self.repo = TaskRepository()

    def generate(self, payload: DetailPageGenerateRequest) -> DetailPageGenerateResponse:
        """生成详情页结构化结果。"""

        template = self._resolve_template(payload.platform, payload.style)
        task_id = self.storage.create_task_id()
        task_dirs = self.storage.prepare_task_dirs(task_id)

        modules: list[dict[str, object]] = []
        for module in template["modules"]:
            module_id = module["id"]
            modules.append(
                {
                    "id": module_id,
                    "name": module["name"],
                    "layout": module["layout"],
                    "copy": self._build_module_copy(module_id, payload),
                    "assets": self._build_module_assets(module_id, payload),
                }
            )

        output = {
            "platform": payload.platform,
            "style": payload.style,
            "title": payload.title,
            "subtitle": payload.subtitle,
            "modules": modules,
            "template_meta": {"name": template["name"], "version": template["version"]},
        }
        module_file = task_dirs["task"] / "detail_page_modules.json"
        module_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

        export_assets = [
            {"type": "json", "path": str(module_file)},
            {"type": "images", "path": str(task_dirs["final"])},
        ]

        summary = self.repo.create_task_summary(
            task_id=task_id,
            task_type="detail_page",
            status="completed",
            title=payload.title,
            platform=payload.platform,
            result_path=str(module_file),
        )
        self.repo.save_task(summary)

        return DetailPageGenerateResponse(
            task_id=task_id,
            module_config_path=str(module_file),
            preview_data=output,
            export_assets=export_assets,
            modules=modules,
        )

    def _resolve_template(self, platform: str, style: str) -> dict[str, object]:
        """根据平台+风格匹配模板，找不到时抛中文业务错误。"""

        for item in self.template_service.list_detail_templates():
            if item.get("platform") == platform and item.get("style") == style:
                return item
        raise AppException(f"未找到平台={platform}、风格={style} 的详情页模板", code=4040)

    def _build_module_copy(self, module_id: str, payload: DetailPageGenerateRequest) -> str:
        """按模块类型填充默认文案。"""

        map_copy = {
            "top_banner": payload.selling_points[0] if payload.selling_points else payload.title,
            "hero": payload.title,
            "core_selling_points": "；".join(payload.selling_points[:5]) or "核心卖点待补充",
            "tea_showcase": "茶汤、茶干、叶底、包装四维展示",
            "specs": " / ".join([f"{x.get('name')}:{x.get('value')}" for x in payload.specs]) or "规格待补充",
            "scenes": "办公、居家、会客等多场景适饮",
            "brew_guide": "建议95℃热水，前两泡快速出汤",
            "audience": "自饮、送礼、老茶客皆宜",
            "quality": "原料可追溯，工艺可说明",
            "delivery": "现货48小时内发货，支持破损补寄",
        }
        return map_copy.get(module_id, "")

    def _build_module_assets(self, module_id: str, payload: DetailPageGenerateRequest) -> list[str]:
        """按模块类型绑定素材引用。

        输入：模块标识 + 详情请求。
        输出：该模块建议引用的图片路径列表。
        """

        if module_id in {"hero", "tea_showcase"}:
            return payload.main_images[:3] + payload.product_images[:3]
        return payload.product_images[:1]
