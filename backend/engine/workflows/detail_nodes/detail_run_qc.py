"""详情图规则型 QC 节点。"""

from __future__ import annotations

from pathlib import Path

from backend.schemas.detail import (
    DetailPageQCCheck,
    DetailPageQCPageSummary,
    DetailPageQCSummary,
)
from backend.engine.workflows.detail_state import DetailWorkflowDependencies, DetailWorkflowState


def detail_run_qc(state: DetailWorkflowState, deps: DetailWorkflowDependencies) -> dict:
    """对详情图结果做规则型 QC，并为后续 selective retry 预留页级结构。"""

    plan = state.get("detail_plan")
    prompt_plan = state.get("detail_prompt_plan", [])
    copy_blocks = state.get("detail_copy_blocks", [])
    render_results = state.get("detail_render_results", [])
    if plan is None:
        raise RuntimeError("detail_run_qc requires detail_plan")

    prompt_map = {item.page_id: item for item in prompt_plan}
    render_map = {item.page_id: item for item in render_results}
    copy_map = {f"{item.page_id}:{item.screen_id}": item for item in copy_blocks}
    checks: list[DetailPageQCCheck] = []
    pages: list[DetailPageQCPageSummary] = []

    checks.append(
        _build_check(
            check_id="task-page-count",
            check_name="page_count_match",
            page_id="task",
            passed=len(render_results) == plan.total_pages,
            message="结果页数与计划页数一致" if len(render_results) == plan.total_pages else "结果页数与计划页数不一致",
            details={"planned_count": plan.total_pages, "generated_count": len(render_results)},
        )
    )

    for page_index, page in enumerate(plan.pages, start=1):
        prompt_item = prompt_map.get(page.page_id)
        render_item = render_map.get(page.page_id)
        page_issues: list[str] = []

        has_copy_gap = any(
            not copy_map.get(f"{page.page_id}:{screen.screen_id}")
            or not (copy_map[f"{page.page_id}:{screen.screen_id}"].headline or "").strip()
            for screen in page.screens
        )
        copy_check = _build_check(
            check_id=f"{page.page_id}-copy",
            check_name="copy_presence",
            page_id=page.page_id,
            passed=not has_copy_gap,
            message="页面文案完整" if not has_copy_gap else "页面存在空文案",
            details={"page_id": page.page_id},
        )
        checks.append(copy_check)
        if copy_check.status != "passed":
            page_issues.append(copy_check.message)

        has_prompt_refs = bool(prompt_item and prompt_item.references)
        refs_check = _build_check(
            check_id=f"{page.page_id}-references",
            check_name="reference_binding",
            page_id=page.page_id,
            passed=has_prompt_refs,
            message="页面已绑定参考图" if has_prompt_refs else "页面缺少 references",
            details={"reference_roles": [ref.role for ref in prompt_item.references] if prompt_item else []},
        )
        checks.append(refs_check)
        if refs_check.status != "passed":
            page_issues.append(refs_check.message)

        expected_roles = {role for screen in page.screens for role in screen.suggested_asset_roles}
        actual_roles = {ref.role for ref in (prompt_item.references if prompt_item else [])}
        for role, check_name, label in [
            ("dry_leaf", "dry_leaf_binding", "茶干页使用 dry_leaf"),
            ("tea_soup", "tea_soup_binding", "茶汤页使用 tea_soup"),
            ("leaf_bottom", "leaf_bottom_binding", "叶底页使用 leaf_bottom"),
        ]:
            if role not in expected_roles:
                continue
            role_check = _build_check(
                check_id=f"{page.page_id}-{role}",
                check_name=check_name,
                page_id=page.page_id,
                passed=role in actual_roles,
                message=label if role in actual_roles else f"{label} 缺失",
                details={"expected_roles": list(expected_roles), "actual_roles": list(actual_roles)},
            )
            checks.append(role_check)
            if role_check.status != "passed":
                page_issues.append(role_check.message)

        if page_index == 1:
            first_screen_ok = bool(actual_roles.intersection({"packaging", "main_result"}))
            first_screen_check = _build_check(
                check_id="page-01-packaging",
                check_name="first_screen_packaging_or_main_result",
                page_id=page.page_id,
                passed=first_screen_ok,
                message="首屏已绑定 packaging/main_result" if first_screen_ok else "首屏缺少 packaging/main_result",
                details={"actual_roles": list(actual_roles)},
            )
            checks.append(first_screen_check)
            if first_screen_check.status != "passed":
                page_issues.append(first_screen_check.message)

        file_exists = bool(render_item and render_item.relative_path and (Path(state["task"].task_dir) / render_item.relative_path).exists())
        file_check = _build_check(
            check_id=f"{page.page_id}-file",
            check_name="result_file_exists",
            page_id=page.page_id,
            passed=file_exists,
            message="结果文件存在" if file_exists else "结果文件不存在",
            details={"relative_path": render_item.relative_path if render_item else ""},
        )
        checks.append(file_check)
        if file_check.status != "passed":
            page_issues.append(file_check.message)

        size_ok = bool(
            render_item
            and render_item.width
            and render_item.height
            and abs((render_item.height / render_item.width) - (4 / 3)) < 0.15
        )
        size_check = _build_check(
            check_id=f"{page.page_id}-size",
            check_name="detail_image_size",
            page_id=page.page_id,
            passed=size_ok,
            message="3:4 比例正确" if size_ok else "详情图尺寸或比例不正确",
            details={"width": render_item.width if render_item else None, "height": render_item.height if render_item else None},
        )
        checks.append(size_check)
        if size_check.status != "passed":
            page_issues.append(size_check.message)

        page_status = "failed" if any(check.page_id == page.page_id and check.status == "failed" for check in checks) else "warning" if page_issues else "passed"
        pages.append(
            DetailPageQCPageSummary(
                page_id=page.page_id,
                title=page.title,
                status=page_status,
                issues=page_issues,
                reference_roles=list(actual_roles),
                file_name=render_item.file_name if render_item else "",
                width=render_item.width if render_item else None,
                height=render_item.height if render_item else None,
            )
        )

    warning_count = sum(1 for check in checks if check.status == "warning")
    failed_count = sum(1 for check in checks if check.status == "failed")
    issues = [check.message for check in checks if check.status != "passed"]
    summary = DetailPageQCSummary(
        passed=failed_count == 0,
        review_required=warning_count > 0 or failed_count > 0,
        warning_count=warning_count,
        failed_count=failed_count,
        issues=issues,
        checks=checks,
        pages=pages,
    )
    deps.storage.save_json_artifact(state["task"].task_id, "qc/detail_qc_report.json", summary)
    return {
        "detail_qc_summary": summary,
        "logs": [
            *state.get("logs", []),
            f"[detail_run_qc] warning_count={warning_count} failed_count={failed_count}",
            "[detail_run_qc] saved qc/detail_qc_report.json",
        ],
    }


def _build_check(
    *,
    check_id: str,
    check_name: str,
    page_id: str,
    passed: bool,
    message: str,
    details: dict[str, object],
) -> DetailPageQCCheck:
    return DetailPageQCCheck(
        check_id=check_id,
        check_name=check_name,
        page_id=page_id,
        status="passed" if passed else "failed",
        message=message,
        details=details,
    )
