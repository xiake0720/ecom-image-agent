"""详情图规则型 QC 节点。"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

from backend.engine.workflows.detail_state import DetailWorkflowDependencies, DetailWorkflowState
from backend.schemas.detail import (
    DetailPageCopyBlock,
    DetailPageQCCheck,
    DetailPageQCPageSummary,
    DetailPageQCSummary,
    DetailPagePromptPlanItem,
    DetailRetryDecisionItem,
    DetailRetryDecisionReport,
    DetailVisualReviewPage,
    DetailVisualReviewReport,
)

_INSTRUCTION_TOKENS = (
    "只做",
    "不虚构",
    "允许",
    "保持稳定",
    "可由模型",
    "不要",
    "只保留",
)
_PROMPT_LEAK_LABELS = (
    "主标题：",
    "副标题：",
    "卖点标签：",
    "参数卡：",
    "辅助说明：",
    "CTA：",
)
_ENGLISH_PARAM_TOKENS = (
    "net_content",
    "origin",
    "ingredients",
    "shelf_life",
    "storage",
    "net_",
)
_SNAKE_CASE_RE = re.compile(r"\b[a-z]{2,}(?:_[a-z0-9]+)+\b")
_HERO_GROUNDING_TOKENS = (
    "resting on surface",
    "contact shadow",
    "ambient occlusion",
    "soft directional light",
    "coherent perspective",
)


def detail_run_qc(state: DetailWorkflowState, deps: DetailWorkflowDependencies) -> dict:
    """对详情图结果执行规则 QC，并生成 visual_review / retry_decisions。"""

    plan = state.get("detail_plan")
    prompt_plan = state.get("detail_prompt_plan", [])
    copy_blocks = state.get("detail_copy_blocks", [])
    render_results = state.get("detail_render_results", [])
    assets = state.get("detail_assets", [])
    if plan is None:
        raise RuntimeError("detail_run_qc requires detail_plan")

    prompt_map = {item.page_id: item for item in prompt_plan}
    render_map = {item.page_id: item for item in render_results}
    copy_map = {f"{item.page_id}:{item.screen_id}": item for item in copy_blocks}
    checks: list[DetailPageQCCheck] = []
    pages: list[DetailPageQCPageSummary] = []
    visual_pages: list[DetailVisualReviewPage] = []
    retry_pages: list[DetailRetryDecisionItem] = []

    generated_count = sum(1 for item in render_results if item.status == "completed")
    if generated_count == 0:
        checks.append(
            _build_check(
                check_id="task-generated-count",
                check_name="generated_count",
                page_id="task",
                status="failed",
                message="本次任务没有成功生成任何详情图",
                details={"planned_count": plan.total_pages, "generated_count": generated_count},
            )
        )
    elif generated_count < plan.total_pages:
        checks.append(
            _build_check(
                check_id="task-generated-count",
                check_name="generated_count",
                page_id="task",
                status="warning",
                message="详情图仅部分生成成功",
                details={"planned_count": plan.total_pages, "generated_count": generated_count},
            )
        )
    else:
        checks.append(
            _build_check(
                check_id="task-generated-count",
                check_name="generated_count",
                page_id="task",
                status="passed",
                message="详情图页数与计划一致",
                details={"planned_count": plan.total_pages, "generated_count": generated_count},
            )
        )

    packaging_asset_count = sum(1 for asset in assets if asset.role == "packaging")
    used_packaging_files = [
        ref.file_name
        for item in prompt_plan
        for ref in item.references
        if ref.role == "packaging"
    ]
    if packaging_asset_count > 1:
        unique_packaging_used = len(set(used_packaging_files))
        status = "passed" if unique_packaging_used > 1 else "warning"
        message = "包装参考已轮换使用" if status == "passed" else "包装参考过度复用单一图片"
        checks.append(
            _build_check(
                check_id="task-packaging-reuse",
                check_name="packaging_reference_diversity",
                page_id="task",
                status=status,
                message=message,
                details={
                    "packaging_asset_count": packaging_asset_count,
                    "used_packaging_files": list(dict.fromkeys(used_packaging_files)),
                },
            )
        )

    task_dir = Path(state["task"].task_dir).resolve()
    for page in plan.pages:
        prompt_item = prompt_map.get(page.page_id)
        render_item = render_map.get(page.page_id)
        page_issues: list[str] = []
        page_warnings: list[str] = []

        block = next((copy_map.get(f"{page.page_id}:{screen.screen_id}") for screen in page.screens), None)
        has_copy_gap = block is None or not (block.headline or "").strip()
        checks.append(
            _build_check(
                check_id=f"{page.page_id}-copy",
                check_name="copy_presence",
                page_id=page.page_id,
                status="failed" if has_copy_gap else "passed",
                message="页面文案完整" if not has_copy_gap else "页面存在空文案",
                details={"page_id": page.page_id},
            )
        )
        if has_copy_gap:
            page_issues.append("页面存在空文案")

        if prompt_item is None or not prompt_item.references:
            page_issues.append("页面缺少 references")
            checks.append(
                _build_check(
                    check_id=f"{page.page_id}-references",
                    check_name="reference_binding",
                    page_id=page.page_id,
                    status="failed",
                    message="页面缺少 references",
                    details={},
                )
            )
        else:
            checks.append(
                _build_check(
                    check_id=f"{page.page_id}-references",
                    check_name="reference_binding",
                    page_id=page.page_id,
                    status="passed",
                    message="页面已绑定参考图",
                    details={"reference_roles": [ref.role for ref in prompt_item.references]},
                )
            )

        expected_anchor_roles = set(page.anchor_roles)
        actual_roles = {ref.role for ref in (prompt_item.references if prompt_item else [])}
        missing_anchor_roles = [role for role in expected_anchor_roles if role not in actual_roles]
        if missing_anchor_roles:
            page_issues.append(f"缺少锚点素材：{', '.join(missing_anchor_roles)}")
            checks.append(
                _build_check(
                    check_id=f"{page.page_id}-anchor",
                    check_name="anchor_binding",
                    page_id=page.page_id,
                    status="failed",
                    message="锚点素材绑定缺失",
                    details={"expected_anchor_roles": list(expected_anchor_roles), "actual_roles": list(actual_roles)},
                )
            )
        else:
            checks.append(
                _build_check(
                    check_id=f"{page.page_id}-anchor",
                    check_name="anchor_binding",
                    page_id=page.page_id,
                    status="passed",
                    message="锚点素材绑定正确",
                    details={"expected_anchor_roles": list(expected_anchor_roles), "actual_roles": list(actual_roles)},
                )
            )

        if block is not None:
            if len(block.headline) > 12:
                page_warnings.append("标题长度超过 12 字")
            if len(block.subheadline) > 24:
                page_warnings.append("副标题长度超过 24 字")
            instruction_findings = _find_instruction_copy(block)
            if instruction_findings:
                page_issues.append(f"文案包含规则句或提示词：{', '.join(instruction_findings)}")
            english_key_findings = _find_english_key_leaks(block.parameter_copy)
            if english_key_findings:
                page_issues.append(f"参数文案包含英文 key 或 snake_case：{', '.join(english_key_findings)}")
            if page.page_role in {"parameter_and_closing", "brewing_method_info"}:
                parameter_cards = [part.strip() for part in block.parameter_copy.split("/") if part.strip()]
                if len(parameter_cards) < 3:
                    page_warnings.append("参数卡不足 3 组")

        if prompt_item is not None:
            prompt_leaks = _find_prompt_copy_leaks(prompt_item.prompt)
            if prompt_leaks:
                page_issues.append(f"render prompt 混入可见文案标签：{', '.join(prompt_leaks)}")
            if page.page_role == "hero_opening":
                missing_grounding = _find_missing_hero_grounding(prompt_item)
                if missing_grounding:
                    page_warnings.append("首屏缺少明确接地感与阴影约束")
                    checks.append(
                        _build_check(
                            check_id=f"{page.page_id}-grounding",
                            check_name="hero_grounding_prompt",
                            page_id=page.page_id,
                            status="warning",
                            message="首屏 prompt 缺少完整接地感约束",
                            details={"missing_tokens": missing_grounding},
                        )
                    )
                else:
                    checks.append(
                        _build_check(
                            check_id=f"{page.page_id}-grounding",
                            check_name="hero_grounding_prompt",
                            page_id=page.page_id,
                            status="passed",
                            message="首屏 prompt 已包含接地感约束",
                            details={"required_tokens": list(_HERO_GROUNDING_TOKENS)},
                        )
                    )

        file_exists = bool(
            render_item
            and render_item.relative_path
            and (task_dir / render_item.relative_path).exists()
        )
        if render_item is not None and render_item.status == "failed":
            page_issues.append(render_item.error_message or "页面渲染失败")
        if not file_exists:
            checks.append(
                _build_check(
                    check_id=f"{page.page_id}-file",
                    check_name="result_file_exists",
                    page_id=page.page_id,
                    status="failed",
                    message="结果文件不存在",
                    details={"relative_path": render_item.relative_path if render_item else ""},
                )
            )
            if render_item is None or render_item.status != "failed":
                page_issues.append("结果文件不存在")
        else:
            checks.append(
                _build_check(
                    check_id=f"{page.page_id}-file",
                    check_name="result_file_exists",
                    page_id=page.page_id,
                    status="passed",
                    message="结果文件存在",
                    details={"relative_path": render_item.relative_path if render_item else ""},
                )
            )

        size_ok = bool(
            render_item
            and render_item.width
            and render_item.height
            and abs((render_item.height / render_item.width) - (4 / 3)) < 0.12
        )
        if not size_ok:
            page_issues.append("详情图尺寸或比例不正确")
            checks.append(
                _build_check(
                    check_id=f"{page.page_id}-size",
                    check_name="detail_image_size",
                    page_id=page.page_id,
                    status="failed",
                    message="详情图尺寸或比例不正确",
                    details={"width": render_item.width if render_item else None, "height": render_item.height if render_item else None},
                )
            )
        else:
            checks.append(
                _build_check(
                    check_id=f"{page.page_id}-size",
                    check_name="detail_image_size",
                    page_id=page.page_id,
                    status="passed",
                    message="3:4 比例正确",
                    details={"width": render_item.width if render_item else None, "height": render_item.height if render_item else None},
                )
            )

        for warning in page_warnings:
            checks.append(
                _build_check(
                    check_id=f"{page.page_id}-{warning}",
                    check_name="page_warning",
                    page_id=page.page_id,
                    status="warning",
                    message=warning,
                    details={},
                )
            )

        page_status = "failed" if page_issues else "warning" if page_warnings else "passed"
        pages.append(
            DetailPageQCPageSummary(
                page_id=page.page_id,
                title=page.title,
                page_role=page.page_role,
                status=page_status,
                issues=[*page_issues, *page_warnings],
                reference_roles=list(actual_roles),
                file_name=render_item.file_name if render_item else "",
                width=render_item.width if render_item else None,
                height=render_item.height if render_item else None,
            )
        )
        visual_pages.append(
            DetailVisualReviewPage(
                page_id=page.page_id,
                page_role=page.page_role,
                title=page.title,
                status=page_status,
                findings=[*page_issues, *page_warnings] or ["页面整体通过基础检查"],
                recommended_actions=_resolve_recommended_actions(
                    page.page_role,
                    render_item.error_message if render_item else "",
                    page_issues,
                    page_warnings,
                ),
            )
        )
        retry_pages.append(
            DetailRetryDecisionItem(
                page_id=page.page_id,
                page_role=page.page_role,
                should_retry=bool(page_issues),
                reason="；".join(page_issues) if page_issues else "",
                strategies=_resolve_retry_strategies(page.page_role, render_item.error_message if render_item else "", page_issues, page_warnings),
            )
        )

    warning_count = sum(1 for check in checks if check.status == "warning")
    failed_count = sum(1 for check in checks if check.status == "failed")
    summary = DetailPageQCSummary(
        passed=failed_count == 0 and generated_count > 0,
        review_required=warning_count > 0 or failed_count > 0,
        warning_count=warning_count,
        failed_count=failed_count,
        issues=[check.message for check in checks if check.status != "passed"],
        checks=checks,
        pages=pages,
    )
    visual_review = DetailVisualReviewReport(
        overall_status="failed" if failed_count > 0 else "warning" if warning_count > 0 else "passed",
        summary=_build_visual_summary(generated_count, plan.total_pages, visual_pages),
        pages=visual_pages,
    )
    retry_decisions = DetailRetryDecisionReport(pages=retry_pages)
    deps.storage.save_json_artifact(state["task"].task_id, "review/visual_review.json", visual_review)
    deps.storage.save_json_artifact(state["task"].task_id, "review/retry_decisions.json", retry_decisions)
    deps.storage.save_json_artifact(state["task"].task_id, "qc/detail_qc_report.json", summary)
    return {
        "detail_visual_review": visual_review,
        "detail_retry_decisions": retry_decisions,
        "detail_qc_summary": summary,
        "logs": [
            *state.get("logs", []),
            f"[detail_run_qc] warning_count={warning_count} failed_count={failed_count}",
            "[detail_run_qc] saved review/visual_review.json",
            "[detail_run_qc] saved review/retry_decisions.json",
            "[detail_run_qc] saved qc/detail_qc_report.json",
        ],
    }


def _build_check(
    *,
    check_id: str,
    check_name: str,
    page_id: str,
    status: str,
    message: str,
    details: dict[str, object],
) -> DetailPageQCCheck:
    """创建单条 QC 检查结果。"""

    return DetailPageQCCheck(
        check_id=check_id,
        check_name=check_name,
        page_id=page_id,
        status=status,
        message=message,
        details=details,
    )


def _build_visual_summary(
    generated_count: int,
    planned_count: int,
    visual_pages: list[DetailVisualReviewPage],
) -> list[str]:
    """生成 visual_review 的总览摘要。"""

    summary = [f"已生成 {generated_count}/{planned_count} 页。"]
    failed_roles = [item.page_role for item in visual_pages if item.status == "failed"]
    if failed_roles:
        summary.append(f"失败页角色：{dict(Counter(failed_roles))}")
    warning_roles = [item.page_role for item in visual_pages if item.status == "warning"]
    if warning_roles:
        summary.append(f"警告页角色：{dict(Counter(warning_roles))}")
    return summary


def _resolve_recommended_actions(
    page_role: str,
    error_message: str,
    issues: list[str],
    warnings: list[str],
) -> list[str]:
    """给 visual_review 输出建议动作。"""

    actions: list[str] = []
    normalized = error_message.lower()
    if "json" in normalized or "500" in normalized:
        actions.append("优先做 provider 抖动重试")
    if any("锚点素材" in item for item in issues):
        actions.append("重新绑定正确锚点素材")
    if any("规则句" in item or "提示词" in item or "文案标签" in item for item in issues):
        actions.append("拆分可见文案与隐藏渲染指令")
    if any("英文 key" in item or "snake_case" in item for item in issues):
        actions.append("把 specs 字段映射成中文参数卡")
    if any("接地感" in item for item in warnings):
        actions.append("补强接触阴影、承托面和光影方向约束")
    if page_role in {"dry_leaf_evidence", "leaf_bottom_process_evidence"}:
        actions.append("进一步强化形态忠实约束")
    if any("标题长度" in item or "参数卡不足" in item for item in warnings):
        actions.append("继续降低文本密度")
    if not actions:
        actions.append("当前页面无需额外处理")
    return list(dict.fromkeys(actions))


def _resolve_retry_strategies(
    page_role: str,
    error_message: str,
    issues: list[str],
    warnings: list[str],
) -> list[str]:
    """给 selective retry 输出建议策略。"""

    if not issues:
        return []
    normalized = error_message.lower()
    strategies: list[str] = []
    if "json" in normalized or "500" in normalized:
        strategies.extend(["original_prompt_retry", "text_density_reduction"])
    if any("锚点素材" in item for item in issues):
        strategies.append("reference_rebinding")
    if any("规则句" in item or "提示词" in item or "文案标签" in item for item in issues):
        strategies.extend(["text_density_reduction", "style_correction"])
    if any("英文 key" in item or "snake_case" in item for item in issues):
        strategies.append("text_density_reduction")
    if any("接地感" in item for item in warnings):
        strategies.append("packaging_emphasis")
    if page_role in {"hero_opening", "packaging_structure_value", "package_closeup_evidence"}:
        strategies.append("packaging_emphasis")
    if page_role in {"scene_value_story", "brand_trust", "gift_openbox_portable"}:
        strategies.append("style_correction")
    if page_role in {"dry_leaf_evidence", "leaf_bottom_process_evidence"}:
        strategies.append("packaging_emphasis")
    return list(dict.fromkeys(strategies))


def _find_instruction_copy(block: DetailPageCopyBlock) -> list[str]:
    """识别用户可见文案里混入的规则句。"""

    findings: list[str] = []
    fields = {
        "headline": block.headline,
        "subheadline": block.subheadline,
        "selling_points": " / ".join(block.selling_points),
        "body_copy": block.body_copy,
        "parameter_copy": block.parameter_copy,
        "cta_copy": block.cta_copy,
    }
    for field_name, text in fields.items():
        normalized = str(text or "").strip()
        if not normalized:
            continue
        for token in _INSTRUCTION_TOKENS:
            if token in normalized:
                findings.append(f"{field_name}:{token}")
    return list(dict.fromkeys(findings))


def _find_english_key_leaks(text: str) -> list[str]:
    """识别参数文案里的英文 key 或 snake_case。"""

    normalized = str(text or "").strip().lower()
    if not normalized:
        return []
    findings = [token for token in _ENGLISH_PARAM_TOKENS if token in normalized]
    findings.extend(_SNAKE_CASE_RE.findall(normalized))
    return list(dict.fromkeys(findings))


def _find_prompt_copy_leaks(prompt: str) -> list[str]:
    """识别 render prompt 中混入的旧式可见文案标签。"""

    normalized = str(prompt or "")
    return [label for label in _PROMPT_LEAK_LABELS if label in normalized]


def _find_missing_hero_grounding(prompt_item: DetailPagePromptPlanItem) -> list[str]:
    """检查首屏 prompt 是否具备接地感关键词。"""

    normalized = (prompt_item.prompt or "").lower()
    return [token for token in _HERO_GROUNDING_TOKENS if token not in normalized]
