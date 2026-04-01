"""主图生成服务。

职责：把 API 输入转换成可后台执行的 workflow 任务，并把运行中状态持续写回本地索引。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from backend.engine.core.config import get_settings
from backend.engine.core.paths import ensure_task_dirs
from backend.engine.domain.asset import AssetType
from backend.engine.domain.task import Task, TaskStatus
from backend.engine.services.storage.local_storage import LocalStorageService
from backend.engine.workflows.graph import run_workflow
from backend.engine.workflows.state import WorkflowExecutionError, WorkflowState, format_workflow_log
from backend.repositories.task_repository import TaskRepository
from backend.schemas.task import MainImageGeneratePayload, TaskSummary

logger = logging.getLogger(__name__)


@dataclass
class PreparedMainImageTask:
    """已完成落盘、可直接进入后台执行的主图任务。"""

    summary: TaskSummary
    initial_state: WorkflowState


class MainImageService:
    """封装主图任务创建与后台执行。"""

    def __init__(self) -> None:
        self.storage = LocalStorageService()
        self.repo = TaskRepository()

    async def prepare_generation(
        self,
        *,
        payload: MainImageGeneratePayload,
        white_bg: UploadFile,
        detail_files: list[UploadFile],
        bg_files: list[UploadFile],
    ) -> PreparedMainImageTask:
        """创建任务并把上传文件先落盘。

        这样路由可以先返回 task_id，后台线程再读取已落盘素材执行 workflow。
        """

        settings = get_settings()
        provider_label = settings.resolve_image_provider_route().label
        model_label = settings.resolve_image_model_selection().label
        task_id = self.storage.create_task_id()
        task_dirs = ensure_task_dirs(task_id)
        task = Task(
            task_id=task_id,
            brand_name=payload.brand_name,
            product_name=payload.product_name,
            category=payload.category,
            platform=payload.platform,
            shot_count=payload.shot_count,
            aspect_ratio=payload.aspect_ratio,
            image_size=payload.image_size,
            status=TaskStatus.CREATED,
            task_dir=str(task_dirs["task"]),
            current_step="queued",
            current_step_label="任务已提交，等待开始",
            progress_percent=0,
            style_type=payload.style_type,
            style_notes=payload.style_notes,
        )
        self.storage.save_task_manifest(task)

        uploads_payload = [(white_bg.filename or "white_bg.png", await white_bg.read(), AssetType.WHITE_BG)]
        for file in detail_files:
            uploads_payload.append((file.filename or "detail.png", await file.read(), AssetType.DETAIL))
        for file in bg_files:
            uploads_payload.append((file.filename or "style.png", await file.read(), AssetType.BACKGROUND_STYLE))

        assets = self.storage.save_uploads(task_id, uploads_payload)
        initial_state: WorkflowState = {
            "task": task,
            "assets": assets,
            "logs": [
                format_workflow_log(
                    task_id=task_id,
                    node_name="fastapi_entry",
                    event="queued",
                    detail="API 请求已创建主图任务，等待后台执行",
                )
            ],
            "cache_enabled": bool(settings.enable_node_cache),
            "ignore_cache": False,
        }
        summary = self.repo.create_task_summary(
            task_id=task_id,
            task_type="main_image",
            status=task.status.value,
            title=payload.product_name,
            platform=payload.platform,
            result_path=str(task_dirs["final"]),
            created_at=task.created_at,
            provider_label=provider_label,
            model_label=model_label,
            detail_image_count=len(detail_files),
            background_image_count=len(bg_files),
        )
        self.repo.save_task(summary)
        return PreparedMainImageTask(summary=summary, initial_state=initial_state)

    def run_prepared_task(self, prepared: PreparedMainImageTask) -> None:
        """在后台线程执行已准备好的主图任务。"""

        initial_state = prepared.initial_state
        task = initial_state["task"]

        def persist_progress(progress_state: WorkflowState) -> None:
            """把 workflow 最新任务态回写到索引，供前端轮询读取。"""

            progress_task = progress_state.get("task")
            if progress_task is not None:
                self.repo.save_runtime_task(progress_task)

        try:
            result = run_workflow(initial_state, on_progress=persist_progress)
            result_task = result["task"]
            self.repo.save_runtime_task(result_task)
            logger.info("主图任务完成 task_id=%s status=%s", task.task_id, result_task.status.value)
        except WorkflowExecutionError as exc:
            failed_state = exc.task_state or {}
            failed_task = failed_state.get("task") if isinstance(failed_state, dict) else None
            if failed_task is not None:
                self.repo.save_runtime_task(failed_task)
            logger.exception("主图任务失败 task_id=%s node=%s", task.task_id, exc.node_name)
        except Exception as exc:  # pragma: no cover - 兜底逻辑
            logger.exception("主图任务出现未处理异常 task_id=%s", task.task_id)
            failed_task = task.model_copy(
                update={
                    "status": TaskStatus.FAILED,
                    "current_step": task.current_step or "fastapi_entry",
                    "current_step_label": "任务执行失败",
                    "progress_percent": task.progress_percent,
                    "error_message": f"任务执行异常：{exc}",
                }
            )
            self.storage.save_task_manifest(failed_task)
            self.repo.save_runtime_task(failed_task)

    def build_result_dir(self, task_id: str) -> Path:
        """返回任务最终图片目录。"""

        return ensure_task_dirs(task_id)["final"]
