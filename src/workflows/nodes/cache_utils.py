"""节点缓存辅助工具。"""

from __future__ import annotations

from typing import Any

from src.core.hash_utils import build_cache_key, hash_assets, hash_payload, hash_task_core_params
from src.workflows.nodes.prompt_utils import load_prompt_text
from src.workflows.state import WorkflowDependencies, WorkflowState


def should_use_cache(state: WorkflowState) -> bool:
    """返回当前节点是否应启用缓存。"""

    return bool(state.get("cache_enabled", False)) and not bool(state.get("ignore_cache", False))


def is_force_rerun(state: WorkflowState) -> bool:
    """返回当前节点是否强制忽略缓存。"""

    return bool(state.get("cache_enabled", False)) and bool(state.get("ignore_cache", False))


def build_node_cache_context(
    *,
    node_name: str,
    state: WorkflowState,
    deps: WorkflowDependencies,
    prompt_filename: str | None = None,
    prompt_version: str | None = None,
    provider_name: str,
    model_id: str,
    extra_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造节点缓存上下文。"""

    cache_context: dict[str, Any] = {
        "node_name": node_name,
        "assets_hash": hash_assets(state.get("assets", [])),
        "task_core_params_hash": hash_task_core_params(state["task"]),
        "prompt_version": prompt_version or resolve_prompt_version(prompt_filename),
        "provider_name": provider_name,
        "model_id": model_id,
    }
    if extra_payload:
        cache_context.update(extra_payload)
    return cache_context


def build_node_cache_key(**kwargs: Any) -> tuple[str, dict[str, Any]]:
    """根据缓存上下文生成稳定 key。"""

    context = build_node_cache_context(**kwargs)
    return build_cache_key(context), context


def resolve_prompt_version(prompt_filename: str | None) -> str:
    """把 prompt 模板解析成稳定版本标识。"""

    if not prompt_filename:
        return "no-prompt-template"
    return hash_payload({"prompt_filename": prompt_filename, "prompt_text": load_prompt_text(prompt_filename)})


def planning_provider_identity(deps: WorkflowDependencies) -> tuple[str, str]:
    """返回规划 provider 名称与模型标识。"""

    provider_name = deps.planning_provider_name or deps.planning_provider.__class__.__name__
    model_id = deps.planning_model_selection.model_id if deps.planning_model_selection else deps.text_provider_mode
    return provider_name, model_id


def hash_state_payload(payload: object) -> str:
    """对任意结构化 payload 计算稳定哈希。"""

    return hash_payload(payload)
