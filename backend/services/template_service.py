"""模板查询服务。"""

from __future__ import annotations

import json
from pathlib import Path

from backend.core.config import get_settings


class TemplateService:
    """读取主图与详情页模板配置。"""

    def __init__(self) -> None:
        self.settings = get_settings()

    def list_detail_templates(self) -> list[dict[str, object]]:
        """加载详情页模板。

        输出：模板列表，每项包含平台、风格、模块约束。
        """

        template_dir = self.settings.template_root / "detail_pages"
        rows: list[dict[str, object]] = []
        for path in sorted(template_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["template_file"] = str(path)
            rows.append(payload)
        return rows

    def list_main_templates(self) -> list[dict[str, object]]:
        """返回主图模板占位配置。"""

        return [
            {"name": "tea_default_tmall", "platform": "tmall", "style": "premium"},
            {"name": "tea_convert_pdd", "platform": "pinduoduo", "style": "value"},
        ]
