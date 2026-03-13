"""统一哈希工具。

用于：
- 生成稳定 JSON 哈希
- 生成素材哈希
- 生成任务核心参数哈希
- 组合节点缓存 key
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def to_jsonable(payload: object) -> object:
    """递归将对象转为可稳定序列化的结构。"""
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    if isinstance(payload, dict):
        return {str(key): to_jsonable(value) for key, value in sorted(payload.items(), key=lambda item: str(item[0]))}
    if isinstance(payload, (list, tuple)):
        return [to_jsonable(item) for item in payload]
    if isinstance(payload, Path):
        return str(payload)
    return payload


def stable_json_dumps(payload: object) -> str:
    """输出稳定排序的 JSON 文本。"""
    return json.dumps(to_jsonable(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def hash_text(value: str) -> str:
    """对文本计算 sha256。"""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_payload(payload: object) -> str:
    """对任意结构化对象计算稳定哈希。"""
    return hash_text(stable_json_dumps(payload))


def hash_file(path: str | Path) -> str:
    """对文件内容计算 sha256。"""
    file_path = Path(path)
    if not file_path.exists():
        return f"missing:{file_path.name}"
    hasher = hashlib.sha256()
    with file_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def hash_assets(assets: list[object]) -> str:
    """对上传素材列表计算稳定哈希。"""
    normalized = []
    for asset in assets:
        item = to_jsonable(asset)
        if isinstance(item, dict) and item.get("local_path"):
            item["file_hash"] = hash_file(str(item["local_path"]))
        normalized.append(item)
    return hash_payload(normalized)


def hash_task_core_params(task: object) -> str:
    """对任务核心参数计算哈希，排除 task_id / created_at / status / task_dir。"""
    normalized = to_jsonable(task)
    if isinstance(normalized, dict):
        core_fields = {
            "brand_name": normalized.get("brand_name"),
            "product_name": normalized.get("product_name"),
            "category": normalized.get("category"),
            "platform": normalized.get("platform"),
            "output_size": normalized.get("output_size"),
            "shot_count": normalized.get("shot_count"),
            "copy_tone": normalized.get("copy_tone"),
        }
        return hash_payload(core_fields)
    return hash_payload(normalized)


def build_cache_key(parts: dict[str, Any]) -> str:
    """基于已归一化字段构造缓存 key。"""
    return hash_payload(parts)
