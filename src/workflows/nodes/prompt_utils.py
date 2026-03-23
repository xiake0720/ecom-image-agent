"""Workflow prompt 辅助模块。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def resolve_prompt_path(filename: str) -> Path:
    """解析 prompt 文件路径。"""
    candidate = PROMPTS_DIR / filename
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Prompt file not found: {filename}")


def describe_prompt_source(filename: str) -> str:
    return resolve_prompt_path(filename).as_posix()


@lru_cache(maxsize=None)
def load_prompt_text(filename: str) -> str:
    return resolve_prompt_path(filename).read_text(encoding="utf-8").strip()


def dump_pretty(payload: object) -> str:
    return json.dumps(_to_jsonable(payload), ensure_ascii=False, indent=2)


def _to_jsonable(payload: object) -> object:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    if isinstance(payload, dict):
        return {str(key): _to_jsonable(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_to_jsonable(item) for item in payload]
    return payload
