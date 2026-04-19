"""API v1 任务查询服务。"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from urllib.parse import quote
import uuid

from backend.core.exceptions import AppException
from backend.db.enums import TaskStatus, TaskType
from backend.db.models.task import Task as DbTask
from backend.db.models.task import TaskEvent, TaskResult
from backend.db.models.user import User
from backend.db.session import get_async_session_factory
from backend.repositories.db.task_db_repository import TaskDbRepository
from backend.repositories.db.task_event_repository import TaskEventRepository
from backend.repositories.db.task_result_repository import TaskResultRepository
from backend.repositories.task_repository import TaskRepository
from backend.schemas.task import TaskSummary
from backend.schemas.task_v1 import (
    TaskDetailResponse,
    TaskEventResponse,
    TaskListItem,
    TaskListResponse,
    TaskResultResponse,
    TaskResultsResponse,
    TaskRuntimeResponse,
)
from backend.services.detail_runtime_service import DetailRuntimeService
from backend.services.task_runtime_service import TaskRuntimeService


class TaskQueryService:
    """面向 `/api/v1/tasks/*` 的任务查询编排层。"""

    def __init__(self) -> None:
        self.session_factory = get_async_session_factory()
        self.local_repo = TaskRepository()
        self.main_runtime_service = TaskRuntimeService()
        self.detail_runtime_service = DetailRuntimeService()

    async def list_tasks(
        self,
        *,
        current_user: User,
        page: int,
        page_size: int,
        task_type: TaskType | None,
        status: TaskStatus | None,
    ) -> TaskListResponse:
        """分页查询当前用户任务。"""

        safe_page = max(page, 1)
        safe_page_size = min(max(page_size, 1), 100)
        offset = (safe_page - 1) * safe_page_size
        async with self.session_factory() as session:
            task_repo = TaskDbRepository(session)
            tasks = await task_repo.list_by_user(
                current_user.id,
                offset=offset,
                limit=safe_page_size,
                task_type=task_type.value if task_type is not None else None,
                status=status.value if status is not None else None,
            )
            total = await task_repo.count_by_user(
                current_user.id,
                task_type=task_type.value if task_type is not None else None,
                status=status.value if status is not None else None,
            )
        return TaskListResponse(
            items=[self._to_list_item(task) for task in tasks],
            page=safe_page,
            page_size=safe_page_size,
            total=total,
        )

    async def get_task_detail(self, *, current_user: User, task_id: str) -> TaskDetailResponse:
        """读取单任务详情。"""

        task_row = await self._get_owned_task(current_user=current_user, task_id=task_id)
        return self._to_detail_response(task_row)

    async def get_task_runtime(self, *, current_user: User, task_id: str) -> TaskRuntimeResponse:
        """读取单任务 runtime 聚合。"""

        async with self.session_factory() as session:
            task_repo = TaskDbRepository(session)
            event_repo = TaskEventRepository(session)
            task_uuid = self._parse_task_id(task_id)
            task_row = await task_repo.get_by_id_for_user(task_uuid, user_id=current_user.id)
            if task_row is None:
                raise AppException(f"任务 {task_id} 不存在", code=4044, status_code=404)
            events = await event_repo.list_by_task_for_user(task_row.id, user_id=current_user.id)

        runtime_payload = self._load_runtime_payload(task_row)
        return TaskRuntimeResponse(
            task=self._to_detail_response(task_row),
            runtime=runtime_payload,
            events=[self._to_event_response(item) for item in events],
        )

    async def get_task_results(self, *, current_user: User, task_id: str) -> TaskResultsResponse:
        """返回任务结果摘要列表。"""

        async with self.session_factory() as session:
            task_repo = TaskDbRepository(session)
            result_repo = TaskResultRepository(session)
            task_uuid = self._parse_task_id(task_id)
            task_row = await task_repo.get_by_id_for_user(task_uuid, user_id=current_user.id)
            if task_row is None:
                raise AppException(f"任务 {task_id} 不存在", code=4044, status_code=404)
            result_rows = await result_repo.list_by_task_for_user(task_row.id, user_id=current_user.id)

        return TaskResultsResponse(
            task_id=task_row.id.hex,
            items=[self._to_result_response(task_row=task_row, result_row=item) for item in result_rows],
        )

    async def _get_owned_task(self, *, current_user: User, task_id: str) -> DbTask:
        async with self.session_factory() as session:
            task_repo = TaskDbRepository(session)
            task_row = await task_repo.get_by_id_for_user(self._parse_task_id(task_id), user_id=current_user.id)
        if task_row is None:
            raise AppException(f"任务 {task_id} 不存在", code=4044, status_code=404)
        return task_row

    def _load_runtime_payload(self, task_row: DbTask) -> dict[str, object] | None:
        """优先复用现有本地 runtime 聚合，失败时回退数据库快照。"""

        task_id = task_row.id.hex
        try:
            if task_row.task_type == TaskType.MAIN_IMAGE.value:
                return self.main_runtime_service.get_runtime(task_id).model_dump(mode="json")
            if task_row.task_type == TaskType.DETAIL_PAGE.value:
                summary = self.local_repo.get_task(task_id) or self._build_detail_summary(task_row)
                return self.detail_runtime_service.get_runtime(summary).model_dump(mode="json")
        except Exception:
            return task_row.runtime_snapshot
        return task_row.runtime_snapshot

    def _build_detail_summary(self, task_row: DbTask) -> TaskSummary:
        """当 JSON 索引缺失时，为旧 detail runtime 服务补一个最小摘要。"""

        return TaskSummary(
            task_id=task_row.id.hex,
            task_type="detail_page_v2",
            status=self._legacy_status(task_row.status),
            created_at=task_row.created_at,
            updated_at=task_row.updated_at,
            title=task_row.title or "",
            platform=task_row.platform or "",
            result_path=str(Path("outputs") / "tasks" / task_row.id.hex / "generated"),
            progress_percent=int(self._progress_float(task_row.progress_percent)),
            current_step=task_row.current_step or "",
            current_step_label="",
            result_count_completed=int((task_row.result_summary or {}).get("result_count", 0)),
            result_count_total=int((task_row.runtime_snapshot or {}).get("result_count_total", 0)),
            export_zip_path=str((task_row.result_summary or {}).get("export_zip_path", "")),
        )

    def _to_list_item(self, task_row: DbTask) -> TaskListItem:
        return TaskListItem(
            task_id=task_row.id.hex,
            task_type=TaskType(task_row.task_type),
            status=TaskStatus(task_row.status),
            title=task_row.title,
            platform=task_row.platform,
            biz_id=task_row.biz_id,
            current_step=task_row.current_step,
            progress_percent=self._progress_float(task_row.progress_percent),
            result_count=int((task_row.result_summary or {}).get("result_count", 0)),
            created_at=task_row.created_at,
            updated_at=task_row.updated_at,
            started_at=task_row.started_at,
            finished_at=task_row.finished_at,
        )

    def _to_detail_response(self, task_row: DbTask) -> TaskDetailResponse:
        return TaskDetailResponse(
            task_id=task_row.id.hex,
            task_type=TaskType(task_row.task_type),
            status=TaskStatus(task_row.status),
            title=task_row.title,
            platform=task_row.platform,
            biz_id=task_row.biz_id,
            source_task_id=task_row.source_task_id.hex if task_row.source_task_id is not None else None,
            parent_task_id=task_row.parent_task_id.hex if task_row.parent_task_id is not None else None,
            current_step=task_row.current_step,
            progress_percent=self._progress_float(task_row.progress_percent),
            input_summary=task_row.input_summary,
            params=task_row.params,
            runtime_snapshot=task_row.runtime_snapshot,
            result_summary=task_row.result_summary,
            error_code=task_row.error_code,
            error_message=task_row.error_message,
            retry_count=task_row.retry_count,
            created_at=task_row.created_at,
            updated_at=task_row.updated_at,
            started_at=task_row.started_at,
            finished_at=task_row.finished_at,
        )

    def _to_event_response(self, event_row: TaskEvent) -> TaskEventResponse:
        return TaskEventResponse(
            event_id=event_row.id.hex,
            event_type=event_row.event_type,
            level=event_row.level,
            step=event_row.step,
            message=event_row.message,
            payload=event_row.payload,
            created_at=event_row.created_at,
        )

    def _to_result_response(self, *, task_row: DbTask, result_row: TaskResult) -> TaskResultResponse:
        return TaskResultResponse(
            result_id=result_row.id.hex,
            result_type=result_row.result_type,
            page_no=result_row.page_no,
            shot_no=result_row.shot_no,
            version_no=result_row.version_no,
            parent_result_id=result_row.parent_result_id.hex if result_row.parent_result_id is not None else None,
            status=result_row.status,
            cos_key=result_row.cos_key,
            mime_type=result_row.mime_type,
            size_bytes=result_row.size_bytes,
            sha256=result_row.sha256,
            width=result_row.width,
            height=result_row.height,
            prompt_plan=result_row.prompt_plan,
            prompt_final=result_row.prompt_final,
            render_meta=result_row.render_meta,
            qc_status=result_row.qc_status,
            qc_score=float(result_row.qc_score) if result_row.qc_score is not None else None,
            is_primary=result_row.is_primary,
            file_url=self._build_result_file_url(task_row=task_row, result_row=result_row),
            download_url_api=f"/api/v1/files/{result_row.id.hex}/download-url",
            created_at=result_row.created_at,
            updated_at=result_row.updated_at,
        )

    def _build_result_file_url(self, *, task_row: DbTask, result_row: TaskResult) -> str:
        task_id = task_row.id.hex
        local_key = str((result_row.render_meta or {}).get("local_relative_path") or result_row.cos_key)
        safe_key = quote(local_key.replace("\\", "/"), safe="/")
        if task_row.task_type == TaskType.DETAIL_PAGE.value:
            return f"/api/detail/jobs/{task_id}/files/{safe_key}"
        return f"/api/tasks/{task_id}/files/{safe_key}"

    def _legacy_status(self, status: str) -> str:
        mapping = {
            TaskStatus.QUEUED.value: "created",
            TaskStatus.PENDING.value: "created",
            TaskStatus.RUNNING.value: "running",
            TaskStatus.SUCCEEDED.value: "completed",
            TaskStatus.FAILED.value: "failed",
            TaskStatus.PARTIAL_FAILED.value: "review_required",
            TaskStatus.CANCELLED.value: "failed",
        }
        return mapping.get(status, "created")

    def _parse_task_id(self, task_id: str) -> uuid.UUID:
        try:
            return uuid.UUID(task_id)
        except ValueError as exc:
            raise AppException(f"任务 ID 非法: {task_id}", code=4007, status_code=400) from exc

    def _progress_float(self, value: Decimal | float | int) -> float:
        if isinstance(value, Decimal):
            return float(value)
        return float(value)
