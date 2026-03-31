"""任务查询路由。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.core.exceptions import AppException
from backend.core.response import success_response
from backend.repositories.task_repository import TaskRepository

router = APIRouter(prefix="/tasks", tags=["tasks"])
repo = TaskRepository()


@router.get("")
def list_tasks(request: Request) -> dict[str, object]:
    """返回任务列表。"""

    return success_response([x.model_dump(mode="json") for x in repo.list_tasks()], request.state.request_id)


@router.get("/{task_id}")
def get_task(task_id: str, request: Request) -> dict[str, object]:
    """返回单任务详情。"""

    task = repo.get_task(task_id)
    if task is None:
        raise AppException(f"任务 {task_id} 不存在", code=4044)
    return success_response(task.model_dump(mode="json"), request.state.request_id)
