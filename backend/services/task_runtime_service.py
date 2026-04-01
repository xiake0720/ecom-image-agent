"""任务运行时服务。

职责：从 task manifest、prompt plan、qc_report 和 outputs/tasks 目录中组装前端工作台所需的运行时视图。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from PIL import Image

from backend.core.exceptions import AppException
from backend.engine.core.config import get_settings
from backend.engine.core.paths import get_task_dir
from backend.engine.domain.prompt_plan_v2 import PromptPlanV2, PromptShot
from backend.engine.domain.qc_report import QCReport
from backend.engine.domain.task import Task, TaskStatus
from backend.repositories.task_repository import TaskRepository
from backend.schemas.task import TaskRuntimeImage, TaskRuntimePayload, TaskRuntimeQCSummary
from backend.services.task_queue_service import main_image_task_queue


class TaskRuntimeService:
    """组装主图工作台运行时数据。"""

    def __init__(self) -> None:
        self.repo = TaskRepository()

    def get_runtime(self, task_id: str) -> TaskRuntimePayload:
        """返回当前任务的运行时状态与结果列表。"""

        task = self._load_task_manifest(task_id)
        summary = self.repo.get_task(task_id)
        prompt_plan = self._load_prompt_plan(task_id)
        file_refs = self._list_result_files(Path(task.task_dir or get_task_dir(task.task_id)))
        results = self._build_runtime_results(task, prompt_plan, file_refs)
        queue_snapshot = main_image_task_queue.get_snapshot(task_id)
        export_zip_url, full_bundle_zip_url = self._resolve_export_urls(task.task_id)
        qc_summary = self._build_qc_summary(task.task_id)
        settings = get_settings()
        provider_label = summary.provider_label if summary is not None and summary.provider_label else settings.resolve_image_provider_route().label
        model_label = summary.model_label if summary is not None and summary.model_label else settings.resolve_image_model_selection().label
        detail_image_count = summary.detail_image_count if summary is not None else 0
        background_image_count = summary.background_image_count if summary is not None else 0
        result_count_completed = sum(1 for item in results if item.status == "completed")
        result_count_total = len(results)
        message = self._build_runtime_message(task, results, queue_snapshot.queue_position, queue_snapshot.queue_size)
        return TaskRuntimePayload(
            task_id=task.task_id,
            status=task.status.value,
            progress_percent=task.progress_percent,
            current_step=task.current_step,
            current_step_label=task.current_step_label,
            message=message,
            queue_position=queue_snapshot.queue_position,
            queue_size=queue_snapshot.queue_size,
            provider_label=provider_label,
            model_label=model_label,
            detail_image_count=detail_image_count,
            background_image_count=background_image_count,
            result_count_completed=result_count_completed,
            result_count_total=result_count_total,
            export_zip_url=export_zip_url,
            full_bundle_zip_url=full_bundle_zip_url,
            qc_summary=qc_summary,
            results=results,
        )

    def resolve_task_file(self, task_id: str, file_name: str) -> Path:
        """解析任务输出目录下的真实文件路径，并阻止越界访问。"""

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
        """读取任务目录中的 task.json。"""

        task_path = get_task_dir(task_id) / "task.json"
        if not task_path.exists():
            raise AppException(f"任务 {task_id} 不存在", code=4044)
        return Task.model_validate_json(task_path.read_text(encoding="utf-8"))

    def _load_prompt_plan(self, task_id: str) -> PromptPlanV2 | None:
        """尽量复用 prompt_plan_v2 作为结果卡片标题来源。"""

        plan_path = get_task_dir(task_id) / "prompt_plan_v2.json"
        if not plan_path.exists():
            return None
        return PromptPlanV2.model_validate_json(plan_path.read_text(encoding="utf-8"))

    def _load_qc_report(self, task_id: str) -> QCReport | None:
        """读取任务 QC 报告。"""

        qc_path = get_task_dir(task_id) / "qc_report.json"
        if not qc_path.exists():
            return None
        return QCReport.model_validate_json(qc_path.read_text(encoding="utf-8"))

    def _build_runtime_results(
        self,
        task: Task,
        prompt_plan: PromptPlanV2 | None,
        file_refs: list[dict[str, object]],
    ) -> list[TaskRuntimeImage]:
        """组装工作台结果卡片。"""

        planned_slots = self._build_slot_meta(task, prompt_plan)
        total_slots = max(len(planned_slots), len(file_refs), task.shot_count or 0)
        completed_count = len(file_refs)
        results: list[TaskRuntimeImage] = []

        for index in range(total_slots):
            slot = planned_slots[index] if index < len(planned_slots) else self._build_fallback_slot(index + 1)
            file_ref = file_refs[index] if index < len(file_refs) else None
            if file_ref is not None:
                results.append(
                    TaskRuntimeImage(
                        id=slot["id"],
                        title=slot["title"],
                        subtitle=slot["subtitle"],
                        status="completed",
                        image_url=self._build_task_file_url(task.task_id, str(file_ref["relative_path"])),
                        file_name=str(file_ref["relative_path"]),
                        width=int(file_ref["width"]) if file_ref.get("width") is not None else None,
                        height=int(file_ref["height"]) if file_ref.get("height") is not None else None,
                        generated_at=str(file_ref.get("generated_at") or ""),
                    )
                )
                continue

            results.append(
                TaskRuntimeImage(
                    id=slot["id"],
                    title=slot["title"],
                    subtitle=slot["subtitle"],
                    status=self._resolve_placeholder_status(task.status, index, completed_count),
                    image_url="",
                    file_name="",
                )
            )

        return results

    def _build_slot_meta(self, task: Task, prompt_plan: PromptPlanV2 | None) -> list[dict[str, str]]:
        """构造结果卡片标题信息。"""

        if prompt_plan is None or not prompt_plan.shots:
            return [self._build_fallback_slot(index + 1) for index in range(task.shot_count)]
        return [self._build_slot_from_prompt(index + 1, shot) for index, shot in enumerate(prompt_plan.shots)]

    def _build_slot_from_prompt(self, index: int, shot: PromptShot) -> dict[str, str]:
        """从 prompt shot 中提取结果卡片标题。"""

        title = shot.title_copy.strip() or f"图位 {index:02d}"
        subtitle = shot.shot_role.replace("_", " ").strip() or "待生成"
        return {"id": shot.shot_id or f"shot-{index:02d}", "title": title, "subtitle": subtitle}

    def _build_fallback_slot(self, index: int) -> dict[str, str]:
        """在 prompt plan 缺失时返回通用卡片标题。"""

        return {"id": f"slot-{index:02d}", "title": f"结果 {index:02d}", "subtitle": "等待生成"}

    def _list_result_files(self, task_dir: Path) -> list[dict[str, object]]:
        """读取任务目录中的已生成图片。"""

        final_dir = task_dir / "final"
        generated_dir = task_dir / "generated"
        image_paths = self._sorted_image_paths(final_dir)
        if not image_paths:
            image_paths = self._sorted_image_paths(generated_dir)

        results: list[dict[str, object]] = []
        for path in image_paths:
            width, height = self._read_image_size(path)
            generated_at = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
            results.append(
                {
                    "relative_path": path.relative_to(task_dir).as_posix(),
                    "file_name": path.name,
                    "width": width,
                    "height": height,
                    "generated_at": generated_at,
                }
            )
        return results

    def _sorted_image_paths(self, root: Path) -> list[Path]:
        """返回目录下按名称排序的图片列表。"""

        if not root.exists():
            return []
        return sorted(
            [path for path in root.iterdir() if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}],
            key=lambda item: item.name,
        )

    def _read_image_size(self, image_path: Path) -> tuple[int | None, int | None]:
        """读取图片尺寸，失败时回退空值。"""

        try:
            with Image.open(image_path) as image:
                return image.size
        except OSError:
            return None, None

    def _resolve_placeholder_status(self, task_status: TaskStatus, index: int, completed_count: int) -> str:
        """为未落盘的结果槽位推导状态。"""

        if task_status == TaskStatus.CREATED:
            return "queued"
        if task_status == TaskStatus.RUNNING:
            return "running" if index == completed_count else "queued"
        if task_status == TaskStatus.FAILED:
            return "failed" if index == completed_count else "queued"
        return "completed"

    def _build_runtime_message(
        self,
        task: Task,
        results: list[TaskRuntimeImage],
        queue_position: int | None,
        queue_size: int,
    ) -> str:
        """拼装工作台顶部提示文字。"""

        completed_count = sum(1 for item in results if item.status == "completed")
        total_count = len(results)
        if task.error_message:
            return task.error_message
        if task.status == TaskStatus.CREATED:
            if queue_position is not None and queue_position > 0:
                return f"任务排队中，前方还有 {queue_position} 个任务。"
            if queue_size > 0:
                return "任务已进入执行队列，等待 worker 开始处理。"
            return "任务已提交，等待开始执行。"
        if task.status == TaskStatus.RUNNING and total_count > 0:
            current_index = min(completed_count + 1, total_count)
            return f"正在生成第 {current_index} / {total_count} 张结果图。"
        if task.status == TaskStatus.REVIEW_REQUIRED:
            return f"结果已生成，共 {completed_count} 张，建议人工复核。"
        if task.status == TaskStatus.COMPLETED:
            return f"任务已完成，共生成 {completed_count} 张结果图。"
        return task.current_step_label or "任务执行失败。"

    def _resolve_export_urls(self, task_id: str) -> tuple[str, str]:
        """解析结果 ZIP 与完整任务包 ZIP 的访问地址。"""

        exports_dir = get_task_dir(task_id) / "exports"
        if not exports_dir.exists():
            return "", ""

        result_zip_path = self._find_latest_export(exports_dir, suffix="_final_images.zip")
        bundle_zip_path = self._find_latest_export(exports_dir, suffix="_full_task_bundle.zip")
        return (
            self._build_task_file_url(task_id, result_zip_path.relative_to(get_task_dir(task_id)).as_posix()) if result_zip_path else "",
            self._build_task_file_url(task_id, bundle_zip_path.relative_to(get_task_dir(task_id)).as_posix()) if bundle_zip_path else "",
        )

    def _find_latest_export(self, exports_dir: Path, *, suffix: str) -> Path | None:
        """返回最新导出文件。"""

        candidates = sorted(
            [path for path in exports_dir.iterdir() if path.is_file() and path.name.endswith(suffix)],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

    def _build_qc_summary(self, task_id: str) -> TaskRuntimeQCSummary:
        """压缩 QC 报告为工作台可读摘要。"""

        report = self._load_qc_report(task_id)
        if report is None:
            return TaskRuntimeQCSummary()
        warning_count = sum(1 for check in report.checks if check.status == "warning")
        failed_count = sum(1 for check in report.checks if check.status == "failed")
        return TaskRuntimeQCSummary(
            passed=report.passed,
            review_required=report.review_required,
            warning_count=warning_count,
            failed_count=failed_count,
        )

    def _build_task_file_url(self, task_id: str, relative_path: str) -> str:
        """构造前端可直接访问的任务文件地址。"""

        safe_path = quote(relative_path.replace("\\", "/"), safe="/")
        return f"/api/tasks/{task_id}/files/{safe_path}"
