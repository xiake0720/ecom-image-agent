from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


POLICIES_DIR = Path(__file__).resolve().parents[2] / "policies"
CATEGORY_POLICIES_DIR = POLICIES_DIR / "categories"
SHOT_TYPE_POLICIES_DIR = POLICIES_DIR / "shot_types"
PLATFORM_POLICIES_DIR = POLICIES_DIR / "platforms"


def describe_policy_source(kind: str, name: str) -> str:
    return _resolve_policy_path(kind, name).as_posix()


@lru_cache(maxsize=None)
def load_category_policy(category_family: str) -> dict[str, Any]:
    return _load_policy_or_default("categories", category_family)


@lru_cache(maxsize=None)
def load_shot_type_policy(shot_type: str) -> dict[str, Any]:
    return _load_policy_or_default("shot_types", shot_type)


@lru_cache(maxsize=None)
def load_platform_policy(platform: str) -> dict[str, Any]:
    return _load_policy_or_default("platforms", platform)


def _load_policy_or_default(kind: str, name: str) -> dict[str, Any]:
    try:
        return _load_policy(kind, name)
    except FileNotFoundError:
        return {
            "name": name,
            "enabled": False,
            "notes": [f"{kind}:{name} policy not found"],
        }


def _load_policy(kind: str, name: str) -> dict[str, Any]:
    path = _resolve_policy_path(kind, name)
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Policy file must contain a mapping: {path}")
    payload.setdefault("source", path.as_posix())
    return payload


def _resolve_policy_path(kind: str, name: str) -> Path:
    normalized = str(name or "").strip().lower()
    if kind == "categories":
        return CATEGORY_POLICIES_DIR / f"{normalized}.yaml"
    if kind == "shot_types":
        return SHOT_TYPE_POLICIES_DIR / f"{normalized}.yaml"
    if kind == "platforms":
        return PLATFORM_POLICIES_DIR / f"{normalized}.yaml"
    raise ValueError(f"Unsupported policy kind: {kind}")
