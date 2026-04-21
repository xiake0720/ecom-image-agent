"""Result image edit orchestration service."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import logging
from pathlib import Path
import shutil
from threading import Thread
from time import perf_counter
from urllib.parse import quote
import uuid

from PIL import Image

from backend.core.config import get_settings
from backend.core.exceptions import AppException
from backend.core.logging import format_log_event
from backend.db.enums import ImageEditMode, ImageEditStatus, TaskEventLevel, TaskEventType, TaskResultStatus, TaskStatus, TaskType
from backend.db.models.task import ImageEdit, Task as DbTask
from backend.db.models.task import TaskEvent, TaskResult
from backend.db.models.user import User
from backend.db.session import get_async_session_factory
from backend.engine.core.config import get_settings as get_engine_settings
from backend.engine.core.paths import ensure_task_dirs, get_task_dir
from backend.engine.domain.asset import Asset, AssetType
from backend.engine.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from backend.engine.providers.router import build_capability_bindings
from backend.repositories.db.image_edit_repository import ImageEditRepository
from backend.repositories.db.task_db_repository import TaskDbRepository
from backend.repositories.db.task_event_repository import TaskEventRepository
from backend.repositories.db.task_result_repository import TaskResultRepository
from backend.schemas.image_edit import ImageEditCreateRequest, ImageEditListResponse, ImageEditResponse
from backend.schemas.task_v1 import TaskResultResponse
from backend.services.storage.cos_service import CosService


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PreparedImageEdit:
    edit_id: uuid.UUID
    edit_task_id: uuid.UUID
    user_id: uuid.UUID
    source_task_id: uuid.UUID
    source_result_id: uuid.UUID
    source_result_type: str
    source_result_cos_key: str
    source_width: int | None
    source_height: int | None
    source_path: Path
    selection_type: str
    selection: dict[str, object]
    instruction: str
    mode: str
    title: str | None
    platform: str | None


@dataclass(frozen=True, slots=True)
class GeneratedEditResult:
    output_path: Path
    relative_path: str
    width: int | None
    height: int | None
    provider_name: str
    model_name: str
    prompt_plan: dict[str, object]
    prompt_final: dict[str, object]
    usage: dict[str, object] | None


class ImageEditService:
    """Create, query, and execute single-image edit tasks."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.session_factory = get_async_session_factory()
        self.cos_service = CosService()

    async def create_edit(
        self,
        *,
        current_user: User,
        result_id: str,
        payload: ImageEditCreateRequest,
        dispatch: bool = True,
    ) -> ImageEditResponse:
        """Create an image edit task scoped to the current user."""

        started_at = perf_counter()
        source_result_uuid = self._parse_uuid(result_id, field_name="result_id")
        edit_task_id = uuid.uuid4()
        edit_id = uuid.uuid4()
        now = self._utcnow()
        selection = payload.selection.model_dump(mode="json")
        execution_backend = self._resolve_execution_backend()
        mode = ImageEditMode.FULL_IMAGE_CONSTRAINED_REGENERATION.value
        logger.info(
            format_log_event(
                "image_edit_started",
                user_id=current_user.id.hex,
                result_id=source_result_uuid.hex,
                task_id=edit_task_id.hex,
                mode=mode,
                dispatch=dispatch,
                selection_type=payload.selection_type,
                instruction_length=len(payload.instruction),
            )
        )

        async with self.session_factory() as session:
            task_repo = TaskDbRepository(session)
            result_repo = TaskResultRepository(session)
            edit_repo = ImageEditRepository(session)
            event_repo = TaskEventRepository(session)

            source_result = await result_repo.get_by_id_for_user(source_result_uuid, user_id=current_user.id)
            if source_result is None:
                raise AppException(f"结果 {result_id} 不存在", code=4045, status_code=404)
            if not source_result.mime_type.startswith("image/"):
                raise AppException("当前结果不是可编辑图片", code=4008, status_code=400)

            source_task = await task_repo.get_by_id_for_user(source_result.task_id, user_id=current_user.id)
            if source_task is None:
                raise AppException(f"结果 {result_id} 不存在", code=4045, status_code=404)

            edit_task = DbTask(
                id=edit_task_id,
                user_id=current_user.id,
                task_type=TaskType.IMAGE_EDIT.value,
                status=TaskStatus.QUEUED.value,
                title=f"图片二次优化 - {source_task.title or source_result.result_type}",
                platform=source_task.platform,
                source_task_id=source_task.id,
                parent_task_id=source_task.id,
                current_step="queued",
                progress_percent=Decimal("0"),
                queued_at=now,
                input_summary={
                    "source_result_id": source_result.id.hex,
                    "source_task_id": source_task.id.hex,
                    "selection_type": payload.selection_type,
                    "selection": selection,
                    "instruction": payload.instruction,
                },
                params={"mode": mode, "execution_backend": execution_backend},
                runtime_snapshot={
                    "mode": mode,
                    "status": TaskStatus.QUEUED.value,
                    "current_step": "queued",
                    "progress_percent": 0,
                    "source_result_id": source_result.id.hex,
                    "edited_result_id": None,
                },
                result_summary={"result_count": 0},
            )
            task_repo.add(edit_task)

            edit_row = ImageEdit(
                id=edit_id,
                source_result_id=source_result.id,
                edit_task_id=edit_task_id,
                user_id=current_user.id,
                selection_type=payload.selection_type,
                selection=selection,
                instruction=payload.instruction,
                mode=mode,
                status=ImageEditStatus.QUEUED.value,
                metadata_json={
                    "source_task_id": source_task.id.hex,
                    "source_result_type": source_result.result_type,
                    "execution_backend": execution_backend,
                },
            )
            edit_repo.add(edit_row)
            for event in self._build_initial_events(
                task_id=edit_task_id,
                user_id=current_user.id,
                source_result_id=source_result.id.hex,
                mode=mode,
                execution_backend=execution_backend,
            ):
                event_repo.add(event)
            await session.commit()
            logger.info(
                format_log_event(
                    "task_create_persisted",
                    user_id=current_user.id.hex,
                    result_id=source_result_uuid.hex,
                    task_id=edit_task_id.hex,
                    mode=mode,
                    elapsed_ms=_elapsed_ms(started_at),
                )
            )

        if dispatch:
            self._dispatch_task(edit_task_id.hex)

        async with self.session_factory() as session:
            created = await ImageEditRepository(session).get_by_id(edit_id)
            if created is None:
                raise AppException("图片编辑任务创建失败", code=5003, status_code=500)
            logger.info(
                format_log_event(
                    "image_edit_succeeded",
                    user_id=current_user.id.hex,
                    result_id=source_result_uuid.hex,
                    task_id=edit_task_id.hex,
                    edit_id=edit_id.hex,
                    mode=mode,
                    elapsed_ms=_elapsed_ms(started_at),
                )
            )
            return self._to_edit_response(edit_row=created, edited_result=None, edited_task=None)

    async def list_edits(self, *, current_user: User, result_id: str) -> ImageEditListResponse:
        """Return edit history for a source result owned by current user."""

        source_result_uuid = self._parse_uuid(result_id, field_name="result_id")
        async with self.session_factory() as session:
            task_repo = TaskDbRepository(session)
            result_repo = TaskResultRepository(session)
            edit_repo = ImageEditRepository(session)
            source_result = await result_repo.get_by_id_for_user(source_result_uuid, user_id=current_user.id)
            if source_result is None:
                raise AppException(f"结果 {result_id} 不存在", code=4045, status_code=404)

            edit_rows = await edit_repo.list_by_source_result_for_user(source_result_uuid, user_id=current_user.id)
            responses: list[ImageEditResponse] = []
            for edit_row in edit_rows:
                edited_result = None
                edited_task = None
                if edit_row.edited_result_id is not None:
                    edited_result = await result_repo.get_by_id_for_user(edit_row.edited_result_id, user_id=current_user.id)
                    if edited_result is not None:
                        edited_task = await task_repo.get_by_id_for_user(edited_result.task_id, user_id=current_user.id)
                responses.append(
                    self._to_edit_response(edit_row=edit_row, edited_result=edited_result, edited_task=edited_task)
                )

        return ImageEditListResponse(source_result_id=source_result_uuid.hex, items=responses)

    def run_edit_task_sync(self, edit_task_id: str) -> None:
        """Synchronous wrapper used by Celery and local fallback execution."""

        started_at = perf_counter()
        logger.info(format_log_event("image_edit_started", task_id=edit_task_id, mode="execute"))
        try:
            prepared = asyncio.run(self._prepare_execution(edit_task_id=edit_task_id))
            generated = self._generate_image(prepared)
            asyncio.run(self._complete_execution(prepared=prepared, generated=generated))
            logger.info(
                format_log_event(
                    "image_edit_succeeded",
                    task_id=edit_task_id,
                    user_id=prepared.user_id.hex,
                    result_id=prepared.source_result_id.hex,
                    provider=generated.provider_name,
                    mode=prepared.mode,
                    elapsed_ms=_elapsed_ms(started_at),
                )
            )
        except Exception as exc:
            logger.exception(format_log_event("image_edit_failed", task_id=edit_task_id, mode="execute", elapsed_ms=_elapsed_ms(started_at)))
            try:
                asyncio.run(self._mark_failed(edit_task_id=edit_task_id, exc=exc))
            except Exception:
                logger.exception("Failed to persist image edit failure edit_task_id=%s", edit_task_id)
            raise

    async def _prepare_execution(self, *, edit_task_id: str) -> PreparedImageEdit:
        task_uuid = self._parse_uuid(edit_task_id, field_name="edit_task_id")
        now = self._utcnow()
        async with self.session_factory() as session:
            task_repo = TaskDbRepository(session)
            result_repo = TaskResultRepository(session)
            edit_repo = ImageEditRepository(session)
            event_repo = TaskEventRepository(session)

            edit_task = await task_repo.get_by_id(task_uuid)
            if edit_task is None or edit_task.task_type != TaskType.IMAGE_EDIT.value:
                raise AppException(f"图片编辑任务 {edit_task_id} 不存在", code=4044, status_code=404)
            edit_row = await edit_repo.get_by_task_id(task_uuid)
            if edit_row is None:
                raise AppException(f"图片编辑记录 {edit_task_id} 不存在", code=4044, status_code=404)
            source_result = await result_repo.get_by_id_for_user(edit_row.source_result_id, user_id=edit_row.user_id)
            if source_result is None:
                raise AppException("源结果不存在或无权访问", code=4045, status_code=404)
            source_task = await task_repo.get_by_id_for_user(source_result.task_id, user_id=edit_row.user_id)
            if source_task is None:
                raise AppException("源任务不存在或无权访问", code=4044, status_code=404)

            source_path = self._resolve_source_image_path(source_task=source_task, source_result=source_result)
            edit_task.status = TaskStatus.RUNNING.value
            edit_task.current_step = "image_edit_generate"
            edit_task.progress_percent = Decimal("20")
            edit_task.started_at = edit_task.started_at or now
            edit_task.runtime_snapshot = {
                **(edit_task.runtime_snapshot or {}),
                "status": TaskStatus.RUNNING.value,
                "current_step": "image_edit_generate",
                "progress_percent": 20,
            }
            edit_row.status = ImageEditStatus.RUNNING.value
            edit_row.started_at = edit_row.started_at or now
            await task_repo.upsert(edit_task)
            await edit_repo.upsert(edit_row)
            event_repo.add(
                self._build_event_row(
                    task_id=edit_task.id,
                    user_id=edit_task.user_id,
                    event_type=TaskEventType.TASK_RUNNING.value,
                    level=TaskEventLevel.INFO.value,
                    step="image_edit_generate",
                    message="图片编辑任务开始生成",
                    payload={"mode": edit_row.mode},
                )
            )
            await session.commit()

            return PreparedImageEdit(
                edit_id=edit_row.id,
                edit_task_id=edit_task.id,
                user_id=edit_task.user_id,
                source_task_id=source_task.id,
                source_result_id=source_result.id,
                source_result_type=source_result.result_type,
                source_result_cos_key=source_result.cos_key,
                source_width=source_result.width,
                source_height=source_result.height,
                source_path=source_path,
                selection_type=edit_row.selection_type,
                selection=edit_row.selection,
                instruction=edit_row.instruction,
                mode=edit_row.mode,
                title=edit_task.title,
                platform=edit_task.platform,
            )

    def _generate_image(self, prepared: PreparedImageEdit) -> GeneratedEditResult:
        task_id = prepared.edit_task_id.hex
        dirs = ensure_task_dirs(task_id)
        input_dir = dirs["inputs"]
        generated_dir = dirs["generated"]
        final_dir = dirs["final"]
        source_copy = input_dir / f"source{prepared.source_path.suffix.lower() or '.png'}"
        if prepared.source_path.resolve() != source_copy.resolve():
            shutil.copy2(prepared.source_path, source_copy)

        request_payload = {
            "edit_id": prepared.edit_id.hex,
            "source_result_id": prepared.source_result_id.hex,
            "selection_type": prepared.selection_type,
            "selection": prepared.selection,
            "instruction": prepared.instruction,
            "mode": prepared.mode,
        }
        (input_dir / "edit_request.json").write_text(json.dumps(request_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        engine_settings = get_engine_settings()
        bindings = build_capability_bindings(engine_settings)
        plan = self._build_prompt_plan(prepared=prepared, image_size=engine_settings.default_image_size)
        (dirs["task"] / "image_edit_prompt_plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")

        source_asset = Asset(
            asset_id=prepared.source_result_id.hex,
            filename=source_copy.name,
            local_path=str(source_copy),
            mime_type=self._guess_mime_type(source_copy),
            asset_type=AssetType.PRODUCT,
            width=prepared.source_width,
            height=prepared.source_height,
        )
        provider_started_at = perf_counter()
        logger.info(
            format_log_event(
                "provider_image_request_started",
                task_id=task_id,
                user_id=prepared.user_id.hex,
                provider=bindings.image_provider_name,
                model=bindings.image_model_selection.model_id,
                mode=prepared.mode,
                reference_count=1,
            )
        )
        try:
            generation = bindings.image_generation_provider.generate_images(
                plan,
                output_dir=generated_dir,
                reference_assets=[source_asset],
            )
        except Exception:
            logger.exception(
                format_log_event(
                    "provider_image_request_failed",
                    task_id=task_id,
                    user_id=prepared.user_id.hex,
                    provider=bindings.image_provider_name,
                    model=bindings.image_model_selection.model_id,
                    mode=prepared.mode,
                    elapsed_ms=_elapsed_ms(provider_started_at),
                )
            )
            raise
        logger.info(
            format_log_event(
                "provider_image_request_succeeded",
                task_id=task_id,
                user_id=prepared.user_id.hex,
                provider=bindings.image_provider_name,
                model=bindings.image_model_selection.model_id,
                mode=prepared.mode,
                image_count=len(generation.images),
                elapsed_ms=_elapsed_ms(provider_started_at),
            )
        )
        if not generation.images:
            raise RuntimeError("image provider did not return any generated image")

        generated_image = generation.images[0]
        generated_path = Path(generated_image.image_path)
        final_path = final_dir / "edited_result.png"
        if generated_path.resolve() != final_path.resolve():
            shutil.copy2(generated_path, final_path)
        width, height = self._read_image_size(final_path, generated_image.width, generated_image.height)
        return GeneratedEditResult(
            output_path=final_path,
            relative_path=final_path.relative_to(dirs["task"]).as_posix(),
            width=width,
            height=height,
            provider_name=bindings.image_provider_name,
            model_name=bindings.image_model_selection.model_id,
            prompt_plan=plan.model_dump(mode="json"),
            prompt_final={
                "instruction": prepared.instruction,
                "mode": prepared.mode,
                "selection_type": prepared.selection_type,
                "selection": prepared.selection,
            },
            usage=generation.usage.model_dump(mode="json") if generation.usage is not None else None,
        )

    async def _complete_execution(self, *, prepared: PreparedImageEdit, generated: GeneratedEditResult) -> None:
        now = self._utcnow()
        async with self.session_factory() as session:
            task_repo = TaskDbRepository(session)
            result_repo = TaskResultRepository(session)
            edit_repo = ImageEditRepository(session)
            event_repo = TaskEventRepository(session)

            edit_task = await task_repo.get_by_id(prepared.edit_task_id)
            edit_row = await edit_repo.get_by_id(prepared.edit_id)
            if edit_task is None or edit_row is None:
                raise AppException("图片编辑任务不存在", code=4044, status_code=404)

            version_no = await result_repo.next_version_no_for_source(prepared.source_result_id)
            result_id = uuid.uuid4()
            mime_type = self._guess_mime_type(generated.output_path)
            cos_key = self._sync_file_to_cos_if_enabled(
                local_path=generated.output_path,
                user_id=prepared.user_id,
                task_id=prepared.edit_task_id,
                file_name=generated.relative_path,
                mime_type=mime_type,
                fallback_key=generated.relative_path,
            )
            result_row = TaskResult(
                id=result_id,
                task_id=prepared.edit_task_id,
                user_id=prepared.user_id,
                result_type=TaskType.IMAGE_EDIT.value,
                version_no=version_no,
                parent_result_id=prepared.source_result_id,
                status=TaskResultStatus.SUCCEEDED.value,
                cos_key=cos_key,
                mime_type=mime_type,
                size_bytes=generated.output_path.stat().st_size,
                sha256=self._sha256(generated.output_path),
                width=generated.width,
                height=generated.height,
                prompt_plan=generated.prompt_plan,
                prompt_final=generated.prompt_final,
                render_meta={
                    "source": "cos" if self.cos_service.is_enabled() else "local_file",
                    "local_relative_path": generated.relative_path,
                    "mode": prepared.mode,
                    "image_edit_id": prepared.edit_id.hex,
                    "source_result_id": prepared.source_result_id.hex,
                    "source_task_id": prepared.source_task_id.hex,
                    "provider_name": generated.provider_name,
                    "model_name": generated.model_name,
                    "selection_type": prepared.selection_type,
                    "selection": prepared.selection,
                    "usage": generated.usage,
                },
                is_primary=True,
            )
            result_repo.add(result_row)

            edit_task.status = TaskStatus.SUCCEEDED.value
            edit_task.current_step = "completed"
            edit_task.progress_percent = Decimal("100")
            edit_task.finished_at = now
            edit_task.runtime_snapshot = {
                **(edit_task.runtime_snapshot or {}),
                "status": TaskStatus.SUCCEEDED.value,
                "current_step": "completed",
                "progress_percent": 100,
                "source_result_id": prepared.source_result_id.hex,
                "edited_result_id": result_id.hex,
                "mode": prepared.mode,
                "provider_name": generated.provider_name,
                "model_name": generated.model_name,
            }
            edit_task.result_summary = {
                "result_count": 1,
                "primary_result_id": result_id.hex,
                "primary_cos_key": cos_key,
                "parent_result_id": prepared.source_result_id.hex,
                "version_no": version_no,
            }
            edit_row.status = ImageEditStatus.SUCCEEDED.value
            edit_row.edited_result_id = result_id
            edit_row.finished_at = now
            edit_row.error_message = None
            edit_row.metadata_json = {
                **(edit_row.metadata_json or {}),
                "provider_name": generated.provider_name,
                "model_name": generated.model_name,
                "result_cos_key": cos_key,
                "version_no": version_no,
            }
            await task_repo.upsert(edit_task)
            await edit_repo.upsert(edit_row)
            event_repo.add(
                self._build_event_row(
                    task_id=prepared.edit_task_id,
                    user_id=prepared.user_id,
                    event_type=TaskEventType.TASK_RESULTS_SYNCED.value,
                    level=TaskEventLevel.INFO.value,
                    step="completed",
                    message="图片编辑结果已写入数据库",
                    payload={"result_id": result_id.hex, "version_no": version_no},
                )
            )
            event_repo.add(
                self._build_event_row(
                    task_id=prepared.edit_task_id,
                    user_id=prepared.user_id,
                    event_type=TaskEventType.TASK_SUCCEEDED.value,
                    level=TaskEventLevel.INFO.value,
                    step="completed",
                    message="图片编辑任务执行完成",
                    payload={"result_id": result_id.hex, "mode": prepared.mode},
                )
            )
            await session.commit()

    async def _mark_failed(self, *, edit_task_id: str, exc: Exception) -> None:
        task_uuid = self._parse_uuid(edit_task_id, field_name="edit_task_id")
        now = self._utcnow()
        async with self.session_factory() as session:
            task_repo = TaskDbRepository(session)
            edit_repo = ImageEditRepository(session)
            event_repo = TaskEventRepository(session)
            edit_task = await task_repo.get_by_id(task_uuid)
            edit_row = await edit_repo.get_by_task_id(task_uuid)
            if edit_task is None:
                return
            edit_task.status = TaskStatus.FAILED.value
            edit_task.current_step = edit_task.current_step or "image_edit_generate"
            edit_task.error_message = str(exc)
            edit_task.finished_at = now
            edit_task.runtime_snapshot = {
                **(edit_task.runtime_snapshot or {}),
                "status": TaskStatus.FAILED.value,
                "error_message": str(exc),
            }
            await task_repo.upsert(edit_task)
            if edit_row is not None:
                edit_row.status = ImageEditStatus.FAILED.value
                edit_row.error_message = str(exc)
                edit_row.finished_at = now
                await edit_repo.upsert(edit_row)
            event_repo.add(
                self._build_event_row(
                    task_id=edit_task.id,
                    user_id=edit_task.user_id,
                    event_type=TaskEventType.TASK_FAILED.value,
                    level=TaskEventLevel.ERROR.value,
                    step=edit_task.current_step,
                    message="图片编辑任务执行失败",
                    payload={"error_message": str(exc)},
                )
            )
            await session.commit()

    def _build_prompt_plan(self, *, prepared: PreparedImageEdit, image_size: str) -> ImagePromptPlan:
        selection_text = self._format_selection(prepared.selection)
        prompt = (
            "Use the source image as a strict visual reference. "
            "Apply the user's edit instruction only to the selected region. "
            "Preserve product identity, composition, brand colors, and all unselected areas. "
            f"Selected region: {selection_text}. "
            f"Instruction: {prepared.instruction}"
        )
        return ImagePromptPlan(
            generation_mode="image_edit",
            prompts=[
                ImagePrompt(
                    shot_id="edit_01",
                    shot_type="image_edit",
                    prompt=prompt,
                    generation_mode="image_edit",
                    edit_instruction=prompt,
                    output_size=image_size,
                    preserve_rules=[
                        "Preserve the source product identity and main composition.",
                        "Do not alter unselected areas except for natural lighting continuity.",
                    ],
                    keep_subject_rules=["Keep the original product as the subject."],
                    editable_regions=[selection_text],
                    locked_regions=["All regions outside the user selection."],
                    composition_notes=["Return a single finished e-commerce image, not a collage."],
                    style_notes=["Match the source image style and lighting."],
                )
            ],
        )

    def _dispatch_task(self, edit_task_id: str) -> None:
        backend = "celery" if self.settings.celery_enabled else "local_thread_fallback"
        logger.info(format_log_event("task_dispatch_started", task_id=edit_task_id, task_type=TaskType.IMAGE_EDIT.value, mode=backend))
        if self.settings.celery_enabled:
            from backend.workers.tasks.image_edit_tasks import run_image_edit_task

            run_image_edit_task.delay(edit_task_id)
            logger.info(format_log_event("task_dispatch_succeeded", task_id=edit_task_id, task_type=TaskType.IMAGE_EDIT.value, mode=backend))
            return

        worker = Thread(
            target=lambda: ImageEditService().run_edit_task_sync(edit_task_id),
            name=f"image-edit-task-{edit_task_id}",
            daemon=True,
        )
        worker.start()
        logger.info(format_log_event("task_dispatch_succeeded", task_id=edit_task_id, task_type=TaskType.IMAGE_EDIT.value, mode=backend))

    def _resolve_execution_backend(self) -> str:
        if self.settings.celery_enabled:
            return "celery"
        return "local_thread_fallback"

    def _resolve_source_image_path(self, *, source_task: DbTask, source_result: TaskResult) -> Path:
        local_key = str((source_result.render_meta or {}).get("local_relative_path") or "")
        if not local_key and not source_result.cos_key.startswith("users/"):
            local_key = source_result.cos_key
        if not local_key:
            raise AppException("源图仅存在于 COS，当前编辑 worker 暂缺 COS 拉取能力", code=5033, status_code=503)

        task_dir = get_task_dir(source_task.id.hex).resolve()
        target = (task_dir / local_key).resolve()
        try:
            target.relative_to(task_dir)
        except ValueError as exc:
            raise AppException("源图路径非法", code=4006, status_code=400) from exc
        if not target.exists() or not target.is_file():
            raise AppException(f"源图文件不存在: {local_key}", code=4045, status_code=404)
        return target

    def _build_initial_events(
        self,
        *,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        source_result_id: str,
        mode: str,
        execution_backend: str,
    ) -> list[TaskEvent]:
        return [
            self._build_event_row(
                task_id=task_id,
                user_id=user_id,
                event_type=TaskEventType.TASK_CREATED.value,
                level=TaskEventLevel.INFO.value,
                step="queued",
                message="图片编辑任务已创建",
                payload={"source_result_id": source_result_id, "mode": mode},
            ),
            self._build_event_row(
                task_id=task_id,
                user_id=user_id,
                event_type=TaskEventType.TASK_QUEUED.value,
                level=TaskEventLevel.INFO.value,
                step="queued",
                message="图片编辑任务已进入执行队列",
                payload={"execution_backend": execution_backend},
            ),
        ]

    def _to_edit_response(
        self,
        *,
        edit_row: ImageEdit,
        edited_result: TaskResult | None,
        edited_task: DbTask | None,
    ) -> ImageEditResponse:
        return ImageEditResponse(
            edit_id=edit_row.id.hex,
            source_result_id=edit_row.source_result_id.hex,
            edit_task_id=edit_row.edit_task_id.hex,
            edited_result_id=edit_row.edited_result_id.hex if edit_row.edited_result_id is not None else None,
            selection_type=edit_row.selection_type,
            selection=edit_row.selection,
            instruction=edit_row.instruction,
            mode=edit_row.mode,
            status=edit_row.status,
            error_message=edit_row.error_message,
            metadata=edit_row.metadata_json,
            edited_result=self._to_result_response(task_row=edited_task, result_row=edited_result)
            if edited_task is not None and edited_result is not None
            else None,
            created_at=edit_row.created_at,
            updated_at=edit_row.updated_at,
            started_at=edit_row.started_at,
            finished_at=edit_row.finished_at,
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
        local_key = str((result_row.render_meta or {}).get("local_relative_path") or result_row.cos_key)
        safe_key = quote(local_key.replace("\\", "/"), safe="/")
        if task_row.task_type == TaskType.DETAIL_PAGE.value:
            return f"/api/detail/jobs/{task_row.id.hex}/files/{safe_key}"
        return f"/api/tasks/{task_row.id.hex}/files/{safe_key}"

    def _build_event_row(
        self,
        *,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        event_type: str,
        level: str,
        step: str | None,
        message: str,
        payload: dict[str, object] | None,
    ) -> TaskEvent:
        return TaskEvent(
            id=uuid.uuid4(),
            task_id=task_id,
            user_id=user_id,
            event_type=event_type,
            level=level,
            step=step,
            message=message,
            payload=payload,
        )

    def _sync_file_to_cos_if_enabled(
        self,
        *,
        local_path: Path,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        file_name: str,
        mime_type: str,
        fallback_key: str,
    ) -> str:
        if not self.cos_service.is_enabled():
            return fallback_key
        cos_key = self.cos_service.build_task_object_key(
            user_id=user_id,
            task_id=task_id,
            kind="results",
            file_name=file_name,
        )
        self.cos_service.upload_file(local_path=local_path, key=cos_key, mime_type=mime_type)
        return cos_key

    def _format_selection(self, selection: dict[str, object]) -> str:
        x = float(selection.get("x", 0))
        y = float(selection.get("y", 0))
        width = float(selection.get("width", 0))
        height = float(selection.get("height", 0))
        return f"rectangle ratio x={x:.4f}, y={y:.4f}, width={width:.4f}, height={height:.4f}"

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

    def _guess_mime_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _parse_uuid(self, value: str, *, field_name: str) -> uuid.UUID:
        try:
            return uuid.UUID(value)
        except ValueError as exc:
            raise AppException(f"{field_name} 非法: {value}", code=4007, status_code=400) from exc

    def _utcnow(self) -> datetime:
        return datetime.now(timezone.utc)


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)
