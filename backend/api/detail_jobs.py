"""详情图真实任务路由。"""

from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse

from backend.core.exceptions import AppException
from backend.core.response import success_response
from backend.repositories.task_repository import TaskRepository
from backend.schemas.detail import DetailPageJobCreatePayload
from backend.services.detail_page_job_service import DetailPageJobService
from backend.services.detail_runtime_service import DetailRuntimeService

router = APIRouter(prefix="/detail/jobs", tags=["detail-jobs"])
service = DetailPageJobService()
repo = TaskRepository()
runtime_service = DetailRuntimeService()


@router.post("")
async def create_detail_job(
    request: Request,
    packaging_files: list[UploadFile] = File(default_factory=list),
    dry_leaf_files: list[UploadFile] = File(default_factory=list),
    tea_soup_files: list[UploadFile] = File(default_factory=list),
    leaf_bottom_files: list[UploadFile] = File(default_factory=list),
    scene_ref_files: list[UploadFile] = File(default_factory=list),
    bg_ref_files: list[UploadFile] = File(default_factory=list),
    brand_name: str = Form(default=""),
    product_name: str = Form(default=""),
    tea_type: str = Form(default="乌龙茶"),
    platform: str = Form(default="tmall"),
    style_preset: str = Form(default="tea_tmall_premium_light"),
    price_band: str = Form(default=""),
    target_slice_count: int = Form(default=8),
    image_size: str = Form(default="2K"),
    main_image_task_id: str = Form(default=""),
    selected_main_result_ids: str = Form(default="[]"),
    selling_points_json: str = Form(default="[]"),
    specs_json: str = Form(default="{}"),
    style_notes: str = Form(default=""),
    brew_suggestion: str = Form(default=""),
    extra_requirements: str = Form(default=""),
    prefer_main_result_first: bool = Form(default=True),
) -> dict[str, object]:
    """创建详情图任务并执行完整 graph。"""

    payload = _build_payload(
        brand_name=brand_name,
        product_name=product_name,
        tea_type=tea_type,
        platform=platform,
        style_preset=style_preset,
        price_band=price_band,
        target_slice_count=target_slice_count,
        image_size=image_size,
        main_image_task_id=main_image_task_id,
        selected_main_result_ids=selected_main_result_ids,
        selling_points_json=selling_points_json,
        specs_json=specs_json,
        style_notes=style_notes,
        brew_suggestion=brew_suggestion,
        extra_requirements=extra_requirements,
        prefer_main_result_first=prefer_main_result_first,
    )
    result = await service.create_job(
        payload=payload,
        packaging_files=packaging_files,
        dry_leaf_files=dry_leaf_files,
        tea_soup_files=tea_soup_files,
        leaf_bottom_files=leaf_bottom_files,
        scene_ref_files=scene_ref_files,
        bg_ref_files=bg_ref_files,
        plan_only=False,
    )
    return success_response(result.model_dump(mode="json"), request.state.request_id, message="详情图任务已提交")


@router.post("/plan")
async def create_detail_plan(
    request: Request,
    packaging_files: list[UploadFile] = File(default_factory=list),
    dry_leaf_files: list[UploadFile] = File(default_factory=list),
    tea_soup_files: list[UploadFile] = File(default_factory=list),
    leaf_bottom_files: list[UploadFile] = File(default_factory=list),
    scene_ref_files: list[UploadFile] = File(default_factory=list),
    bg_ref_files: list[UploadFile] = File(default_factory=list),
    brand_name: str = Form(default=""),
    product_name: str = Form(default=""),
    tea_type: str = Form(default="乌龙茶"),
    platform: str = Form(default="tmall"),
    style_preset: str = Form(default="tea_tmall_premium_light"),
    price_band: str = Form(default=""),
    target_slice_count: int = Form(default=8),
    image_size: str = Form(default="2K"),
    main_image_task_id: str = Form(default=""),
    selected_main_result_ids: str = Form(default="[]"),
    selling_points_json: str = Form(default="[]"),
    specs_json: str = Form(default="{}"),
    style_notes: str = Form(default=""),
    brew_suggestion: str = Form(default=""),
    extra_requirements: str = Form(default=""),
    prefer_main_result_first: bool = Form(default=True),
) -> dict[str, object]:
    """只生成规划、文案和 prompt，不执行渲染。"""

    payload = _build_payload(
        brand_name=brand_name,
        product_name=product_name,
        tea_type=tea_type,
        platform=platform,
        style_preset=style_preset,
        price_band=price_band,
        target_slice_count=target_slice_count,
        image_size=image_size,
        main_image_task_id=main_image_task_id,
        selected_main_result_ids=selected_main_result_ids,
        selling_points_json=selling_points_json,
        specs_json=specs_json,
        style_notes=style_notes,
        brew_suggestion=brew_suggestion,
        extra_requirements=extra_requirements,
        prefer_main_result_first=prefer_main_result_first,
    )
    result = await service.create_job(
        payload=payload,
        packaging_files=packaging_files,
        dry_leaf_files=dry_leaf_files,
        tea_soup_files=tea_soup_files,
        leaf_bottom_files=leaf_bottom_files,
        scene_ref_files=scene_ref_files,
        bg_ref_files=bg_ref_files,
        plan_only=True,
    )
    return success_response(result.model_dump(mode="json"), request.state.request_id, message="详情图规划任务已完成")


@router.get("/{task_id}")
def get_detail_job(task_id: str, request: Request) -> dict[str, object]:
    """返回详情图任务摘要。"""

    summary = repo.get_task(task_id)
    if summary is None or summary.task_type != "detail_page_v2":
        raise AppException(f"详情图任务 {task_id} 不存在", code=4044)
    return success_response(summary.model_dump(mode="json"), request.state.request_id)


@router.get("/{task_id}/runtime")
def get_detail_runtime(task_id: str, request: Request) -> dict[str, object]:
    """返回详情图 runtime 聚合。"""

    summary = repo.get_task(task_id)
    if summary is None or summary.task_type != "detail_page_v2":
        raise AppException(f"详情图任务 {task_id} 不存在", code=4044)
    runtime = runtime_service.get_runtime(summary)
    return success_response(runtime.model_dump(mode="json"), request.state.request_id)


@router.get("/{task_id}/files/{file_name:path}")
def get_detail_file(task_id: str, file_name: str) -> FileResponse:
    """访问详情图任务文件。"""

    target = runtime_service.resolve_task_file(task_id, file_name)
    return FileResponse(target)


def _build_payload(
    *,
    brand_name: str,
    product_name: str,
    tea_type: str,
    platform: str,
    style_preset: str,
    price_band: str,
    target_slice_count: int,
    image_size: str,
    main_image_task_id: str,
    selected_main_result_ids: str,
    selling_points_json: str,
    specs_json: str,
    style_notes: str,
    brew_suggestion: str,
    extra_requirements: str,
    prefer_main_result_first: bool,
) -> DetailPageJobCreatePayload:
    return DetailPageJobCreatePayload(
        brand_name=brand_name,
        product_name=product_name,
        tea_type=tea_type,
        platform=platform,
        style_preset=style_preset,
        price_band=price_band,
        target_slice_count=target_slice_count,
        image_size=image_size,
        main_image_task_id=main_image_task_id,
        selected_main_result_ids=_safe_json_list(selected_main_result_ids),
        selling_points=_safe_json_list(selling_points_json),
        specs=_safe_json_dict(specs_json),
        style_notes=style_notes,
        brew_suggestion=brew_suggestion,
        extra_requirements=extra_requirements,
        prefer_main_result_first=prefer_main_result_first,
    )


def _safe_json_list(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _safe_json_dict(raw: str) -> dict[str, str]:
    try:
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}
