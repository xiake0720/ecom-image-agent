"""文案生成节点。

文件位置：
- `src/workflows/nodes/generate_copy.py`

核心职责：
- 基于任务、商品分析和 shot plan 生成结构化 `CopyPlan`
- 在 provider 或 mock 产出之后做程序级归一化，确保最终文案适合 1440x1440 中文贴图
- 在进入 `overlay_text` 之前截断超长文案、清空不必要的 bullets/cta，并记录可观测日志
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re

from src.core.logging import summarize_text
from src.domain.copy_plan import CopyItem, CopyPlan
from src.domain.shot_plan import ShotPlan
from src.services.fallbacks.copy_fallback import build_default_copy_item_for_shot, merge_copy_plan_with_shots
from src.services.planning.copy_generator import build_mock_copy_plan
from src.workflows.nodes.cache_utils import (
    build_node_cache_key,
    hash_state_payload,
    is_force_rerun,
    planning_provider_identity,
    should_use_cache,
)
from src.workflows.nodes.prompt_utils import dump_pretty, load_prompt_text
from src.workflows.state import WorkflowDependencies, WorkflowState

logger = logging.getLogger(__name__)

TITLE_MAX_LENGTH = 18
SUBTITLE_MAX_LENGTH = 22
TITLE_PREFERRED_RANGE = (8, 14)
SUBTITLE_PREFERRED_RANGE = (8, 16)
POETIC_OR_DESCRIPTIVE_MARKERS = (
    "仿佛",
    "宛如",
    "像是",
    "让你",
    "带来",
    "呈现",
    "诠释",
    "演绎",
    "感受",
    "故事",
    "诗意",
    "氛围感",
)


@dataclass(frozen=True)
class CopyNormalizationReport:
    """单条文案归一化结果，供日志和测试复用。"""

    shot_id: str
    shot_type: str
    original_length: int
    normalized_length: int
    copy_shortened: bool
    brand_anchor_valid: bool


def generate_copy(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """生成并落盘结构化中文贴图文案。"""
    task = state["task"]
    shot_plan = state["shot_plan"]
    logs = [*state.get("logs", []), f"[generate_copy] start mode={deps.text_provider_mode}"]
    provider_name, provider_model_id = planning_provider_identity(deps)
    cache_key, cache_context = build_node_cache_key(
        node_name="generate_copy",
        state=state,
        deps=deps,
        prompt_filename="generate_copy.md" if deps.text_provider_mode == "real" else None,
        prompt_version="mock-copy-plan-v2" if deps.text_provider_mode != "real" else None,
        provider_name=provider_name,
        model_id=provider_model_id,
        extra_payload={
            "product_analysis_hash": hash_state_payload(state["product_analysis"]),
            "shot_plan_hash": hash_state_payload(shot_plan),
        },
    )

    if should_use_cache(state):
        cached_plan = deps.storage.load_cached_json_artifact("generate_copy", cache_key, CopyPlan)
        if cached_plan is not None:
            logs.append(f"[generate_copy] cache hit key={cache_key}")
            copy_plan = _finalize_copy_plan(
                copy_plan=cached_plan,
                shot_plan=shot_plan,
                task=task,
                product_analysis=state["product_analysis"],
                deps=deps,
                logs=logs,
                source_label="cache",
            )
            deps.storage.save_json_artifact(task.task_id, "copy_plan.json", copy_plan)
            if state.get("cache_enabled"):
                deps.storage.save_cached_json_artifact("generate_copy", cache_key, copy_plan, metadata=cache_context)
            logs.append("[generate_copy] restored copy_plan.json from cache")
            return {"copy_plan": copy_plan, "logs": logs}
        logs.append(f"[generate_copy] cache miss key={cache_key}")
    elif is_force_rerun(state):
        logs.append("[generate_copy] ignore cache forced rerun")

    if deps.text_provider_mode == "real":
        prompt = _build_copy_generation_prompt(
            task=task,
            product_analysis=state["product_analysis"],
            shot_plan=shot_plan,
        )
        copy_plan = deps.planning_provider.generate_structured(
            prompt,
            CopyPlan,
            system_prompt=load_prompt_text("generate_copy.md"),
        )
        source_label = "provider"
    else:
        copy_plan = build_mock_copy_plan(task, shot_plan)
        source_label = "mock"

    copy_plan = _finalize_copy_plan(
        copy_plan=copy_plan,
        shot_plan=shot_plan,
        task=task,
        product_analysis=state["product_analysis"],
        deps=deps,
        logs=logs,
        source_label=source_label,
    )

    deps.storage.save_json_artifact(task.task_id, "copy_plan.json", copy_plan)
    if state.get("cache_enabled"):
        deps.storage.save_cached_json_artifact("generate_copy", cache_key, copy_plan, metadata=cache_context)

    first_title = copy_plan.items[0].title if copy_plan.items else ""
    logs.extend(
        [
            f"[generate_copy] completed items={len(copy_plan.items)} first_title={first_title!r}",
            f"[generate_copy] planning_model={deps.planning_model_selection.model_id if deps.planning_model_selection else '-'}",
            "[generate_copy] saved copy_plan.json",
        ]
    )
    return {"copy_plan": copy_plan, "logs": logs}


def _build_copy_generation_prompt(*, task, product_analysis, shot_plan: ShotPlan) -> str:
    """构建 provider 用户 prompt，显式限制贴图文案长度、品牌和 shot 风格。"""
    copy_contract = {
        "title_rule": "8~14 个中文字符优先，最长不超过 18。",
        "subtitle_rule": "8~16 个中文字符优先，最长不超过 22。",
        "bullets_rule": "默认留空，除非当前 shot 明确必须用列表。",
        "cta_rule": "默认关闭，不要主动生成 CTA。",
        "brand_rule": "只能使用输入里可确认的信息，不得创造新的品牌名、系列名或 slogan。",
        "style_rule": "短句、可贴图、适合 1440x1440 中文叠字，不要散文、诗句、解释句。",
        "allowed_brand_anchors": _collect_allowed_brand_anchors(task=task, product_analysis=product_analysis),
        "shot_copy_rules": [
            {
                "shot_id": shot.shot_id,
                "shot_type": shot.shot_type,
                "copy_style_rule": _copy_style_rule_for_shot_type(shot.shot_type),
            }
            for shot in shot_plan.shots
        ],
    }
    return (
        "请基于任务信息、商品分析和图组规划，为每个 shot 生成一条结构化中文贴图文案。\n"
        "只生成 CopyPlan，不要重新规划图组，不要输出布局建议，不要输出解释性文字。\n"
        "只允许使用输入中可确认的信息，不得创造新的品牌名、系列名、虚构 slogan 或包装上没有的品牌锚点。\n"
        f"贴图文案合同:\n{dump_pretty(copy_contract)}\n\n"
        f"任务信息:\n{dump_pretty(task)}\n\n"
        f"商品分析:\n{dump_pretty(product_analysis)}\n\n"
        f"图组规划:\n{dump_pretty(shot_plan)}"
    )


def _finalize_copy_plan(
    *,
    copy_plan: CopyPlan,
    shot_plan: ShotPlan,
    task,
    product_analysis,
    deps: WorkflowDependencies,
    logs: list[str],
    source_label: str,
) -> CopyPlan:
    """合并 fallback 后做贴图归一化，避免长文案直接透传到叠字链路。"""
    provider_status = getattr(deps.planning_provider, "last_response_status_code", None)
    provider_metadata = getattr(deps.planning_provider, "last_response_metadata", {}) or {}
    parsed_summary = summarize_text(str(copy_plan.model_dump(mode="json")), limit=240)
    logger.info(
        "generate_copy %s summary: provider_status=%s, provider_metadata=%s, parsed_copy_plan=%s",
        source_label,
        provider_status,
        provider_metadata,
        parsed_summary,
    )
    logs.append(
        f"[generate_copy] {source_label} structured_result status={provider_status or '-'} summary={parsed_summary}"
    )

    merge_result = merge_copy_plan_with_shots(copy_plan, shot_plan.shots)
    if merge_result.original_count == 0:
        logs.append("[generate_copy] warning: parsed CopyPlan.items=0, fallback copy items applied")
    if merge_result.unexpected_shot_ids:
        logs.append(
            "[generate_copy] warning: unexpected shot_ids ignored="
            f"{', '.join(merge_result.unexpected_shot_ids)}"
        )
    if merge_result.duplicate_shot_ids:
        logs.append(
            "[generate_copy] warning: duplicate shot_ids ignored="
            f"{', '.join(merge_result.duplicate_shot_ids)}"
        )
    if merge_result.fallback_added_count > 0:
        logs.append(
            "[generate_copy] warning: fallback copy added missing_shot_ids="
            f"{', '.join(merge_result.missing_shot_ids)} added={merge_result.fallback_added_count}"
        )

    normalized_plan, normalization_reports = _normalize_copy_plan_for_overlay(
        copy_plan=merge_result.plan,
        shot_plan=shot_plan,
        task=task,
        product_analysis=product_analysis,
    )
    for report in normalization_reports:
        logs.append(
            (
                "[generate_copy] normalized_copy "
                f"shot_id={report.shot_id} "
                f"shot_type={report.shot_type} "
                f"original_length={report.original_length} "
                f"normalized_length={report.normalized_length} "
                f"copy_shortened={str(report.copy_shortened).lower()} "
                f"brand_anchor_valid={str(report.brand_anchor_valid).lower()}"
            )
        )

    final_summary = summarize_text(str(normalized_plan.model_dump(mode="json")), limit=240)
    logger.info(
        "generate_copy normalized copy plan: original_items=%s, fallback_added=%s, final_items=%s, summary=%s",
        merge_result.original_count,
        merge_result.fallback_added_count,
        len(normalized_plan.items),
        final_summary,
    )
    logs.append(
        "[generate_copy] CopyPlan normalized "
        f"original_items={merge_result.original_count} "
        f"fallback_added={merge_result.fallback_added_count} "
        f"final_items={len(normalized_plan.items)}"
    )
    return normalized_plan


def _normalize_copy_plan_for_overlay(*, copy_plan: CopyPlan, shot_plan: ShotPlan, task, product_analysis) -> tuple[CopyPlan, list[CopyNormalizationReport]]:
    """把模型文案收敛成适合 1440x1440 中文贴图的短版 CopyPlan。"""
    shot_map = {shot.shot_id: shot for shot in shot_plan.shots}
    reports: list[CopyNormalizationReport] = []
    normalized_items: list[CopyItem] = []
    for item in copy_plan.items:
        shot = shot_map[item.shot_id]
        normalized_item, report = _normalize_copy_item(
            item=item,
            shot=shot,
            task=task,
            product_analysis=product_analysis,
        )
        normalized_items.append(normalized_item)
        reports.append(report)
    return CopyPlan(items=normalized_items), reports


def _normalize_copy_item(*, item: CopyItem, shot, task, product_analysis) -> tuple[CopyItem, CopyNormalizationReport]:
    """单条文案归一化：短句化、去散文化、去品牌漂移，并清空不必要 bullets/cta。"""
    original_length = _copy_item_length(item)
    brand_anchor_valid = _validate_brand_anchor(item=item, task=task, product_analysis=product_analysis)
    fallback_item = build_default_copy_item_for_shot(shot, task=task, product_analysis=product_analysis)
    normalized_item = CopyItem(
        shot_id=item.shot_id,
        title=_normalize_copy_text_field(
            raw_text=item.title,
            fallback_text=fallback_item.title,
            max_length=TITLE_MAX_LENGTH,
            preferred_range=TITLE_PREFERRED_RANGE,
            brand_anchor_valid=brand_anchor_valid,
        ),
        subtitle=_normalize_copy_text_field(
            raw_text=item.subtitle,
            fallback_text=fallback_item.subtitle,
            max_length=SUBTITLE_MAX_LENGTH,
            preferred_range=SUBTITLE_PREFERRED_RANGE,
            brand_anchor_valid=brand_anchor_valid,
        ),
        bullets=[],
        cta=None,
    )
    report = CopyNormalizationReport(
        shot_id=item.shot_id,
        shot_type=shot.shot_type,
        original_length=original_length,
        normalized_length=_copy_item_length(normalized_item),
        copy_shortened=normalized_item != item,
        brand_anchor_valid=brand_anchor_valid,
    )
    return normalized_item, report


def _normalize_copy_text_field(
    *,
    raw_text: str,
    fallback_text: str,
    max_length: int,
    preferred_range: tuple[int, int],
    brand_anchor_valid: bool,
) -> str:
    """把单个 title/subtitle 收敛成适合贴图的短句。"""
    cleaned = _clean_copy_text(raw_text)
    if not brand_anchor_valid:
        cleaned = ""
    if cleaned and _looks_like_overlay_copy(cleaned, max_length=max_length):
        shortened = _shorten_copy_text(cleaned, max_length=max_length)
        if _text_length(shortened) <= max_length:
            return shortened
    fallback_clean = _shorten_copy_text(_clean_copy_text(fallback_text), max_length=max_length)
    if _text_length(fallback_clean) >= preferred_range[0]:
        return fallback_clean
    return fallback_clean[:max_length]


def _clean_copy_text(value: str) -> str:
    """清理换行、标点和解释语气，保留更适合贴图的短句主体。"""
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"[“”\"'《》「」]", "", text)
    text = re.split(r"[。！？；\n]", text, maxsplit=1)[0]
    if _text_length(text) > SUBTITLE_MAX_LENGTH:
        text = re.split(r"[，、：:]", text, maxsplit=1)[0]
    text = text.replace("/", " ").replace("|", " ").replace("-", " ")
    text = re.sub(r"\s+", "", text)
    return text.strip()


def _looks_like_overlay_copy(text: str, *, max_length: int) -> bool:
    """判断文案是否已经足够像电商贴图短文案。"""
    if not text:
        return False
    if _text_length(text) > max_length:
        return False
    return not any(marker in text for marker in POETIC_OR_DESCRIPTIVE_MARKERS)


def _shorten_copy_text(text: str, *, max_length: int) -> str:
    """优先按短句切分缩短，避免直接把长句完整透传到 overlay_text。"""
    if _text_length(text) <= max_length:
        return text
    for separator in ("，", "。", "；", "：", " ", "、"):
        if separator in text:
            candidate = text.split(separator, maxsplit=1)[0].strip()
            if candidate and _text_length(candidate) <= max_length:
                return candidate
    return text[:max_length]


def _validate_brand_anchor(*, item: CopyItem, task, product_analysis) -> bool:
    """用轻量启发式检测是否出现输入中没有的品牌锚点或虚构 slogan。"""
    combined_text = "".join([item.title or "", item.subtitle or "", "".join(item.bullets or []), item.cta or ""])
    if not combined_text.strip():
        return True
    if re.search(r"[“\"'《「].{2,12}[”\"'》」]", combined_text):
        return False
    allowed_anchors = _collect_allowed_brand_anchors(task=task, product_analysis=product_analysis)
    allowed_anchor_lower = {anchor.lower() for anchor in allowed_anchors}
    english_tokens = re.findall(r"[A-Za-z][A-Za-z0-9&\\-]{1,20}", combined_text)
    if any(token.lower() not in allowed_anchor_lower for token in english_tokens):
        return False
    series_matches = re.findall(r"([A-Za-z0-9\u4e00-\u9fff]{2,16})(系列|品牌|出品)", combined_text)
    for candidate, _label in series_matches:
        if candidate.lower() not in allowed_anchor_lower and candidate not in allowed_anchors:
            return False
    return True


def _collect_allowed_brand_anchors(*, task, product_analysis) -> list[str]:
    """收集允许出现在贴图文案里的品牌锚点来源。"""
    values = [
        getattr(task, "brand_name", ""),
        getattr(task, "product_name", ""),
        *list(getattr(product_analysis, "must_preserve_texts", []) or []),
    ]
    anchors: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in anchors:
            continue
        anchors.append(text)
    return anchors


def _copy_item_length(item: CopyItem) -> int:
    """统计一条文案的可见字符总长度，便于记录归一化前后差异。"""
    return sum(_text_length(text) for text in [item.title, item.subtitle, "".join(item.bullets or []), item.cta or ""])


def _text_length(text: str) -> int:
    """按去空白后的可见字符长度做贴图文案长度判断。"""
    return len(re.sub(r"\s+", "", str(text or "")))


def _copy_style_rule_for_shot_type(shot_type: str) -> str:
    """给 prompt 和 fallback 共用的 shot-specific 文案风格规则。"""
    rules = {
        "hero_brand": "品牌感+品类信息+简洁价值点，不能写成首图 slogan 或散文。",
        "package_detail": "强调材质、工艺、结构细节，不能像 hero 口号。",
        "dry_leaf_detail": "强调原料、条索、干茶纹理和质感。",
        "tea_soup_experience": "强调汤色、口感、饮用体验，不能回到包装介绍。",
        "lifestyle_or_brewing_context": "强调场景体验、日常饮用氛围和冲泡感。",
        "package_in_brewing_context": "强调包装进入冲泡场景后的完整画面感。",
        "label_or_material_detail": "强调材质、纹理、印刷或标签结构的近景卖点。",
        "package_with_leaf_hint": "强调包装主体加轻度茶叶暗示，文案不要写成原料图。",
        "open_box_structure": "强调开盒层次、结构清晰和取用逻辑。",
        "carry_action": "强调轻松提拿、携带和礼赠体面感。",
    }
    return rules.get(shot_type, "短句表达核心卖点，适合中文贴图叠字。")
