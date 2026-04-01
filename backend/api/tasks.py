"""任务查询路由。"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from backend.core.exceptions import AppException
from backend.core.response import success_response
from backend.repositories.task_repository import TaskRepository
from backend.services.task_runtime_service import TaskRuntimeService

router = APIRouter(prefix="/tasks", tags=["tasks"])
repo = TaskRepository()
runtime_service = TaskRuntimeService()


@router.get("")
def list_tasks(request: Request) -> dict[str, object]:
    """返回任务列表。"""

    return success_response([item.model_dump(mode="json") for item in repo.list_tasks()], request.state.request_id)


@router.get("/{task_id}")
def get_task(task_id: str, request: Request) -> dict[str, object]:
    """返回单任务摘要。"""

    task = repo.get_task(task_id)
    if task is None:
        raise AppException(f"任务 {task_id} 不存在", code=4044)
    return success_response(task.model_dump(mode="json"), request.state.request_id)


@router.get("/{task_id}/runtime")
def get_task_runtime(task_id: str, request: Request) -> dict[str, object]:
    """返回适合主图工作台轮询的运行时数据。"""

    runtime = runtime_service.get_runtime(task_id)
    return success_response(runtime.model_dump(mode="json"), request.state.request_id)


@router.get("/{task_id}/files/{file_name:path}")
def get_task_file(task_id: str, file_name: str) -> FileResponse:
    """访问任务输出目录下的真实文件。"""

    target = runtime_service.resolve_task_file(task_id, file_name)
    return FileResponse(target)
