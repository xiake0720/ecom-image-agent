"""API v1 任务查询路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from backend.api.dependencies import get_current_user
from backend.core.response import success_response
from backend.db.enums import TaskStatus, TaskType
from backend.db.models.user import User
from backend.services.task_query_service import TaskQueryService


router = APIRouter(prefix="/tasks", tags=["tasks-v1"])
service = TaskQueryService()


@router.get("")
async def list_tasks(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    task_type: TaskType | None = None,
    status: TaskStatus | None = None,
) -> dict[str, object]:
    """分页查询当前用户任务。"""

    data = await service.list_tasks(
        current_user=current_user,
        page=page,
        page_size=page_size,
        task_type=task_type,
        status=status,
    )
    return success_response(data.model_dump(mode="json"), request.state.request_id)


@router.get("/{task_id}")
async def get_task_detail(
    task_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    """返回当前用户可访问的任务详情。"""

    data = await service.get_task_detail(current_user=current_user, task_id=task_id)
    return success_response(data.model_dump(mode="json"), request.state.request_id)


@router.get("/{task_id}/runtime")
async def get_task_runtime(
    task_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    """返回当前用户任务的 runtime 聚合。"""

    data = await service.get_task_runtime(current_user=current_user, task_id=task_id)
    return success_response(data.model_dump(mode="json"), request.state.request_id)


@router.get("/{task_id}/results")
async def get_task_results(
    task_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    """返回当前用户任务的结果摘要。"""

    data = await service.get_task_results(current_user=current_user, task_id=task_id)
    return success_response(data.model_dump(mode="json"), request.state.request_id)
