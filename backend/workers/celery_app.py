"""Celery 应用配置入口。"""

from __future__ import annotations

from celery import Celery

from backend.core.config import get_settings


def create_celery_app() -> Celery:
    """创建 Celery app，并统一读取 FastAPI 配置。"""

    settings = get_settings()
    app = Celery(
        "ecom_image_agent",
        broker=settings.resolve_celery_broker_url(),
        backend=settings.resolve_celery_result_backend(),
        include=[
            "backend.workers.tasks.main_image_tasks",
            "backend.workers.tasks.detail_page_tasks",
            "backend.workers.tasks.image_edit_tasks",
        ],
    )
    app.conf.update(
        task_serializer=settings.celery_task_serializer,
        accept_content=settings.celery_accept_content,
        result_serializer=settings.celery_result_serializer,
        task_always_eager=settings.celery_task_always_eager,
        task_eager_propagates=True,
        task_track_started=True,
        task_time_limit=settings.celery_task_time_limit_seconds,
        task_soft_time_limit=settings.celery_task_soft_time_limit_seconds,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        broker_connection_retry_on_startup=True,
        timezone="UTC",
    )
    return app


celery_app = create_celery_app()
