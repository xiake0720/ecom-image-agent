"""详情图运行时聚合服务。"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from backend.core.exceptions import AppException
from backend.engine.core.paths import get_task_dir
from backend.engine.domain.task import Task, TaskStatus
from backend.schemas.detail import (
    DetailCopyPlanResult,
    DetailDirectorBrief,
    DetailPageCopyBlock,
    DetailPageJobCreatePayload,
    DetailPagePlanPayload,
    DetailPagePromptPlanItem,
    DetailPageQCSummary,
    DetailPageRenderResult,
    DetailPageRuntimeImage,
    DetailPageRuntimePayload,
    DetailPreflightReport,
    DetailRetryDecisionReport,
    DetailVisualReviewReport,
)
from backend.schemas.task import TaskSummary
from backend.services.task_usage_service import TaskUsageService


class DetailRuntimeService:
    """读取 detail graph 产物并组装 runtime。"""

    def __init__(self) -> None:
        self.usage_service = TaskUsageService()

    def get_runtime(self, summary: TaskSummary) -> DetailPageRuntimePayload:
        """返回详情图 runtime 聚合。"""

        task = self._load_task_manifest(summary.task_id)
        task_dir = Path(task.task_dir or get_task_dir(summary.task_id))
        plan = self._load_json(task_dir / "plan" / "detail_plan.json", DetailPagePlanPayload)
        copy_wrapper = self._load_json(task_dir / "plan" / "detail_copy_plan.json", DetailCopyPlanResult)
        copy_blocks = copy_wrapper.items if copy_wrapper is not None else []
        prompt_plan = self._load_json_list(task_dir / "plan" / "detail_prompt_plan.json", DetailPagePromptPlanItem)
        request_payload = self._load_json(task_dir / "inputs" / "request_payload.json", DetailPageJobCreatePayload)
        preflight_report = self._load_json(task_dir / "inputs" / "preflight_report.json", DetailPreflightReport)
        director_brief = self._load_json(task_dir / "plan" / "director_brief.json", DetailDirectorBrief)
        visual_review = self._load_json(task_dir / "review" / "visual_review.json", DetailVisualReviewReport)
        retry_decisions = self._load_json(task_dir / "review" / "retry_decisions.json", DetailRetryDecisionReport)
        qc_summary = self._load_json(task_dir / "qc" / "detail_qc_report.json", DetailPageQCSummary) or DetailPageQCSummary()
        render_results = self._load_json_list(task_dir / "generated" / "detail_render_report.json", DetailPageRenderResult)
        images = self._build_images(task, plan, prompt_plan, render_results)
        planned_count = plan.total_pages if plan else len(prompt_plan)
        generated_count = sum(1 for image in images if image.status == "completed")
        error_message = task.error_message or self._load_error_message_from_render_results(render_results)
        usage_summary = self.usage_service.build_runtime_usage_summary(
            task.task_id,
            upstream_task_id=request_payload.main_image_task_id if request_payload is not None else "",
        )
        return DetailPageRuntimePayload(
            task_id=task.task_id,
            status=task.status.value,
            progress_percent=task.progress_percent,
            current_stage=task.current_step,
            current_stage_label=task.current_step_label,
            message=self._resolve_runtime_message(task=task, generated_count=generated_count, planned_count=planned_count, error_message=error_message),
            error_message=error_message,
            generated_count=generated_count,
            planned_count=planned_count,
            plan=plan,
            copy_blocks=copy_blocks,
            prompt_plan=prompt_plan,
            preflight_report=preflight_report,
            director_brief=director_brief,
            visual_review=visual_review,
            retry_decisions=retry_decisions,
            usage_summary=usage_summary,
            qc_summary=qc_summary,
            images=images,
            export_zip_url=self._resolve_export_url(task.task_id, task_dir),
        )

    def resolve_task_file(self, task_id: str, file_name: str) -> Path:
        """限制详情图任务文件访问范围。"""

        task_dir = get_task_dir(task_id).resolve()
        target = (task_dir / file_name).resolve()
        try:
            target.relative_to(task_dir)
        except ValueError as exc:
            raise AppException("不允许访问任务目录之外的文件", code=4006) from exc
        if not target.exists() or not target.is_file():
            raise AppException(f"任务文件不存在：{file_name}", code=4045)
        return target

    def _load_task_manifest(self, task_id: str) -> Task:
        task_path = get_task_dir(task_id) / "task.json"
        if not task_path.exists():
            raise AppException(f"详情图任务 {task_id} 不存在", code=4044)
        return Task.model_validate_json(task_path.read_text(encoding="utf-8"))

    def _load_json(self, path: Path, model_cls):
        if not path.exists():
            return None
        return model_cls.model_validate_json(path.read_text(encoding="utf-8"))

    def _load_json_list(self, path: Path, model_cls) -> list:
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "items" in payload:
            payload = payload["items"]
        if not isinstance(payload, list):
            return []
        return [model_cls.model_validate(item) for item in payload]

    def _build_images(
        self,
        task: Task,
        plan: DetailPagePlanPayload | None,
        prompt_plan: list[DetailPagePromptPlanItem],
        render_results: list[DetailPageRenderResult],
    ) -> list[DetailPageRuntimeImage]:
        if not render_results and task.current_step == "detail_generate_prompt":
            return []
        render_map = {item.page_id: item for item in render_results}
        images: list[DetailPageRuntimeImage] = []
        source_pages = prompt_plan or []
        if not source_pages and plan is not None:
            source_pages = [
                DetailPagePromptPlanItem(
                    page_id=page.page_id,
                    page_title=page.title,
                    page_role=page.page_role,
                    layout_mode=page.layout_mode,
                    primary_headline_screen_id=page.primary_headline_screen_id,
                    global_style_anchor=plan.global_style_anchor,
                    screen_themes=[screen.theme for screen in page.screens],
                    layout_notes=[],
                    title_copy="",
                    subtitle_copy="",
                    selling_points_for_render=[],
                    prompt="",
                    negative_prompt="",
                    references=[],
                )
                for page in plan.pages
            ]
        for index, item in enumerate(source_pages, start=1):
            render_row = render_map.get(item.page_id)
            if render_row is not None and render_row.status == "completed" and render_row.relative_path:
                images.append(
                    DetailPageRuntimeImage(
                        image_id=f"detail-{index:02d}",
                        page_id=item.page_id,
                        title=item.page_title,
                        page_role=item.page_role,
                        status="completed",
                        file_name=render_row.relative_path,
                        image_url=self._build_url(task.task_id, render_row.relative_path),
                        width=render_row.width,
                        height=render_row.height,
                        reference_roles=render_row.reference_roles,
                        retry_count=render_row.retry_count,
                    )
                )
                continue
            if render_row is not None and render_row.status == "failed":
                images.append(
                    DetailPageRuntimeImage(
                        image_id=f"detail-{index:02d}",
                        page_id=item.page_id,
                        title=item.page_title,
                        page_role=item.page_role,
                        status="failed",
                        reference_roles=render_row.reference_roles,
                        error_message=render_row.error_message,
                        retry_count=render_row.retry_count,
                    )
                )
                continue
            images.append(
                DetailPageRuntimeImage(
                    image_id=f"detail-{index:02d}",
                    page_id=item.page_id,
                    title=item.page_title,
                    page_role=item.page_role,
                    status=self._resolve_placeholder_status(task.status, index, render_results),
                    reference_roles=[ref.role for ref in item.references],
                    retry_count=0,
                )
            )
        return images

    def _resolve_placeholder_status(
        self,
        task_status: TaskStatus,
        index: int,
        render_results: list[DetailPageRenderResult],
    ) -> str:
        processed_count = len(render_results)
        if task_status == TaskStatus.CREATED:
            return "queued"
        if task_status == TaskStatus.RUNNING:
            return "running" if index == processed_count + 1 else "queued"
        if task_status == TaskStatus.FAILED:
            return "failed" if index <= processed_count else "queued"
        if task_status == TaskStatus.REVIEW_REQUIRED:
            return "queued" if index > processed_count else "failed"
        return "completed"

    def _resolve_runtime_message(
        self,
        *,
        task: Task,
        generated_count: int,
        planned_count: int,
        error_message: str,
    ) -> str:
        if error_message:
            return error_message
        if task.status == TaskStatus.CREATED:
            return "详情图任务已提交，等待执行。"
        if task.status == TaskStatus.RUNNING:
            if planned_count > 0:
                return f"正在生成详情图（{generated_count}/{planned_count}）"
            return task.current_step_label or "详情图任务运行中"
        if task.status == TaskStatus.REVIEW_REQUIRED:
            return f"详情图已生成 {generated_count}/{planned_count} 页，请复核 review 与 QC 结果。"
        if task.status == TaskStatus.COMPLETED:
            if task.current_step == "detail_generate_prompt" or planned_count == 0:
                return "规划、文案与 Prompt 已完成。"
            return f"详情图任务已完成，共生成 {generated_count}/{planned_count} 张 3:4 单屏图。"
        return task.current_step_label or "详情图任务失败。"

    def _resolve_export_url(self, task_id: str, task_dir: Path) -> str:
        path = task_dir / "exports" / "detail_bundle.zip"
        if not path.exists():
            return ""
        return self._build_url(task_id, path.relative_to(task_dir).as_posix())

    def _build_url(self, task_id: str, relative_path: str) -> str:
        safe = quote(relative_path.replace("\\", "/"), safe="/")
        return f"/api/detail/jobs/{task_id}/files/{safe}"

    def _load_error_message_from_render_results(self, render_results: list[DetailPageRenderResult]) -> str:
        for item in render_results:
            if item.status == "failed" and item.error_message:
                return item.error_message
        return ""
