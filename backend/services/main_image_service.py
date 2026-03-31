"""主图生成服务。

职责：把 API 输入转换为既有 workflow 可消费的状态，保证旧能力复用且接口稳定。
"""

from __future__ import annotations

import logging
from fastapi import UploadFile

from backend.repositories.task_repository import TaskRepository
from backend.schemas.task import MainImageGeneratePayload, TaskSummary
from src.core.config import get_settings
from src.core.paths import ensure_task_dirs
from src.domain.asset import AssetType
from src.domain.task import Task, TaskStatus
from src.services.storage.local_storage import LocalStorageService
from src.workflows.graph import run_workflow
from src.workflows.state import WorkflowState, format_workflow_log

logger = logging.getLogger(__name__)


class MainImageService:
    """封装主图任务执行。

    设计原因：
    - 将同步 workflow 调用封装在 service 层，路由层只做参数编排；
    - 未来改异步队列时，可只替换此类实现。
    """

    def __init__(self) -> None:
        self.storage = LocalStorageService()
        self.repo = TaskRepository()

    async def generate(
        self,
        *,
        payload: MainImageGeneratePayload,
        white_bg: UploadFile,
        detail_files: list[UploadFile],
        bg_files: list[UploadFile],
    ) -> TaskSummary:
        """执行主图生成。

        输入：结构化文本参数 + 上传素材文件。
        输出：任务摘要，包含结果目录路径。
        """

        settings = get_settings()
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
            status=TaskStatus.RUNNING,
            task_dir=str(task_dirs["task"]),
            style_type=payload.style_type,
            style_notes=payload.style_notes,
        )
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
                    event="start",
                    detail="API 请求进入主图生成流程",
                )
            ],
            "cache_enabled": bool(settings.enable_node_cache),
            "ignore_cache": False,
        }
        result = run_workflow(initial_state)
        result_task = result["task"]
        summary = self.repo.create_task_summary(
            task_id=task_id,
            task_type="main_image",
            status=result_task.status.value,
            title=payload.product_name,
            platform=payload.platform,
            result_path=str(task_dirs["final"]),
        )
        self.repo.save_task(summary)
        logger.info("主图任务完成 task_id=%s status=%s", task_id, result_task.status.value)
        return summary
