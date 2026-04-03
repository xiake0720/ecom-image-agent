"""详情图任务服务。"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from queue import Queue
from threading import Lock, Thread

from fastapi import UploadFile

from backend.engine.core.paths import ensure_task_dirs, get_task_dir
from backend.engine.domain.task import Task, TaskStatus
from backend.engine.services.storage.local_storage import LocalStorageService
from backend.repositories.task_repository import TaskRepository
from backend.schemas.detail import (
    DetailPageAssetRef,
    DetailPageJobCreatePayload,
    DetailPageJobCreateResult,
    DetailPageQCSummary,
)
from backend.services.detail_copy_service import DetailCopyService
from backend.services.detail_planner_service import DetailPlannerService
from backend.services.detail_prompt_service import DetailPromptService
from backend.services.detail_render_service import DetailRenderService


@dataclass
class PreparedDetailTask:
    """详情图队列任务上下文。"""

    payload: DetailPageJobCreatePayload
    task_id: str


class _DetailTaskQueue:
    """详情图单 worker 队列。"""

    def __init__(self) -> None:
        self._queue: Queue[PreparedDetailTask] = Queue()
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
    """负责详情图任务创建、执行、落盘。"""

    def __init__(self) -> None:
        self.storage = LocalStorageService()
        self.repo = TaskRepository()
        self.planner = DetailPlannerService(template_root=Path("backend/templates"))
        self.copy_service = DetailCopyService()
        self.prompt_service = DetailPromptService()
        self.render_service = DetailRenderService()

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
        """创建详情图任务并投递到后台队列。"""

        task_id = self.storage.create_task_id()
        task_dirs = ensure_task_dirs(task_id)
        self._ensure_detail_dirs(task_dirs["task"])

        task = Task(
            task_id=task_id,
            brand_name=payload.brand_name,
            product_name=payload.product_name,
            category=payload.category,
            platform=payload.platform,
            shot_count=payload.target_slice_count,
            aspect_ratio="1:3",
            image_size=payload.image_size,
            style_type=payload.style_preset,
            style_notes=payload.style_notes,
            status=TaskStatus.CREATED,
            task_dir=str(task_dirs["task"]),
            current_step="queued",
            current_step_label="详情图任务已提交",
            progress_percent=0,
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
        self._write_inputs(task_id, payload, assets)

        summary = self.repo.create_task_summary(
            task_id=task_id,
            task_type="detail_page_v2",
            status="created",
            title=payload.product_name or f"{payload.tea_type}详情图",
            platform=payload.platform,
            result_path=str(get_task_dir(task_id) / "generated"),
            created_at=task.created_at,
        )
        self.repo.save_task(summary)

        prepared = PreparedDetailTask(payload=payload.model_copy(), task_id=task_id)
        if plan_only:
            self.run_prepared(prepared, plan_only=True)
        else:
            detail_task_queue.enqueue(prepared, lambda item: self.run_prepared(item, plan_only=False))
        return DetailPageJobCreateResult(task_id=task_id, status="created")

    def run_prepared(self, prepared: PreparedDetailTask, *, plan_only: bool) -> None:
        """执行详情图任务。"""

        task_dir = get_task_dir(prepared.task_id)
        task = Task.model_validate_json((task_dir / "task.json").read_text(encoding="utf-8"))
        try:
            task = task.model_copy(update={"status": TaskStatus.RUNNING, "current_step": "planning", "current_step_label": "正在生成详情规划", "progress_percent": 15})
            self.storage.save_task_manifest(task)
            self.repo.save_runtime_task(task, task_type="detail_page_v2")

            assets = self._load_assets(task_dir / "inputs" / "asset_manifest.json")
            plan = self.planner.build_plan(prepared.payload, assets)
            (task_dir / "plan" / "detail_plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")

            copy_blocks = self.copy_service.build_copy(prepared.payload, plan)
            (task_dir / "plan" / "detail_copy_plan.json").write_text(json.dumps([item.model_dump(mode="json") for item in copy_blocks], ensure_ascii=False, indent=2), encoding="utf-8")

            prompt_plan = self.prompt_service.build_prompt_plan(plan, copy_blocks, assets)
            (task_dir / "plan" / "detail_prompt_plan.json").write_text(json.dumps([item.model_dump(mode="json") for item in prompt_plan], ensure_ascii=False, indent=2), encoding="utf-8")

            if plan_only:
                task = task.model_copy(update={"status": TaskStatus.COMPLETED, "current_step": "planning_done", "current_step_label": "规划已完成", "progress_percent": 100})
                self.storage.save_task_manifest(task)
                self.repo.save_runtime_task(task, task_type="detail_page_v2")
                return

            task = task.model_copy(update={"current_step": "rendering", "current_step_label": "正在生成详情图", "progress_percent": 70})
            self.storage.save_task_manifest(task)
            self.repo.save_runtime_task(task, task_type="detail_page_v2")

            self.render_service.render_pages(task_dir=task_dir, prompt_plan=prompt_plan, copy_blocks=copy_blocks, image_size=prepared.payload.image_size)
            qc = self._run_qc(task_dir, plan.total_pages, prompt_plan, copy_blocks)
            (task_dir / "qc" / "detail_qc_report.json").write_text(qc.model_dump_json(indent=2), encoding="utf-8")
            self.render_service.build_bundle(task_dir)

            task = task.model_copy(update={"status": TaskStatus.COMPLETED, "current_step": "done", "current_step_label": "详情图任务完成", "progress_percent": 100})
            self.storage.save_task_manifest(task)
            self.repo.save_runtime_task(task, task_type="detail_page_v2")
        except Exception as exc:
            failed = task.model_copy(update={"status": TaskStatus.FAILED, "current_step": "failed", "current_step_label": "详情图任务失败", "error_message": str(exc)})
            self.storage.save_task_manifest(failed)
            self.repo.save_runtime_task(failed, task_type="detail_page_v2")

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
        """写入素材并记录角色。"""

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
        for index, rel in enumerate(payload.selected_main_result_ids, start=counter):
            source = get_task_dir(payload.main_image_task_id) / rel
            if source.exists():
                name = f"main_{index:03d}_{Path(rel).name}"
                target = get_task_dir(task_id) / "inputs" / name
                target.write_bytes(source.read_bytes())
                asset_rows.append(
                    DetailPageAssetRef(
                        asset_id=f"asset-{index:03d}",
                        role="main_result",
                        file_name=name,
                        relative_path=f"inputs/{name}",
                        source_type="main_task",
                        source_task_id=payload.main_image_task_id,
                        source_result_file=rel,
                    )
                )
        return asset_rows

    def _write_inputs(self, task_id: str, payload: DetailPageJobCreatePayload, assets: list[DetailPageAssetRef]) -> None:
        """写入请求参数与素材清单。"""

        task_dir = get_task_dir(task_id)
        (task_dir / "inputs" / "request_payload.json").write_text(payload.model_dump_json(indent=2), encoding="utf-8")
        (task_dir / "inputs" / "asset_manifest.json").write_text(json.dumps([item.model_dump(mode="json") for item in assets], ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_assets(self, path: Path) -> list[DetailPageAssetRef]:
        payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        return [DetailPageAssetRef.model_validate(item) for item in payload]

    def _run_qc(self, task_dir: Path, planned_count: int, prompt_plan: list, copy_blocks: list) -> DetailPageQCSummary:
        """规则型 QC。"""

        issues: list[str] = []
        generated = list((task_dir / "generated").glob("*.png"))
        if len(generated) != planned_count:
            issues.append("生成数量与计划不一致")
        if not copy_blocks:
            issues.append("文案规划为空")
        if any(not item.references for item in prompt_plan):
            issues.append("存在页面缺少参考图绑定")
        if not any(any(ref.role in {"packaging", "main_result"} for ref in item.references) for item in prompt_plan[:1]):
            issues.append("首屏缺少包装主体")
        if any("茶汤" in "".join(item.screen_themes) and not any(ref.role == "tea_soup" for ref in item.references) for item in prompt_plan):
            issues.append("茶汤屏缺少 tea_soup 参考")

        return DetailPageQCSummary(
            passed=len(issues) == 0,
            warning_count=len(issues),
            failed_count=0,
            issues=issues,
        )

    def _ensure_detail_dirs(self, task_dir: Path) -> None:
        for name in ["inputs", "plan", "generated", "qc", "exports"]:
            (task_dir / name).mkdir(parents=True, exist_ok=True)

