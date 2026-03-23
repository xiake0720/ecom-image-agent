"""商品分析节点。

文件位置：
- `src/workflows/nodes/analyze_product.py`

核心职责：
- 选择用于分析的参考图
- 调用视觉分析 provider 或 mock 规则
- 输出 `product_analysis.json`

节点前后关系：
- 上游节点：`ingest_assets`
- 下游节点：`style_director`

关键输入/输出：
- 输入：`task`、`assets`
- 输出：`product_analysis` 及分析用参考图调试字段
"""

from __future__ import annotations

import logging
<<<<<<< HEAD
=======
import re
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c

from src.core.config import get_settings
from src.domain.product_analysis import ProductAnalysis
from src.services.analysis.product_analyzer import build_mock_product_analysis
from src.services.assets.reference_selector import ReferenceSelection, select_reference_bundle
from src.services.planning.tea_shot_planner import resolve_tea_package_template_family
from src.workflows.nodes.cache_utils import (
    build_node_cache_key,
    is_force_rerun,
    should_use_cache,
    vision_provider_identity,
)
from src.workflows.nodes.prompt_utils import dump_pretty, load_prompt_text
from src.workflows.state import WorkflowDependencies, WorkflowState, format_connected_contract_logs

logger = logging.getLogger(__name__)

<<<<<<< HEAD
=======
TEXT_ANCHOR_MAX_COUNT = 5
_TEXT_ANCHOR_INVALID_TOKENS = {"", "none", "null", "n/a", "-", "unknown"}
_TEXT_ANCHOR_STATUS_MARKERS = {
    "unreadable": "unreadable",
    "uncertain": "uncertain",
    "无法识别": "unreadable",
    "看不清": "unreadable",
    "不可辨认": "unreadable",
    "不确定": "uncertain",
    "unclear": "uncertain",
    "blurry": "uncertain",
}
_VISUAL_STRUCTURE_MARKERS = (
    "package",
    "label",
    "layout",
    "zone",
    "position",
    "placement",
    "mark",
    "silhouette",
    "structure",
    "container",
    "background",
    "props",
    "hero",
    "轮廓",
    "标签",
    "标识区",
    "标签区",
    "区域",
    "位置",
    "结构",
    "版式",
    "留白",
    "背景",
    "主体",
    "材质",
    "纹理",
)
_TEXT_HINT_MARKERS = (
    "品牌",
    "品名",
    "产品名",
    "净含量",
    "含量",
    "系列",
    "香型",
    "口味",
    "单丛",
    "乌龙",
    "红茶",
    "绿茶",
    "白茶",
    "茶",
)
_TEXT_ANCHOR_UNIT_PATTERN = re.compile(r"\d+(?:\.\d+)?\s*(?:g|kg|ml|l|克|千克|毫升|升|袋|盒|罐|片|capsules?)", re.IGNORECASE)
_LATIN_TOKEN_PATTERN = re.compile(r"[A-Za-z]")

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c

def analyze_product(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """生成并落盘商品分析结果。

    参数：
    - state：当前 workflow 状态，必须包含 `task` 和 `assets`
    - deps：依赖注入对象，内部提供视觉分析 provider 和 storage

    返回值：
    - 包含 `product_analysis` 以及参考图选择调试字段的字典

    关键副作用：
    - 调用真实视觉分析 provider 或 mock 分析逻辑
    - 写入 `product_analysis.json`
    - 记录参考图选择日志，便于后续排查“主图为什么选错”
    """
    task = state["task"]
    logs = [*state.get("logs", []), f"[analyze_product] start mode={deps.vision_provider_mode}"]
    provider_name, provider_model_id = vision_provider_identity(deps)
    selection = _select_analysis_assets(state)
    selected_assets = selection.selected_assets
    selected_asset_ids = selection.selected_asset_ids
    cache_key, cache_context = build_node_cache_key(
        node_name="analyze_product",
        state=state,
        deps=deps,
        prompt_filename="analyze_product.md" if deps.vision_provider_mode == "real" else None,
        prompt_version="mock-product-analysis-v1" if deps.vision_provider_mode != "real" else None,
        provider_name=provider_name,
        model_id=provider_model_id,
        extra_payload={
            "selected_asset_ids": selected_asset_ids,
            "analyze_max_reference_images": _resolve_analyze_max_reference_images(state),
        },
    )
    logs.extend(_format_selection_logs(node_name="analyze_product", selection=selection))

    if should_use_cache(state):
        cached_analysis = deps.storage.load_cached_json_artifact("analyze_product", cache_key, ProductAnalysis)
        if cached_analysis is not None:
<<<<<<< HEAD
            deps.storage.save_json_artifact(task.task_id, "product_analysis.json", cached_analysis)
=======
            cached_analysis = _normalize_product_lock_fields(
                cached_analysis.model_copy(
                    update={
                        "source_asset_ids": selected_asset_ids or cached_analysis.source_asset_ids,
                        "asset_completeness_mode": cached_analysis.asset_completeness_mode or selection.asset_completeness_mode,
                    }
                )
            )
            deps.storage.save_json_artifact(task.task_id, "product_analysis.json", cached_analysis)
            logs.extend(_format_text_anchor_logs(node_name="analyze_product", analysis=cached_analysis))
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
            logs.extend(
                [
                    f"[analyze_product] cache hit key={cache_key}",
                    f"[cache] node=analyze_product status=hit key={cache_key}",
                    "[analyze_product] restored cached product_analysis.json",
                ]
            )
            return {
                "product_analysis": cached_analysis,
                "product_lock": cached_analysis,
                "analyze_reference_asset_ids": selected_asset_ids,
                "analyze_selected_main_asset_id": selection.selected_main_asset_id,
                "analyze_selected_detail_asset_id": selection.selected_detail_asset_id,
<<<<<<< HEAD
=======
                "analyze_asset_completeness_mode": selection.asset_completeness_mode,
                "analyze_text_anchor_source": cached_analysis.text_anchor_source,
                "analyze_text_anchor_count": len(cached_analysis.must_preserve_texts),
                "analyze_extracted_text_anchors": list(cached_analysis.must_preserve_texts),
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
                "analyze_reference_selection_reason": selection.selection_reason,
                "logs": [*logs, *format_connected_contract_logs({"product_analysis": cached_analysis, "product_lock": cached_analysis}, node_name="analyze_product")],
            }
        logs.extend(
            [
                f"[analyze_product] cache miss key={cache_key}",
                f"[cache] node=analyze_product status=miss key={cache_key}",
            ]
        )
    elif is_force_rerun(state):
        logs.extend(
            [
                "[analyze_product] ignore cache requested",
                "[cache] node=analyze_product status=ignored key=-",
            ]
        )

    if deps.vision_provider_mode == "real":
        assets_payload = [
            {
                "asset_id": asset.asset_id,
                "filename": asset.filename,
                "asset_type": asset.asset_type.value,
                "width": asset.width,
                "height": asset.height,
                "tags": asset.tags,
            }
            for asset in selected_assets
        ]
        prompt = (
            "请基于当前上传商品图做 SKU 级视觉分析，并输出结构化商品分析结果。\n"
            f"任务信息:\n{dump_pretty(task)}\n\n"
            f"素材信息:\n{dump_pretty(assets_payload)}"
        )
        if deps.vision_analysis_provider is None:
            raise RuntimeError("Vision provider is required when ECOM_IMAGE_AGENT_VISION_PROVIDER_MODE=real.")
        analysis = deps.vision_analysis_provider.generate_structured_from_assets(
            prompt,
            ProductAnalysis,
            assets=selected_assets,
            system_prompt=load_prompt_text("analyze_product.md"),
        )
<<<<<<< HEAD
        analysis = _normalize_product_lock_fields(analysis.model_copy(update={"source_asset_ids": selected_asset_ids}))
    else:
        analysis = build_mock_product_analysis(state.get("assets", []), task.product_name)
        analysis = _normalize_product_lock_fields(analysis.model_copy(update={"source_asset_ids": selected_asset_ids}))
=======
        analysis = _normalize_product_lock_fields(
            analysis.model_copy(
                update={
                    "source_asset_ids": selected_asset_ids,
                    "asset_completeness_mode": selection.asset_completeness_mode,
                }
            )
        )
    else:
        analysis = build_mock_product_analysis(state.get("assets", []), task.product_name)
        analysis = _normalize_product_lock_fields(
            analysis.model_copy(
                update={
                    "source_asset_ids": selected_asset_ids,
                    "asset_completeness_mode": selection.asset_completeness_mode,
                }
            )
        )
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c

    deps.storage.save_json_artifact(task.task_id, "product_analysis.json", analysis)
    if state.get("cache_enabled"):
        deps.storage.save_cached_json_artifact("analyze_product", cache_key, analysis, metadata=cache_context)
<<<<<<< HEAD
=======
    logs.extend(_format_text_anchor_logs(node_name="analyze_product", analysis=analysis))
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    logs.extend(
        [
            (
                "[analyze_product] completed "
                f"category={analysis.category} "
                f"subcategory={analysis.subcategory} "
                f"product_form={analysis.product_form} "
                f"package_template_family={analysis.package_template_family or '-'} "
<<<<<<< HEAD
=======
                f"asset_completeness_mode={analysis.asset_completeness_mode or '-'} "
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
                f"must_preserve={len(analysis.visual_identity.must_preserve)}"
            ),
            f"[analyze_product] vision_model={deps.vision_model_selection.model_id if deps.vision_model_selection else '-'}",
            "[analyze_product] saved product_analysis.json",
        ]
    )
    logs.extend(format_connected_contract_logs({"product_analysis": analysis, "product_lock": analysis}, node_name="analyze_product"))
    return {
        "product_analysis": analysis,
        "product_lock": analysis,
        "analyze_reference_asset_ids": selected_asset_ids,
        "analyze_selected_main_asset_id": selection.selected_main_asset_id,
        "analyze_selected_detail_asset_id": selection.selected_detail_asset_id,
<<<<<<< HEAD
=======
        "analyze_asset_completeness_mode": selection.asset_completeness_mode,
        "analyze_text_anchor_source": analysis.text_anchor_source,
        "analyze_text_anchor_count": len(analysis.must_preserve_texts),
        "analyze_extracted_text_anchors": list(analysis.must_preserve_texts),
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        "analyze_reference_selection_reason": selection.selection_reason,
        "logs": logs,
    }


def _resolve_analyze_max_reference_images(state: WorkflowState) -> int:
    """解析分析阶段可使用的参考图数量上限。"""
    explicit_value = state.get("analyze_max_reference_images")
    if explicit_value is not None:
        return max(1, int(explicit_value))
    return max(1, int(get_settings().analyze_max_reference_images))


def _select_analysis_assets(state: WorkflowState) -> ReferenceSelection:
    """分析阶段和渲染阶段共用同一套参考图选择规则。"""
    return select_reference_bundle(
        state.get("assets", []),
        max_images=_resolve_analyze_max_reference_images(state),
    )


def _format_selection_logs(*, node_name: str, selection: ReferenceSelection) -> list[str]:
    """统一输出参考图选择日志，便于 UI 和任务日志同时查看。"""
    return [
        (
            f"[{node_name}] selected_main_asset_id={selection.selected_main_asset_id or '-'} "
            f"selected_detail_asset_id={selection.selected_detail_asset_id or '-'} "
<<<<<<< HEAD
=======
            f"asset_completeness_mode={selection.asset_completeness_mode} "
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
            f"selected_reference_asset_ids={selection.selected_asset_ids or []}"
        ),
        f"[{node_name}] selection_reason={selection.selection_reason}",
    ]


<<<<<<< HEAD
=======
def _format_text_anchor_logs(*, node_name: str, analysis: ProductAnalysis) -> list[str]:
    """统一输出文字锚点提取结果，便于后续排查 OCR/QC 为什么拿不到有效文字证据。"""
    logs = [
        (
            f"[{node_name}] extracted_text_anchors={analysis.must_preserve_texts or []} "
            f"text_anchor_source={analysis.text_anchor_source} "
            f"text_anchor_count={len(analysis.must_preserve_texts)} "
            f"text_anchor_status={analysis.text_anchor_status}"
        )
    ]
    if not analysis.must_preserve_texts:
        logs.append(
            f"[{node_name}] warning text anchor evidence weak source={analysis.text_anchor_source} "
            f"status={analysis.text_anchor_status} notes={analysis.text_anchor_notes or ['none']}"
        )
    return logs


>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
def _normalize_product_lock_fields(analysis: ProductAnalysis) -> ProductAnalysis:
    """把旧分析结果补齐成当前 image_edit 链路需要的 product_lock 字段。

    这样做的原因：
    - 历史分析结构和当前图生图链路需要的字段并不完全一致
    - 在这里统一归一化后，后面的 style/prompt/render 节点就可以稳定消费
    """
    package_type = analysis.package_type or analysis.packaging_structure.primary_container
    primary_color = analysis.primary_color or (analysis.visual_identity.dominant_colors[0] if analysis.visual_identity.dominant_colors else "")
    material = analysis.material or analysis.material_guess.container_material
    label_structure = analysis.label_structure or (
        f"{analysis.visual_identity.label_position} label / ratio={analysis.visual_identity.label_ratio}"
    )
    locked_elements = analysis.locked_elements or [
        *analysis.visual_identity.must_preserve,
        "package silhouette",
        "front label layout",
    ]
    editable_elements = analysis.editable_elements or ["background", "props", "lighting", "crop"]
<<<<<<< HEAD
=======
    text_anchor_payload = _resolve_text_anchor_payload(analysis)
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    package_template_family = analysis.package_template_family or resolve_tea_package_template_family(
        analysis.model_copy(
            update={
                "package_type": package_type,
                "primary_color": primary_color,
                "material": material,
                "label_structure": label_structure,
            }
        )
    )
    return analysis.model_copy(
        update={
            "locked_elements": locked_elements,
<<<<<<< HEAD
            "must_preserve_texts": analysis.must_preserve_texts or [],
            "editable_elements": editable_elements,
            "package_type": package_type,
            "package_template_family": package_template_family,
=======
            "must_preserve_texts": text_anchor_payload["anchors"],
            "text_anchor_status": text_anchor_payload["status"],
            "text_anchor_source": text_anchor_payload["source"],
            "text_anchor_notes": text_anchor_payload["notes"],
            "editable_elements": editable_elements,
            "package_type": package_type,
            "package_template_family": package_template_family,
            "asset_completeness_mode": analysis.asset_completeness_mode or "packshot_only",
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
            "primary_color": primary_color,
            "material": material,
            "label_structure": label_structure,
        }
    )
<<<<<<< HEAD
=======


def _resolve_text_anchor_payload(analysis: ProductAnalysis) -> dict[str, object]:
    """统一解析 must_preserve_texts 的来源、状态和兜底策略。

    规则：
    - provider 明确给出且通过过滤的短文本锚点，直接作为 `provider`
    - provider 为空时，尝试从 `visual_identity.must_preserve / locked_elements` 中筛出短文本锚点
    - 仍拿不到时，不再静默空数组，而是显式写出 `text_anchor_status`
    """
    provider_status = _normalize_text_anchor_status(analysis.text_anchor_status)
    provider_notes = _normalize_text_anchor_notes(analysis.text_anchor_notes)
    provider_anchors, inline_status = _normalize_text_anchors(analysis.must_preserve_texts)
    provider_status = inline_status or provider_status
    if provider_anchors:
        return {
            "anchors": provider_anchors,
            "source": "provider",
            "status": provider_status if provider_status in {"readable", "uncertain"} else "readable",
            "notes": provider_notes,
        }

    fallback_anchors = _extract_fallback_text_anchors(analysis)
    if fallback_anchors:
        notes = _merge_unique_strings(
            provider_notes,
            ["provider returned empty must_preserve_texts, fallback extracted short text anchors from visual fields"],
        )
        return {
            "anchors": fallback_anchors,
            "source": "fallback",
            "status": "uncertain",
            "notes": notes,
        }

    final_status = provider_status if provider_status in {"uncertain", "unreadable"} else "unreadable"
    notes = provider_notes or ["no stable text anchor could be extracted from provider or fallback"]
    return {
        "anchors": [],
        "source": "none",
        "status": final_status,
        "notes": notes,
    }


def _normalize_text_anchor_status(value: str) -> str:
    """把 provider 或 fallback 的文字锚点状态收敛为固定枚举。"""
    text = str(value or "").strip().lower()
    if text in {"readable", "uncertain", "unreadable"}:
        return text
    for marker, normalized in _TEXT_ANCHOR_STATUS_MARKERS.items():
        if marker in text:
            return normalized
    return "readable" if text else ""


def _normalize_text_anchor_notes(values: list[str] | None) -> list[str]:
    """清洗 provider 侧的文字锚点说明，避免把空值或占位词写入日志与落盘。"""
    notes: list[str] = []
    for raw in values or []:
        text = str(raw or "").strip()
        if not text:
            continue
        if text.lower() in _TEXT_ANCHOR_INVALID_TOKENS:
            continue
        if text not in notes:
            notes.append(text)
    return notes[:3]


def _normalize_text_anchors(values: list[str] | None) -> tuple[list[str], str]:
    """过滤 provider 返回的文字锚点，只保留短、关键、适合后续 OCR 对比的文本。"""
    anchors: list[str] = []
    detected_status = ""
    for raw in values or []:
        text = _normalize_text_anchor(raw)
        if not text:
            normalized_status = _normalize_text_anchor_status(str(raw))
            if normalized_status in {"uncertain", "unreadable"}:
                detected_status = normalized_status
            continue
        if text not in anchors:
            anchors.append(text)
        if len(anchors) >= TEXT_ANCHOR_MAX_COUNT:
            break
    return anchors, detected_status


def _normalize_text_anchor(value: str) -> str:
    """清洗单条文字锚点，并过滤掉视觉结构描述或过长说明句。"""
    text = " ".join(str(value or "").strip().split())
    if not text:
        return ""
    if text.lower() in _TEXT_ANCHOR_INVALID_TOKENS:
        return ""
    text = text.strip("[](){}'\"，。；;：: ")
    if not text:
        return ""
    if any(marker in text.lower() for marker in _TEXT_ANCHOR_STATUS_MARKERS):
        return ""
    if len(text) > 24 or len(text) < 2:
        return ""
    if _looks_like_visual_structure_rule(text):
        return ""
    if not _looks_like_short_text_anchor(text):
        return ""
    return text


def _extract_fallback_text_anchors(analysis: ProductAnalysis) -> list[str]:
    """当 provider 没给 must_preserve_texts 时，从现有视觉字段里回收可用短文本锚点。"""
    candidates = [
        *list(getattr(analysis.visual_identity, "must_preserve", []) or []),
        *list(analysis.locked_elements or []),
    ]
    anchors, _ = _normalize_text_anchors(candidates)
    return anchors


def _looks_like_visual_structure_rule(text: str) -> bool:
    """识别“front label layout / package silhouette”这类视觉规则，避免误当文字锚点。"""
    lower = text.lower()
    if any(marker in lower for marker in _VISUAL_STRUCTURE_MARKERS):
        return True
    if any(marker in text for marker in ("留白", "构图", "轮廓", "结构", "区域", "材质", "纹理", "位置")):
        return True
    return False


def _looks_like_short_text_anchor(text: str) -> bool:
    """判断一段文本是否更像包装上真实可见的短文字，而不是长句说明。"""
    if _TEXT_ANCHOR_UNIT_PATTERN.search(text):
        return True
    if any(marker in text for marker in _TEXT_HINT_MARKERS):
        return True
    if len(text) <= 16 and _LATIN_TOKEN_PATTERN.search(text):
        return True
    chinese_char_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    digit_count = len(re.findall(r"\d", text))
    if 2 <= chinese_char_count <= 12 and len(text) <= 18:
        return True
    if chinese_char_count >= 2 and digit_count >= 1 and len(text) <= 20:
        return True
    return False


def _merge_unique_strings(*groups: list[str]) -> list[str]:
    """按原始顺序去重合并字符串，避免日志与落盘说明重复。"""
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            merged.append(text)
    return merged
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
