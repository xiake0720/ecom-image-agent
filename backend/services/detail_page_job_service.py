"""详情图任务服务。"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from threading import Lock, Thread

from fastapi import UploadFile

from backend.engine.core.config import get_settings
from backend.engine.core.paths import ensure_task_dirs, get_task_dir
from backend.engine.domain.task import Task, TaskStatus
from backend.engine.services.storage.local_storage import LocalStorageService
from backend.engine.workflows.detail_graph import run_detail_workflow
from backend.engine.workflows.detail_state import (
    DetailWorkflowExecutionError,
    DetailWorkflowState,
    format_detail_workflow_log,
)
from backend.repositories.task_repository import TaskRepository
from backend.schemas.detail import DetailPageAssetRef, DetailPageJobCreatePayload, DetailPageJobCreateResult


@dataclass
class PreparedDetailTask:
    """已完成落盘、可直接进入后台执行的详情图任务。"""

    task_id: str
    summary_title: str
    initial_state: DetailWorkflowState
    plan_only: bool


class _DetailTaskQueue:
    """详情图单 worker 队列。"""

    def __init__(self) -> None:
        self._queue: Queue[tuple[PreparedDetailTask, object]] = Queue()
        self._pending: deque[str] = deque()
        self._active: str | None = None
        self._lock = Lock()
        self._worker: Thread | None = None

    def enqueue(self, item: PreparedDetailTask, executor) -> None:
        self._ensure_worker()
        with self._lock:
            self._pending.append(item.task_id)
        self._queue.put((item, executor))

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._worker = Thread(target=self._loop, name="detail-task-queue", daemon=True)
            self._worker.start()

    def _loop(self) -> None:
        while True:
            item, executor = self._queue.get()
            with self._lock:
                if item.task_id in self._pending:
                    self._pending.remove(item.task_id)
                self._active = item.task_id
            try:
                executor(item)
            finally:
                with self._lock:
                    if self._active == item.task_id:
                        self._active = None
                self._queue.task_done()


detail_task_queue = _DetailTaskQueue()


class DetailPageJobService:
    """负责创建详情图任务并触发 detail graph。"""

    def __init__(self) -> None:
        self.storage = LocalStorageService()
        self.repo = TaskRepository()

    async def create_job(
        self,
        *,
        payload: DetailPageJobCreatePayload,
        packaging_files: list[UploadFile],
        dry_leaf_files: list[UploadFile],
        tea_soup_files: list[UploadFile],
        leaf_bottom_files: list[UploadFile],
        scene_ref_files: list[UploadFile],
        bg_ref_files: list[UploadFile],
        plan_only: bool,
    ) -> DetailPageJobCreateResult:
        """创建详情图任务，并根据模式立即执行或入队。"""

        settings = get_settings()
        task_id = self.storage.create_task_id()
        task_dirs = ensure_task_dirs(task_id)
        self._ensure_detail_dirs(task_dirs["task"])
        task = Task(
            task_id=task_id,
            brand_name=payload.brand_name,
            product_name=payload.product_name or f"{payload.tea_type}详情图",
            category=payload.category,
            platform=payload.platform,
            shot_count=payload.target_slice_count,
            aspect_ratio="3:4",
            image_size=payload.image_size,
            status=TaskStatus.CREATED,
            task_dir=str(task_dirs["task"]),
            current_step="queued",
            current_step_label="详情图任务已提交",
            progress_percent=0,
            style_type=payload.style_preset,
            style_notes=payload.style_notes,
        )
        self.storage.save_task_manifest(task)

        assets = await self._persist_assets(
            task_id=task_id,
            payload=payload,
            packaging_files=packaging_files,
            dry_leaf_files=dry_leaf_files,
            tea_soup_files=tea_soup_files,
            leaf_bottom_files=leaf_bottom_files,
            scene_ref_files=scene_ref_files,
            bg_ref_files=bg_ref_files,
        )
        initial_state: DetailWorkflowState = {
            "task": task,
            "detail_payload": payload.model_copy(),
            "detail_assets": assets,
            "logs": [
                format_detail_workflow_log(
                    task_id=task_id,
                    node_name="fastapi_entry",
                    event="queued",
                    detail="API 请求已创建详情图任务，等待 detail graph 执行",
                )
            ],
            "error_message": "",
        }
        provider_label = settings.resolve_image_provider_route().label
        model_label = settings.resolve_image_model_selection().label
        summary = self.repo.create_task_summary(
            task_id=task_id,
            task_type="detail_page_v2",
            status=task.status.value,
            title=task.product_name,
            platform=payload.platform,
            result_path=str(get_task_dir(task_id) / "generated"),
            created_at=task.created_at,
            provider_label=provider_label,
            model_label=model_label,
        )
        self.repo.save_task(summary)

        prepared = PreparedDetailTask(
            task_id=task_id,
            summary_title=task.product_name,
            initial_state=initial_state,
            plan_only=plan_only,
        )
        if plan_only:
            self.run_prepared(prepared)
        else:
            detail_task_queue.enqueue(prepared, self.run_prepared)
        return DetailPageJobCreateResult(task_id=task_id, status="created")

    def run_prepared(self, prepared: PreparedDetailTask) -> None:
        """执行 detail graph，并持续把运行时状态写回索引。"""

        initial_state = prepared.initial_state
        task = initial_state["task"]

        def persist_progress(progress_state: DetailWorkflowState) -> None:
            progress_task = progress_state.get("task")
            if progress_task is not None:
                self.repo.save_runtime_task(progress_task, task_type="detail_page_v2")

        try:
            result = run_detail_workflow(
                initial_state,
                stop_after="detail_generate_prompt" if prepared.plan_only else None,
                on_progress=persist_progress,
            )
            result_task = result["task"]
            self.repo.save_runtime_task(result_task, task_type="detail_page_v2")
        except DetailWorkflowExecutionError as exc:
            failed_state = exc.task_state or {}
            failed_task = failed_state.get("task") if isinstance(failed_state, dict) else None
            if failed_task is not None:
                self.repo.save_runtime_task(failed_task, task_type="detail_page_v2")
        except Exception as exc:  # pragma: no cover - 兜底保护
            failed_task = task.model_copy(
                update={
                    "status": TaskStatus.FAILED,
                    "current_step": task.current_step or "fastapi_entry",
                    "current_step_label": "详情图任务执行失败",
                    "error_message": f"详情图任务执行异常：{exc}",
                }
            )
            self.storage.save_task_manifest(failed_task)
            self.repo.save_runtime_task(failed_task, task_type="detail_page_v2")

    async def _persist_assets(
        self,
        *,
        task_id: str,
        payload: DetailPageJobCreatePayload,
        packaging_files: list[UploadFile],
        dry_leaf_files: list[UploadFile],
        tea_soup_files: list[UploadFile],
        leaf_bottom_files: list[UploadFile],
        scene_ref_files: list[UploadFile],
        bg_ref_files: list[UploadFile],
    ) -> list[DetailPageAssetRef]:
        """写入素材文件，并记录角色与来源。"""

        asset_rows: list[DetailPageAssetRef] = []
        role_map = [
            ("packaging", packaging_files),
            ("dry_leaf", dry_leaf_files),
            ("tea_soup", tea_soup_files),
            ("leaf_bottom", leaf_bottom_files),
            ("scene_ref", scene_ref_files),
            ("bg_ref", bg_ref_files),
        ]
        counter = 1
        for role, files in role_map:
            for file in files:
                name = file.filename or f"{role}_{counter}.png"
                target = get_task_dir(task_id) / "inputs" / name
                target.write_bytes(await file.read())
                asset_rows.append(
                    DetailPageAssetRef(
                        asset_id=f"asset-{counter:03d}",
                        role=role,
                        file_name=name,
                        relative_path=f"inputs/{name}",
                    )
                )
                counter += 1
        if payload.main_image_task_id:
            for rel in payload.selected_main_result_ids:
                source = get_task_dir(payload.main_image_task_id) / rel
                if not source.exists():
                    continue
                name = f"main_{counter:03d}_{Path(rel).name}"
                target = get_task_dir(task_id) / "inputs" / name
                target.write_bytes(source.read_bytes())
                asset_rows.append(
                    DetailPageAssetRef(
                        asset_id=f"asset-{counter:03d}",
                        role="main_result",
                        file_name=name,
                        relative_path=f"inputs/{name}",
                        source_type="main_task",
                        source_task_id=payload.main_image_task_id,
                        source_result_file=rel,
                    )
                )
                counter += 1
        return asset_rows

    def _ensure_detail_dirs(self, task_dir: Path) -> None:
        for name in ["inputs", "plan", "generated", "review", "qc", "exports"]:
            (task_dir / name).mkdir(parents=True, exist_ok=True)
