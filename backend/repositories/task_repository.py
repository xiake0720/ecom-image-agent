"""任务元数据仓储。

设计意图：当前阶段继续使用本地 JSON 持久化，接口层不直接感知索引文件细节。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from backend.core.config import get_settings
from backend.engine.core.paths import get_task_dir
from backend.engine.domain.task import Task
from backend.schemas.task import TaskSummary


class TaskRepository:
    """管理任务索引与单任务摘要。"""

    def __init__(self) -> None:
        settings = get_settings()
        self.root = settings.storage_root / "tasks"
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"

    def list_tasks(self) -> list[TaskSummary]:
        """读取任务列表，按更新时间倒序返回。"""

        rows = self._read_index()
        rows.sort(key=lambda item: item.get("updated_at", item.get("created_at", "")), reverse=True)
        return [self._enrich_summary(TaskSummary.model_validate(row)) for row in rows]

    def get_task(self, task_id: str) -> TaskSummary | None:
        """根据 task_id 查询任务摘要。"""

        for row in self._read_index():
            if row.get("task_id") == task_id:
                return self._enrich_summary(TaskSummary.model_validate(row))
        return None

    def save_task(self, task: TaskSummary) -> None:
        """新增或更新任务索引。"""

        rows = self._read_index()
        exists = False
        for index, row in enumerate(rows):
            if row.get("task_id") == task.task_id:
                rows[index] = task.model_dump(mode="json")
                exists = True
                break
        if not exists:
            rows.append(task.model_dump(mode="json"))
        self.index_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_runtime_task(self, task: Task, *, task_type: str = "main_image") -> TaskSummary:
        """把运行中的任务状态同步回摘要索引。"""

        existing = self.get_task(task.task_id)
        now = datetime.utcnow()
        effective_task_type = existing.task_type if existing is not None else task_type
        result_count_completed = self._count_result_files(task.task_id)
        result_count_total = max(task.shot_count, result_count_completed)
        export_zip_path = self._resolve_export_zip_path(task.task_id, task_type=effective_task_type)
        result_dir_name = "generated" if effective_task_type == "detail_page_v2" else "final"
        summary = TaskSummary(
            task_id=task.task_id,
            task_type=effective_task_type,
            status=task.status.value,
            created_at=existing.created_at if existing is not None else task.created_at,
            updated_at=now,
            title=(existing.title if existing is not None and existing.title else task.product_name),
            platform=(existing.platform if existing is not None and existing.platform else task.platform),
            result_path=str(Path(task.task_dir) / result_dir_name),
            progress_percent=task.progress_percent,
            current_step=task.current_step,
            current_step_label=task.current_step_label,
            result_count_completed=result_count_completed,
            result_count_total=result_count_total,
            export_zip_path=export_zip_path,
            provider_label=existing.provider_label if existing is not None else "",
            model_label=existing.model_label if existing is not None else "",
            detail_image_count=existing.detail_image_count if existing is not None else 0,
            background_image_count=existing.background_image_count if existing is not None else 0,
        )
        self.save_task(summary)
        return summary

    def create_task_summary(
        self,
        *,
        task_id: str,
        task_type: str,
        status: str,
        title: str,
        platform: str,
        result_path: str,
        created_at: datetime | None = None,
        provider_label: str = "",
        model_label: str = "",
        detail_image_count: int = 0,
        background_image_count: int = 0,
    ) -> TaskSummary:
        """构造统一任务摘要对象。"""

        now = datetime.utcnow()
        return TaskSummary(
            task_id=task_id,
            task_type=task_type,
            status=status,
            created_at=created_at or now,
            updated_at=now,
            title=title,
            platform=platform,
            result_path=result_path,
            provider_label=provider_label,
            model_label=model_label,
            detail_image_count=detail_image_count,
            background_image_count=background_image_count,
        )

    def _read_index(self) -> list[dict[str, object]]:
        """读取索引文件，不存在时返回空列表。"""

        if not self.index_path.exists():
            return []
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _enrich_summary(self, summary: TaskSummary) -> TaskSummary:
        """用 task manifest 和目录状态补齐摘要。"""

        manifest_path = get_task_dir(summary.task_id) / "task.json"
        if not manifest_path.exists():
            return summary

        task = Task.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        completed = self._count_result_files(summary.task_id)
        total = max(task.shot_count, completed)
        return summary.model_copy(
            update={
                "status": task.status.value,
                "progress_percent": task.progress_percent,
                "current_step": task.current_step,
                "current_step_label": task.current_step_label,
                "result_count_completed": completed,
                "result_count_total": total,
                "export_zip_path": self._resolve_export_zip_path(summary.task_id, task_type=summary.task_type),
                "provider_label": summary.provider_label,
                "model_label": summary.model_label,
                "detail_image_count": summary.detail_image_count,
                "background_image_count": summary.background_image_count,
            }
        )

    def _count_result_files(self, task_id: str) -> int:
        """统计任务已落盘的最终结果图数量。"""

        task_dir = get_task_dir(task_id)
        final_dir = task_dir / "final"
        generated_dir = task_dir / "generated"
        target_dir = final_dir if final_dir.exists() and any(final_dir.iterdir()) else generated_dir
        if not target_dir.exists():
            return 0
        return len([path for path in target_dir.iterdir() if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}])

    def _resolve_export_zip_path(self, task_id: str, *, task_type: str = "main_image") -> str:
        """返回结果图 ZIP 的相对路径。"""

        exports_dir = get_task_dir(task_id) / "exports"
        if not exports_dir.exists():
            return ""
        if task_type == "detail_page_v2":
            detail_bundle = exports_dir / "detail_bundle.zip"
            if detail_bundle.exists():
                return str(detail_bundle.relative_to(get_task_dir(task_id)).as_posix())
        candidates = sorted(
            [path for path in exports_dir.iterdir() if path.is_file() and path.name.endswith("_final_images.zip")],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return ""
        return str(candidates[0].relative_to(get_task_dir(task_id)).as_posix())
