"""详情图运行时聚合服务。"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from PIL import Image

from backend.core.exceptions import AppException
from backend.engine.core.paths import get_task_dir
from backend.schemas.detail import (
    DetailPageCopyBlock,
    DetailPagePlanPayload,
    DetailPagePromptPlanItem,
    DetailPageQCSummary,
    DetailPageRuntimeImage,
    DetailPageRuntimePayload,
)
from backend.schemas.task import TaskSummary


class DetailRuntimeService:
    """读取详情图任务目录并聚合 runtime。"""

    def get_runtime(self, summary: TaskSummary) -> DetailPageRuntimePayload:
        """返回详情图 runtime。"""

        task_dir = get_task_dir(summary.task_id)
        plan = self._load_json(task_dir / "plan" / "detail_plan.json", DetailPagePlanPayload)
        copy_blocks = self._load_json_list(task_dir / "plan" / "detail_copy_plan.json", DetailPageCopyBlock)
        prompt_plan = self._load_json_list(task_dir / "plan" / "detail_prompt_plan.json", DetailPagePromptPlanItem)
        qc_summary = self._load_qc_summary(task_dir / "qc" / "detail_qc_report.json")
        render_rows = self._load_render_report(task_dir / "generated" / "detail_render_report.json")
        images = self._load_images(summary.task_id, task_dir, prompt_plan, render_rows)
        planned_count = plan.total_pages if plan else len(prompt_plan)
        generated_count = sum(1 for image in images if image.status == "completed")
        task_error_message = self._load_task_error_message(task_dir)
        runtime_message = self._resolve_runtime_message(status=summary.status, task_error_message=task_error_message)
        return DetailPageRuntimePayload(
            task_id=summary.task_id,
            status=summary.status,
            progress_percent=summary.progress_percent,
            current_stage=summary.current_step,
            current_stage_label=summary.current_step_label,
            message=runtime_message,
            generated_count=generated_count,
            planned_count=planned_count,
            plan=plan,
            copy_blocks=copy_blocks,
            prompt_plan=prompt_plan,
            qc_summary=qc_summary,
            images=images,
            export_zip_url=self._resolve_export_url(summary.task_id, task_dir),
        )

    def resolve_task_file(self, task_id: str, file_name: str) -> Path:
        """限制详情图文件访问范围。"""

        task_dir = get_task_dir(task_id).resolve()
        target = (task_dir / file_name).resolve()
        try:
            target.relative_to(task_dir)
        except ValueError as exc:
            raise AppException("不允许访问任务目录之外的文件", code=4006) from exc
        if not target.exists() or not target.is_file():
            raise AppException(f"任务文件不存在：{file_name}", code=4045)
        return target

    def _load_json(self, path: Path, model_cls: type[DetailPagePlanPayload]) -> DetailPagePlanPayload | None:
        if not path.exists():
            return None
        return model_cls.model_validate_json(path.read_text(encoding="utf-8"))

    def _load_json_list(self, path: Path, model_cls: type[DetailPageCopyBlock] | type[DetailPagePromptPlanItem]) -> list:
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "items" in payload:
            payload = payload["items"]
        return [model_cls.model_validate(item) for item in payload]

    def _load_qc_summary(self, path: Path) -> DetailPageQCSummary:
        if not path.exists():
            return DetailPageQCSummary()
        payload = json.loads(path.read_text(encoding="utf-8"))
        return DetailPageQCSummary.model_validate(payload)

    def _load_images(
        self,
        task_id: str,
        task_dir: Path,
        prompt_plan: list[DetailPagePromptPlanItem],
        render_rows: dict[str, dict[str, object]],
    ) -> list[DetailPageRuntimeImage]:
        generated = sorted((task_dir / "generated").glob("*.png"))
        rows: list[DetailPageRuntimeImage] = []
        for index, item in enumerate(prompt_plan, start=1):
            render_row = render_rows.get(item.page_id, {})
            render_status = str(render_row.get("status", "")).strip()
            image_path = generated[index - 1] if index - 1 < len(generated) else None
            if image_path and image_path.exists():
                width, height = self._size_of(image_path)
                rows.append(
                    DetailPageRuntimeImage(
                        image_id=f"detail-{index:02d}",
                        page_id=item.page_id,
                        title=item.page_title,
                        status="completed",
                        file_name=image_path.relative_to(task_dir).as_posix(),
                        image_url=self._build_url(task_id, image_path.relative_to(task_dir).as_posix()),
                        width=width,
                        height=height,
                        reference_roles=[ref.role for ref in item.references],
                    )
                )
            elif render_status == "failed":
                rows.append(
                    DetailPageRuntimeImage(
                        image_id=f"detail-{index:02d}",
                        page_id=item.page_id,
                        title=item.page_title,
                        status="failed",
                        reference_roles=[ref.role for ref in item.references],
                    )
                )
            else:
                rows.append(
                    DetailPageRuntimeImage(
                        image_id=f"detail-{index:02d}",
                        page_id=item.page_id,
                        title=item.page_title,
                        status="running",
                    )
                )
        return rows

    def _load_render_report(self, path: Path) -> dict[str, dict[str, object]]:
        """读取渲染报告，透出单页状态。"""

        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            return {}
        rows: dict[str, dict[str, object]] = {}
        for item in payload:
            if isinstance(item, dict) and isinstance(item.get("page_id"), str):
                rows[item["page_id"]] = item
        return rows

    def _load_task_error_message(self, task_dir: Path) -> str:
        """从 task.json 提取失败信息。"""

        task_file = task_dir / "task.json"
        if not task_file.exists():
            return ""
        payload = json.loads(task_file.read_text(encoding="utf-8"))
        error_message = payload.get("error_message")
        return str(error_message).strip() if error_message else ""

    def _resolve_runtime_message(self, *, status: str, task_error_message: str) -> str:
        """根据任务状态返回更明确的用户可读信息。"""

        if status in {"created", "running"}:
            return "详情图任务运行中"
        if status == "completed":
            return "详情图任务已完成"
        if status == "failed":
            return task_error_message or "详情图任务失败，请检查渲染日志与模型配置。"
        return "详情图任务状态未知"

    def _resolve_export_url(self, task_id: str, task_dir: Path) -> str:
        path = task_dir / "exports" / "detail_bundle.zip"
        if not path.exists():
            return ""
        return self._build_url(task_id, path.relative_to(task_dir).as_posix())

    def _build_url(self, task_id: str, relative_path: str) -> str:
        safe = quote(relative_path.replace("\\", "/"), safe="/")
        return f"/api/detail/jobs/{task_id}/files/{safe}"

    def _size_of(self, path: Path) -> tuple[int | None, int | None]:
        try:
            with Image.open(path) as image:
                return image.size
        except OSError:
            return None, None
