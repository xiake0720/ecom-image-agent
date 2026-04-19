"""任务数据库兼容写入服务。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import uuid

from PIL import Image

from backend.core.config import get_settings
from backend.core.security import hash_password
from backend.db.enums import (
    TaskAssetScanStatus,
    TaskEventLevel,
    TaskEventType,
    TaskResultStatus,
    TaskStatus,
    TaskType,
    UserStatus,
)
from backend.db.models.task import Task as DbTask
from backend.db.models.task import TaskAsset, TaskEvent, TaskResult
from backend.db.models.user import User
from backend.db.session import get_async_session_factory
from backend.engine.core.paths import get_task_dir
from backend.engine.domain.asset import Asset, AssetType
from backend.engine.domain.task import Task as LegacyTask
from backend.engine.domain.task import TaskStatus as LegacyTaskStatus
from backend.repositories.db.task_asset_repository import TaskAssetRepository
from backend.repositories.db.task_db_repository import TaskDbRepository
from backend.repositories.db.task_event_repository import TaskEventRepository
from backend.repositories.db.task_result_repository import TaskResultRepository
from backend.repositories.db.user_repository import UserRepository
from backend.repositories.task_repository import TaskRepository
from backend.schemas.detail import DetailPageAssetRef, DetailPageRenderResult
from backend.schemas.task import TaskSummary
from backend.services.storage.cos_service import CosService


@dataclass(frozen=True, slots=True)
class DbTaskAssetInput:
    """兼容层写入 `task_assets` 时使用的素材描述。"""

    role: str
    source_type: str
    file_name: str | None
    local_path: Path
    sort_order: int = 0
    width: int | None = None
    height: int | None = None
    duration_ms: int | None = None
    source_task_id: str | None = None
    source_result_file: str | None = None
    metadata: dict[str, object] | None = None


class TaskDbMirrorService:
    """把现有本地任务元数据镜像写入 PostgreSQL。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.session_factory = get_async_session_factory()
        self.local_repo = TaskRepository()
        self.cos_service = CosService()

    async def create_task_record(
        self,
        *,
        task_id: str,
        current_user: User | None,
        task_type: TaskType,
        title: str,
        platform: str,
        input_summary: dict[str, object] | None = None,
        params: dict[str, object] | None = None,
        source_task_id: str | None = None,
        parent_task_id: str | None = None,
        assets: list[DbTaskAssetInput] | None = None,
        created_at: datetime | None = None,
    ) -> None:
        """创建兼容任务主记录，并把输入素材同步到数据库。"""

        async with self.session_factory() as session:
            task_repo = TaskDbRepository(session)
            asset_repo = TaskAssetRepository(session)
            event_repo = TaskEventRepository(session)
            user_repo = UserRepository(session)
            result_repo = TaskResultRepository(session)

            user_id = await self._resolve_effective_user_id(user_repo=user_repo, current_user=current_user)
            task_uuid = self._parse_task_id(task_id)
            existing = await task_repo.get_by_id(task_uuid)
            now = self._utcnow()
            task_row = existing or DbTask(id=task_uuid, user_id=user_id, task_type=task_type.value)
            task_row.user_id = user_id
            task_row.task_type = task_type.value
            task_row.status = TaskStatus.QUEUED.value
            task_row.title = title or None
            task_row.platform = platform or None
            task_row.source_task_id = self._parse_optional_task_id(source_task_id)
            task_row.parent_task_id = self._parse_optional_task_id(parent_task_id)
            task_row.current_step = "queued"
            task_row.progress_percent = Decimal("0")
            task_row.input_summary = input_summary
            task_row.params = params
            task_row.runtime_snapshot = {
                "legacy_task_id": task_id,
                "legacy_status": LegacyTaskStatus.CREATED.value,
                "current_step": "queued",
                "progress_percent": 0,
            }
            task_row.result_summary = {"result_count": 0}
            if existing is None:
                task_row.created_at = self._ensure_aware_datetime(created_at or now)
            await task_repo.upsert(task_row)

            for asset_input in assets or []:
                asset_row = await self._build_asset_row(
                    asset_input=asset_input,
                    task_id=task_uuid,
                    user_id=user_id,
                    result_repo=result_repo,
                )
                await asset_repo.upsert(asset_row)

            await event_repo.upsert(
                self._build_event_row(
                    task_id=task_uuid,
                    user_id=user_id,
                    event_type=TaskEventType.TASK_CREATED,
                    level=TaskEventLevel.INFO,
                    step="queued",
                    message="任务已写入数据库兼容层",
                    payload={"task_type": task_type.value},
                )
            )
            await event_repo.upsert(
                self._build_event_row(
                    task_id=task_uuid,
                    user_id=user_id,
                    event_type=TaskEventType.TASK_QUEUED,
                    level=TaskEventLevel.INFO,
                    step="queued",
                    message="任务已进入执行队列",
                    payload={"progress_percent": 0},
                )
            )
            await session.commit()

    async def sync_runtime_from_local(self, *, task_id: str, task_type: TaskType | None = None) -> None:
        """根据本地 task.json 和产物目录，把最新运行态同步到数据库。"""

        summary = self.local_repo.get_task(task_id)
        task_path = get_task_dir(task_id) / "task.json"
        if not task_path.exists():
            return
        legacy_task = LegacyTask.model_validate_json(task_path.read_text(encoding="utf-8"))
        effective_task_type = task_type or self._map_task_type(summary.task_type if summary is not None else "")
        async with self.session_factory() as session:
            task_repo = TaskDbRepository(session)
            event_repo = TaskEventRepository(session)
            result_repo = TaskResultRepository(session)
            user_repo = UserRepository(session)

            task_uuid = self._parse_task_id(task_id)
            task_row = await task_repo.get_by_id(task_uuid)
            if task_row is None:
                user_id = await self._resolve_effective_user_id(user_repo=user_repo, current_user=None)
                task_row = DbTask(id=task_uuid, user_id=user_id, task_type=effective_task_type.value)
            task_row.task_type = effective_task_type.value
            task_row.status = self._map_status(legacy_task.status).value
            task_row.title = (summary.title if summary is not None else legacy_task.product_name) or None
            task_row.platform = (summary.platform if summary is not None else legacy_task.platform) or None
            task_row.current_step = legacy_task.current_step or None
            task_row.progress_percent = Decimal(str(legacy_task.progress_percent or 0))
            task_row.error_message = legacy_task.error_message or None
            task_row.runtime_snapshot = self._build_runtime_snapshot(summary=summary, legacy_task=legacy_task)

            results_payload = self._build_result_rows(
                task_id=task_id,
                task_uuid=task_uuid,
                user_id=task_row.user_id,
                task_type=effective_task_type,
            )
            task_row.result_summary = self._build_result_summary(summary=summary, results=results_payload)
            if task_row.status in {TaskStatus.RUNNING, TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.PARTIAL_FAILED}:
                task_row.started_at = task_row.started_at or self._ensure_aware_datetime(summary.created_at if summary is not None else legacy_task.created_at)
            if task_row.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.PARTIAL_FAILED, TaskStatus.CANCELLED}:
                task_row.finished_at = self._resolve_finished_at(summary=summary, results=results_payload)
            await task_repo.upsert(task_row)

            for result_row in results_payload:
                await result_repo.upsert(result_row)

            for event_row in self._build_state_events(task_row=task_row, legacy_task=legacy_task, result_count=len(results_payload)):
                await event_repo.upsert(event_row)

            await event_repo.upsert(
                self._build_event_row(
                    task_id=task_uuid,
                    user_id=task_row.user_id,
                    event_type=TaskEventType.TASK_RESULTS_SYNCED,
                    level=TaskEventLevel.INFO,
                    step=legacy_task.current_step or None,
                    message="任务结果摘要已同步到数据库",
                    payload={"result_count": len(results_payload)},
                )
            )
            await session.commit()

    def sync_runtime_from_local_sync(self, *, task_id: str, task_type: TaskType | None = None) -> None:
        """供后台线程调用的同步包装器。"""

        asyncio.run(self.sync_runtime_from_local(task_id=task_id, task_type=task_type))

    @staticmethod
    def build_main_image_asset_inputs(assets: list[Asset]) -> list[DbTaskAssetInput]:
        """把主图上传素材转换成数据库素材输入。"""

        role_map = {
            AssetType.WHITE_BG: "white_bg",
            AssetType.DETAIL: "detail",
            AssetType.BACKGROUND_STYLE: "background_style",
            AssetType.PRODUCT: "product",
            AssetType.OTHER: "other",
        }
        rows: list[DbTaskAssetInput] = []
        for index, asset in enumerate(assets):
            rows.append(
                DbTaskAssetInput(
                    role=role_map.get(asset.asset_type, "other"),
                    source_type="upload",
                    file_name=asset.filename,
                    local_path=Path(asset.local_path),
                    sort_order=index,
                    width=asset.width,
                    height=asset.height,
                )
            )
        return rows

    @staticmethod
    def build_detail_asset_inputs(task_id: str, assets: list[DetailPageAssetRef]) -> list[DbTaskAssetInput]:
        """把详情图素材引用转换成数据库素材输入。"""

        task_dir = get_task_dir(task_id)
        rows: list[DbTaskAssetInput] = []
        for index, asset in enumerate(assets):
            rows.append(
                DbTaskAssetInput(
                    role=asset.role,
                    source_type=asset.source_type,
                    file_name=asset.file_name,
                    local_path=task_dir / asset.relative_path,
                    sort_order=index,
                    width=asset.width,
                    height=asset.height,
                    source_task_id=asset.source_task_id or None,
                    source_result_file=asset.source_result_file or None,
                    metadata={"asset_id": asset.asset_id},
                )
            )
        return rows

    async def _resolve_effective_user_id(self, *, user_repo: UserRepository, current_user: User | None) -> uuid.UUID:
        """旧接口未接鉴权时，使用禁用的兼容账号承接任务所有权。"""

        if current_user is not None:
            return current_user.id

        compat_email = self.settings.compat_task_user_email.strip().lower()
        existing = await user_repo.get_by_email(compat_email)
        if existing is not None:
            return existing.id

        compat_user = User(
            id=uuid.uuid4(),
            email=compat_email,
            password_hash=hash_password(uuid.uuid4().hex),
            nickname=self.settings.compat_task_user_nickname,
            status=UserStatus.DISABLED.value,
        )
        user_repo.add(compat_user)
        await self._flush_safe(user_repo.session)
        return compat_user.id

    async def _build_asset_row(
        self,
        *,
        asset_input: DbTaskAssetInput,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        result_repo: TaskResultRepository,
    ) -> TaskAsset:
        """构造 `task_assets` 行，并尽量补齐来源结果外键。"""

        relative_path = self._relative_task_path(asset_input.local_path)
        mime_type = self._guess_mime_type(asset_input.local_path)
        width, height = self._read_image_size(asset_input.local_path, asset_input.width, asset_input.height)
        cos_key = self._sync_file_to_cos_if_enabled(
            local_path=asset_input.local_path,
            user_id=user_id,
            task_id=task_id,
            kind="inputs",
            file_name=asset_input.file_name or relative_path,
            mime_type=mime_type,
            fallback_key=relative_path,
        )
        source_task_result_id = await self._resolve_source_task_result_id(
            result_repo=result_repo,
            source_task_id=asset_input.source_task_id,
            source_result_file=asset_input.source_result_file,
        )
        return TaskAsset(
            id=self._uuid5(f"task-asset:{task_id.hex}:{relative_path}"),
            task_id=task_id,
            user_id=user_id,
            role=asset_input.role,
            source_type=asset_input.source_type,
            source_task_result_id=source_task_result_id,
            file_name=asset_input.file_name,
            cos_key=cos_key,
            mime_type=mime_type,
            size_bytes=asset_input.local_path.stat().st_size,
            sha256=self._sha256(asset_input.local_path),
            width=width,
            height=height,
            duration_ms=asset_input.duration_ms,
            scan_status=TaskAssetScanStatus.PENDING.value,
            metadata_json=asset_input.metadata,
            sort_order=asset_input.sort_order,
        )

    async def _resolve_source_task_result_id(
        self,
        *,
        result_repo: TaskResultRepository,
        source_task_id: str | None,
        source_result_file: str | None,
    ) -> uuid.UUID | None:
        """如果上游主图结果已经被镜像，则建立 asset -> task_result 的关系。"""

        if not source_task_id or not source_result_file:
            return None
        source_uuid = self._parse_optional_task_id(source_task_id)
        if source_uuid is None:
            return None
        result = await result_repo.find_by_task_and_cos_key(source_uuid, cos_key=source_result_file)
        if result is None:
            for candidate in await result_repo.list_by_task(source_uuid):
                if (candidate.render_meta or {}).get("local_relative_path") == source_result_file:
                    result = candidate
                    break
        return result.id if result is not None else None

    def _build_result_rows(
        self,
        *,
        task_id: str,
        task_uuid: uuid.UUID,
        user_id: uuid.UUID,
        task_type: TaskType,
    ) -> list[TaskResult]:
        """扫描本地产物目录，构造 `task_results` 镜像行。"""

        task_dir = get_task_dir(task_id)
        if task_type == TaskType.DETAIL_PAGE:
            return self._build_detail_results(task_dir=task_dir, task_id=task_id, task_uuid=task_uuid, user_id=user_id)
        return self._build_main_results(task_dir=task_dir, task_id=task_id, task_uuid=task_uuid, user_id=user_id)

    def _build_main_results(
        self,
        *,
        task_dir: Path,
        task_id: str,
        task_uuid: uuid.UUID,
        user_id: uuid.UUID,
        result_type: str = TaskType.MAIN_IMAGE.value,
    ) -> list[TaskResult]:
        """扫描主图结果目录。"""

        target_dir = task_dir / "final"
        if not target_dir.exists() or not any(target_dir.iterdir()):
            target_dir = task_dir / "generated"
        image_paths = self._sorted_image_paths(target_dir)
        rows: list[TaskResult] = []
        for index, path in enumerate(image_paths, start=1):
            relative_path = path.relative_to(task_dir).as_posix()
            width, height = self._read_image_size(path)
            mime_type = self._guess_mime_type(path)
            cos_key = self._sync_file_to_cos_if_enabled(
                local_path=path,
                user_id=user_id,
                task_id=task_uuid,
                kind="results",
                file_name=relative_path,
                mime_type=mime_type,
                fallback_key=relative_path,
            )
            rows.append(
                TaskResult(
                    id=self._uuid5(f"task-result:{task_id}:{relative_path}"),
                    task_id=task_uuid,
                    user_id=user_id,
                    result_type=result_type,
                    shot_no=index,
                    status=TaskResultStatus.SUCCEEDED.value,
                    cos_key=cos_key,
                    mime_type=mime_type,
                    size_bytes=path.stat().st_size,
                    sha256=self._sha256(path),
                    width=width,
                    height=height,
                    render_meta={"source": "cos" if self.cos_service.is_enabled() else "local_file", "local_relative_path": relative_path},
                    is_primary=index == 1,
                )
            )
        return rows

    def _build_detail_results(
        self,
        *,
        task_dir: Path,
        task_id: str,
        task_uuid: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[TaskResult]:
        """优先根据详情图 render report 镜像结果。"""

        report_path = task_dir / "generated" / "detail_render_report.json"
        if not report_path.exists():
            return self._build_main_results(
                task_dir=task_dir,
                task_id=task_id,
                task_uuid=task_uuid,
                user_id=user_id,
                result_type=TaskType.DETAIL_PAGE.value,
            )

        render_rows = [
            DetailPageRenderResult.model_validate(item)
            for item in json.loads(report_path.read_text(encoding="utf-8"))
            if isinstance(item, dict)
        ]
        rows: list[TaskResult] = []
        for index, render_row in enumerate(render_rows, start=1):
            if render_row.status != "completed" or not render_row.relative_path:
                continue
            image_path = task_dir / render_row.relative_path
            if not image_path.exists():
                continue
            width, height = self._read_image_size(image_path, render_row.width, render_row.height)
            mime_type = self._guess_mime_type(image_path)
            cos_key = self._sync_file_to_cos_if_enabled(
                local_path=image_path,
                user_id=user_id,
                task_id=task_uuid,
                kind="results",
                file_name=render_row.relative_path,
                mime_type=mime_type,
                fallback_key=render_row.relative_path,
            )
            rows.append(
                TaskResult(
                    id=self._uuid5(f"task-result:{task_id}:{render_row.relative_path}"),
                    task_id=task_uuid,
                    user_id=user_id,
                    result_type=TaskType.DETAIL_PAGE.value,
                    page_no=index,
                    version_no=max(1, render_row.retry_count + 1),
                    status=TaskResultStatus.SUCCEEDED.value,
                    cos_key=cos_key,
                    mime_type=mime_type,
                    size_bytes=image_path.stat().st_size,
                    sha256=self._sha256(image_path),
                    width=width,
                    height=height,
                    prompt_final={"page_id": render_row.page_id, "page_title": render_row.page_title},
                    render_meta={
                        "provider_name": render_row.provider_name,
                        "model_name": render_row.model_name,
                        "reference_roles": render_row.reference_roles,
                        "retry_count": render_row.retry_count,
                        "source": "cos" if self.cos_service.is_enabled() else "local_file",
                        "local_relative_path": render_row.relative_path,
                    },
                    is_primary=index == 1,
                )
            )
        return rows

    def _build_runtime_snapshot(self, *, summary: TaskSummary | None, legacy_task: LegacyTask) -> dict[str, object]:
        """把旧任务 manifest 压缩成数据库可查询的 runtime 摘要。"""

        return {
            "legacy_task_id": legacy_task.task_id,
            "legacy_status": legacy_task.status.value,
            "current_step": legacy_task.current_step,
            "current_step_label": legacy_task.current_step_label,
            "progress_percent": legacy_task.progress_percent,
            "error_message": legacy_task.error_message,
            "result_count_completed": summary.result_count_completed if summary is not None else 0,
            "result_count_total": summary.result_count_total if summary is not None else legacy_task.shot_count,
            "export_zip_path": summary.export_zip_path if summary is not None else "",
        }

    def _build_result_summary(self, *, summary: TaskSummary | None, results: list[TaskResult]) -> dict[str, object]:
        """生成任务结果摘要，供列表和详情接口直接读取。"""

        primary = next((item for item in results if item.is_primary), None)
        return {
            "result_count": len(results),
            "primary_result_id": primary.id.hex if primary is not None else None,
            "primary_cos_key": primary.cos_key if primary is not None else None,
            "export_zip_path": summary.export_zip_path if summary is not None else "",
        }

    def _build_state_events(self, *, task_row: DbTask, legacy_task: LegacyTask, result_count: int) -> list[TaskEvent]:
        """只记录关键状态变化，避免把高频进度写成噪音事件。"""

        status = TaskStatus(task_row.status)
        payload = {
            "status": task_row.status,
            "progress_percent": float(task_row.progress_percent),
            "result_count": result_count,
        }
        if status == TaskStatus.RUNNING:
            return [
                self._build_event_row(
                    task_id=task_row.id,
                    user_id=task_row.user_id,
                    event_type=TaskEventType.TASK_RUNNING,
                    level=TaskEventLevel.INFO,
                    step=legacy_task.current_step or None,
                    message=legacy_task.current_step_label or "任务执行中",
                    payload=payload,
                )
            ]
        if status == TaskStatus.SUCCEEDED:
            return [
                self._build_event_row(
                    task_id=task_row.id,
                    user_id=task_row.user_id,
                    event_type=TaskEventType.TASK_SUCCEEDED,
                    level=TaskEventLevel.INFO,
                    step=legacy_task.current_step or None,
                    message="任务执行完成",
                    payload=payload,
                )
            ]
        if status == TaskStatus.PARTIAL_FAILED:
            return [
                self._build_event_row(
                    task_id=task_row.id,
                    user_id=task_row.user_id,
                    event_type=TaskEventType.TASK_PARTIAL_FAILED,
                    level=TaskEventLevel.WARNING,
                    step=legacy_task.current_step or None,
                    message=legacy_task.current_step_label or "任务部分失败，需要人工复核",
                    payload=payload,
                )
            ]
        if status == TaskStatus.FAILED:
            return [
                self._build_event_row(
                    task_id=task_row.id,
                    user_id=task_row.user_id,
                    event_type=TaskEventType.TASK_FAILED,
                    level=TaskEventLevel.ERROR,
                    step=legacy_task.current_step or None,
                    message=legacy_task.error_message or legacy_task.current_step_label or "任务执行失败",
                    payload=payload,
                )
            ]
        if status == TaskStatus.CANCELLED:
            return [
                self._build_event_row(
                    task_id=task_row.id,
                    user_id=task_row.user_id,
                    event_type=TaskEventType.TASK_CANCELLED,
                    level=TaskEventLevel.WARNING,
                    step=legacy_task.current_step or None,
                    message="任务已取消",
                    payload=payload,
                )
            ]
        return [
            self._build_event_row(
                task_id=task_row.id,
                user_id=task_row.user_id,
                event_type=TaskEventType.TASK_QUEUED,
                level=TaskEventLevel.INFO,
                step=legacy_task.current_step or None,
                message=legacy_task.current_step_label or "任务排队中",
                payload=payload,
            )
        ]

    def _build_event_row(
        self,
        *,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        event_type: TaskEventType,
        level: TaskEventLevel,
        step: str | None,
        message: str,
        payload: dict[str, object] | None,
    ) -> TaskEvent:
        """构造可幂等 upsert 的事件行。"""

        event_key = f"task-event:{task_id.hex}:{event_type.value}:{step or '-'}"
        return TaskEvent(
            id=self._uuid5(event_key),
            task_id=task_id,
            user_id=user_id,
            event_type=event_type.value,
            level=level.value,
            step=step,
            message=message,
            payload=payload,
        )

    def _resolve_finished_at(self, *, summary: TaskSummary | None, results: list[TaskResult]) -> datetime | None:
        """尽量给终态任务补上 finished_at。"""

        if summary is not None:
            return self._ensure_aware_datetime(summary.updated_at)
        return self._utcnow()

    def _map_status(self, status: LegacyTaskStatus) -> TaskStatus:
        """把旧 workflow 状态映射到数据库枚举。"""

        mapping = {
            LegacyTaskStatus.CREATED: TaskStatus.QUEUED,
            LegacyTaskStatus.RUNNING: TaskStatus.RUNNING,
            LegacyTaskStatus.COMPLETED: TaskStatus.SUCCEEDED,
            LegacyTaskStatus.REVIEW_REQUIRED: TaskStatus.PARTIAL_FAILED,
            LegacyTaskStatus.FAILED: TaskStatus.FAILED,
        }
        return mapping[status]

    def _map_task_type(self, task_type: str) -> TaskType:
        """把旧 task_type 文本映射到集中枚举。"""

        if task_type == "detail_page_v2":
            return TaskType.DETAIL_PAGE
        if task_type == TaskType.IMAGE_EDIT.value:
            return TaskType.IMAGE_EDIT
        return TaskType.MAIN_IMAGE

    def _parse_task_id(self, task_id: str) -> uuid.UUID:
        """兼容无连字符 hex task_id。"""

        return uuid.UUID(task_id)

    def _parse_optional_task_id(self, task_id: str | None) -> uuid.UUID | None:
        if not task_id:
            return None
        try:
            return self._parse_task_id(task_id)
        except ValueError:
            return None

    def _relative_task_path(self, path: Path) -> str:
        """把本地文件路径稳定映射为任务相对路径。"""

        task_id = self._find_task_id_in_path(path)
        if task_id is None:
            return path.name
        return path.relative_to(get_task_dir(task_id)).as_posix()

    def _find_task_id_in_path(self, path: Path) -> str | None:
        for index, part in enumerate(path.parts):
            if part == "tasks" and index + 1 < len(path.parts):
                return path.parts[index + 1]
        return None

    def _sorted_image_paths(self, root: Path) -> list[Path]:
        if not root.exists():
            return []
        return sorted(
            [path for path in root.iterdir() if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}],
            key=lambda item: item.name,
        )

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _guess_mime_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"

    def _sync_file_to_cos_if_enabled(
        self,
        *,
        local_path: Path,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        kind: str,
        file_name: str,
        mime_type: str,
        fallback_key: str,
    ) -> str:
        """COS 启用时上传文件并返回对象 key；否则保持本地相对路径兼容。"""

        if not self.cos_service.is_enabled():
            return fallback_key
        cos_key = self.cos_service.build_task_object_key(
            user_id=user_id,
            task_id=task_id,
            kind=kind,
            file_name=file_name,
        )
        self.cos_service.upload_file(local_path=local_path, key=cos_key, mime_type=mime_type)
        return cos_key

    def _read_image_size(
        self,
        path: Path,
        width: int | None = None,
        height: int | None = None,
    ) -> tuple[int | None, int | None]:
        if width is not None and height is not None:
            return width, height
        try:
            with Image.open(path) as image:
                return image.size
        except OSError:
            return width, height

    def _utcnow(self) -> datetime:
        return datetime.now(timezone.utc)

    def _ensure_aware_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _uuid5(self, value: str) -> uuid.UUID:
        return uuid.uuid5(uuid.NAMESPACE_URL, value)

    async def _flush_safe(self, session) -> None:
        """兼容 SQLite 测试环境，确保兼容用户主键可用。"""

        await session.flush()

