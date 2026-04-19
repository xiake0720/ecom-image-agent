"""主图生成服务。

职责：把 API 输入转换成可后台执行的 workflow 任务，并把运行中状态持续写回本地索引。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from backend.db.enums import TaskType
from backend.db.models.user import User
from backend.engine.core.config import get_settings
from backend.engine.core.paths import ensure_task_dirs
from backend.engine.domain.asset import Asset, AssetType
from backend.engine.domain.task import Task, TaskStatus
from backend.engine.services.storage.local_storage import LocalStorageService
from backend.engine.workflows.graph import run_workflow
from backend.engine.workflows.state import WorkflowExecutionError, WorkflowState, format_workflow_log
from backend.repositories.task_repository import TaskRepository
from backend.schemas.task import MainImageGeneratePayload, TaskSummary
from backend.services.task_db_mirror_service import TaskDbMirrorService

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
        self.db_mirror = TaskDbMirrorService()

    async def prepare_generation(
        self,
        *,
        payload: MainImageGeneratePayload,
        white_bg: UploadFile,
        detail_files: list[UploadFile],
        bg_files: list[UploadFile],
        current_user: User | None,
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
        self.storage.save_json_artifact(task_id, "inputs/asset_manifest.json", assets)
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
        await self.db_mirror.create_task_record(
            task_id=task_id,
            current_user=current_user,
            task_type=TaskType.MAIN_IMAGE,
            title=payload.product_name,
            platform=payload.platform,
            input_summary={
                "white_bg_count": 1,
                "detail_image_count": len(detail_files),
                "background_image_count": len(bg_files),
            },
            params=payload.model_dump(mode="json"),
            assets=self.db_mirror.build_main_image_asset_inputs(assets),
            created_at=task.created_at,
        )
        return PreparedMainImageTask(summary=summary, initial_state=initial_state)

    def load_prepared_task(self, task_id: str) -> PreparedMainImageTask:
        """从已落盘任务目录重建 Celery worker 可执行状态。"""

        task_dirs = ensure_task_dirs(task_id)
        task_path = task_dirs["task"] / "task.json"
        if not task_path.exists():
            raise FileNotFoundError(f"主图任务 manifest 不存在: {task_id}")
        task = Task.model_validate_json(task_path.read_text(encoding="utf-8"))
        asset_manifest_path = task_dirs["inputs"] / "asset_manifest.json"
        if asset_manifest_path.exists():
            assets = [Asset.model_validate(item) for item in self._load_json_list(asset_manifest_path)]
        else:
            assets = self._scan_input_assets(task_id)
        settings = get_settings()
        summary = self.repo.get_task(task_id) or self.repo.create_task_summary(
            task_id=task_id,
            task_type="main_image",
            status=task.status.value,
            title=task.product_name,
            platform=task.platform,
            result_path=str(task_dirs["final"]),
            created_at=task.created_at,
            provider_label=settings.resolve_image_provider_route().label,
            model_label=settings.resolve_image_model_selection().label,
        )
        initial_state: WorkflowState = {
            "task": task,
            "assets": assets,
            "logs": [
                format_workflow_log(
                    task_id=task_id,
                    node_name="celery_worker",
                    event="loaded",
                    detail="Celery worker 已从任务目录恢复主图任务",
                )
            ],
            "cache_enabled": bool(settings.enable_node_cache),
            "ignore_cache": False,
        }
        return PreparedMainImageTask(summary=summary, initial_state=initial_state)

    def run_prepared_task(self, prepared: PreparedMainImageTask, *, raise_on_error: bool = False) -> None:
        """在后台线程执行已准备好的主图任务。"""

        initial_state = prepared.initial_state
        task = initial_state["task"]

        def persist_progress(progress_state: WorkflowState) -> None:
            """把 workflow 最新任务态回写到索引，供前端轮询读取。"""

            progress_task = progress_state.get("task")
            if progress_task is not None:
                self.repo.save_runtime_task(progress_task)
                self.db_mirror.sync_runtime_from_local_sync(task_id=progress_task.task_id, task_type=TaskType.MAIN_IMAGE)

        try:
            result = run_workflow(initial_state, on_progress=persist_progress)
            result_task = result["task"]
            self.repo.save_runtime_task(result_task)
            self.db_mirror.sync_runtime_from_local_sync(task_id=result_task.task_id, task_type=TaskType.MAIN_IMAGE)
            logger.info("主图任务完成 task_id=%s status=%s", task.task_id, result_task.status.value)
        except WorkflowExecutionError as exc:
            failed_state = exc.task_state or {}
            failed_task = failed_state.get("task") if isinstance(failed_state, dict) else None
            if failed_task is not None:
                self.repo.save_runtime_task(failed_task)
                self.db_mirror.sync_runtime_from_local_sync(task_id=failed_task.task_id, task_type=TaskType.MAIN_IMAGE)
            logger.exception("主图任务失败 task_id=%s node=%s", task.task_id, exc.node_name)
            if raise_on_error:
                raise
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
            self.db_mirror.sync_runtime_from_local_sync(task_id=failed_task.task_id, task_type=TaskType.MAIN_IMAGE)
            if raise_on_error:
                raise

    def build_result_dir(self, task_id: str) -> Path:
        """返回任务最终图片目录。"""

        return ensure_task_dirs(task_id)["final"]

    def _load_json_list(self, path: Path) -> list[dict[str, object]]:
        """读取 Pydantic 列表产物。"""

        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []

    def _scan_input_assets(self, task_id: str) -> list[Asset]:
        """兼容历史任务：没有 asset_manifest 时从 inputs 目录推导素材。"""

        inputs_dir = ensure_task_dirs(task_id)["inputs"]
        image_paths = sorted(
            [path for path in inputs_dir.iterdir() if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}],
            key=lambda item: item.name,
        )
        assets: list[Asset] = []
        for index, path in enumerate(image_paths, start=1):
            asset_type = AssetType.WHITE_BG if index == 1 else AssetType.DETAIL
            assets.append(
                Asset(
                    asset_id=f"asset-{index:02d}",
                    filename=path.name,
                    local_path=str(path),
                    mime_type=self._guess_mime_type(path),
                    asset_type=asset_type,
                )
            )
        return assets

    def _guess_mime_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"
