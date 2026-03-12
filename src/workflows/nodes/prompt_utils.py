"""Workflow prompt 辅助模块。

该模块位于 `src/workflows/nodes/`，提供：
- prompt 文件加载
- 结构化对象的调试输出格式化

它不负责业务判断，只用于让节点中的 prompt 组装更清晰、可读。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def resolve_prompt_path(filename: str) -> Path:
    """解析 `src/prompts/` 下的 prompt 文件路径。"""
    return PROMPTS_DIR / filename


def describe_prompt_source(filename: str) -> str:
    """返回 prompt 文件的可读来源路径。"""
    return resolve_prompt_path(filename).as_posix()


@lru_cache(maxsize=None)
def load_prompt_text(filename: str) -> str:
    """读取 `src/prompts/` 下的 prompt 文本。"""
    return resolve_prompt_path(filename).read_text(encoding="utf-8").strip()


def dump_pretty(payload: object) -> str:
    """将 Pydantic 对象或普通对象格式化为可读 JSON 字符串。"""
    return json.dumps(_to_jsonable(payload), ensure_ascii=False, indent=2)


def _to_jsonable(payload: object) -> object:
    """递归把 Pydantic 对象、列表和字典转为可 JSON 序列化结构。"""
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    if isinstance(payload, dict):
        return {str(key): _to_jsonable(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_to_jsonable(item) for item in payload]
    return payload
