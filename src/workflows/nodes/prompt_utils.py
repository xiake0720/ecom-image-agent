"""Workflow prompt 辅助模块。

该模块位于 `src/workflows/nodes/`，提供：
- prompt 文件加载
- 结构化对象的调试输出格式化

它不负责业务判断，只用于让节点中的 prompt 组装更清晰、可读。
"""

from __future__ import annotations

import json
from pathlib import Path


def load_prompt_text(filename: str) -> str:
    """读取 `src/prompts/` 下的 prompt 文本。"""
    return Path("src/prompts", filename).read_text(encoding="utf-8").strip()


def dump_pretty(payload: object) -> str:
    """将 Pydantic 对象或普通对象格式化为可读 JSON 字符串。"""
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False, indent=2)
