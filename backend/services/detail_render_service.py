"""详情图渲染与导出服务。"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable

from PIL import Image

from backend.engine.domain.asset import Asset, AssetType
from backend.engine.domain.generation_result import GeneratedImage, GenerationResult
from backend.engine.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from backend.engine.domain.prompt_plan_v2 import PromptPlanV2, PromptShot
from backend.schemas.detail import (
    DetailPageAssetRef,
    DetailPagePromptPlanItem,
    DetailPageRenderResult,
    DetailRetryStrategy,
)

RenderProgressCallback = Callable[[int, int, list[DetailPageRenderResult]], None]


class DetailRenderService:
    """详情图正式渲染器。"""

    def render_pages(
        self,
        *,
        task_dir: Path,
        prompt_plan: list[DetailPagePromptPlanItem],
        image_provider: object,
        provider_name: str,
        model_name: str,
        image_size: str,
        progress_callback: RenderProgressCallback | None = None,
    ) -> list[DetailPageRenderResult]:
        """按 prompt 计划逐页渲染详情图。"""

        generated_dir = task_dir / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)
        render_results: list[DetailPageRenderResult] = []
        total_count = len(prompt_plan)
        for index, item in enumerate(prompt_plan, start=1):
            started_at = datetime.utcnow().isoformat()
            page_result = self._render_with_retry(
                task_dir=task_dir,
                generated_dir=generated_dir,
                index=index,
                prompt_plan_item=item,
                image_provider=image_provider,
                provider_name=provider_name,
                model_name=model_name,
                image_size=image_size,
                started_at=started_at,
            )
            render_results.append(page_result)
            self._write_render_report(task_dir=task_dir, rows=render_results)
            if progress_callback is not None:
                progress_callback(index, total_count, list(render_results))
        return render_results

    def build_bundle(self, task_dir: Path) -> Path:
        """打包详情图任务产物。"""

        exports_dir = task_dir / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        archive = shutil.make_archive(str(exports_dir / "detail_bundle"), "zip", root_dir=task_dir)
        return Path(archive)

    def _render_with_retry(
        self,
        *,
        task_dir: Path,
        generated_dir: Path,
        index: int,
        prompt_plan_item: DetailPagePromptPlanItem,
        image_provider: object,
        provider_name: str,
        model_name: str,
        image_size: str,
        started_at: str,
    ) -> DetailPageRenderResult:
        attempts = self._build_attempt_items(prompt_plan_item)
        applied_strategies: list[DetailRetryStrategy] = []
        last_error = ""
        for attempt_index, (strategy, attempt_item) in enumerate(attempts, start=1):
            try:
                reference_assets, background_assets = self._build_assets(task_dir=task_dir, refs=attempt_item.references)
                generated = self._render_single_page(
                    provider=image_provider,
                    prompt_plan_item=attempt_item,
                    shot_id=attempt_item.page_id,
                    image_size=image_size,
                    output_dir=generated_dir,
                    reference_assets=reference_assets,
                    background_style_assets=background_assets,
                )
                target = generated_dir / f"{index:02d}_{attempt_item.page_id}.png"
                source_path = Path(generated.image_path)
                if source_path.resolve() != target.resolve():
                    shutil.copyfile(source_path, target)
                width, height = self._read_image_size(target)
                return DetailPageRenderResult(
                    render_id=f"detail-render-{index:02d}",
                    page_id=attempt_item.page_id,
                    page_title=attempt_item.page_title,
                    page_role=attempt_item.page_role,
                    status="completed",
                    file_name=target.name,
                    relative_path=target.relative_to(task_dir).as_posix(),
                    width=width,
                    height=height,
                    reference_roles=[ref.role for ref in attempt_item.references],
                    provider_name=provider_name,
                    model_name=model_name,
                    retry_count=max(0, attempt_index - 1),
                    retry_strategies=applied_strategies,
                    started_at=started_at,
                    completed_at=datetime.utcnow().isoformat(),
                )
            except Exception as exc:
                last_error = str(exc)
                if strategy != "original_prompt_retry":
                    applied_strategies.append(strategy)
                if attempt_index >= len(attempts):
                    break
                if not self._should_continue_retry(last_error, prompt_plan_item):
                    break
        return DetailPageRenderResult(
            render_id=f"detail-render-{index:02d}",
            page_id=prompt_plan_item.page_id,
            page_title=prompt_plan_item.page_title,
            page_role=prompt_plan_item.page_role,
            status="failed",
            reference_roles=[ref.role for ref in prompt_plan_item.references],
            provider_name=provider_name,
            model_name=model_name,
            error_message=last_error,
            retry_count=len(applied_strategies),
            retry_strategies=applied_strategies,
            started_at=started_at,
            completed_at=datetime.utcnow().isoformat(),
        )

    def _build_attempt_items(
        self,
        item: DetailPagePromptPlanItem,
    ) -> list[tuple[DetailRetryStrategy, DetailPagePromptPlanItem]]:
        attempts: list[tuple[DetailRetryStrategy, DetailPagePromptPlanItem]] = [("original_prompt_retry", item)]
        text_light_item = item.model_copy(
            update={
                "prompt": f"{item.prompt}\n重试策略：降低图中文字密度，只保留主标题和必要短标签。",
                "subtitle_copy": "",
                "selling_points_for_render": item.selling_points_for_render[:1],
                "text_density": "none" if item.text_density == "low" else "low",
                "copy_strategy": "light",
            }
        )
        attempts.append(("text_density_reduction", text_light_item))
        if item.page_role in {"scene_value_story", "brand_trust", "gift_openbox_portable", "tea_soup_evidence"}:
            rebound_refs = [ref for ref in item.references if ref.role not in {"scene_ref", "bg_ref"}] or list(item.references)
            rebound_item = item.model_copy(
                update={
                    "references": rebound_refs,
                    "prompt": f"{item.prompt}\n重试策略：弱化场景参考，仅保留包装与证据锚点，减少非必要背景干扰。",
                }
            )
            attempts.append(("reference_rebinding", rebound_item))
        else:
            packaging_item = item.model_copy(
                update={
                    "prompt": f"{item.prompt}\n重试策略：进一步强化包装保护和主体稳定，减少装饰元素。",
                }
            )
            attempts.append(("packaging_emphasis", packaging_item))
        return attempts

    def _should_continue_retry(self, error_message: str, item: DetailPagePromptPlanItem) -> bool:
        if not item.retryable:
            return False
        normalized = error_message.lower()
        transient_markers = [
            "bad_response_body",
            "unexpected end of json input",
            "response is not valid json",
            "500",
            "timed out",
        ]
        if any(marker in normalized for marker in transient_markers):
            return True
        return item.page_role in {"scene_value_story", "brand_trust", "gift_openbox_portable", "tea_soup_evidence"}

    def _render_single_page(
        self,
        *,
        provider,
        prompt_plan_item: DetailPagePromptPlanItem,
        shot_id: str,
        image_size: str,
        output_dir: Path,
        reference_assets: list[Asset],
        background_style_assets: list[Asset],
    ) -> GeneratedImage:
        """执行单页模型渲染，并返回 provider 原始结果图。"""

        if hasattr(provider, "generate_images_v2"):
            result = provider.generate_images_v2(
                PromptPlanV2(
                    shots=[
                        PromptShot(
                            shot_id=shot_id,
                            shot_role=prompt_plan_item.page_role,
                            render_prompt=prompt_plan_item.prompt,
                            copy_strategy=prompt_plan_item.copy_strategy,
                            text_density=prompt_plan_item.text_density,
                            should_render_text=prompt_plan_item.should_render_text,
                            title_copy=prompt_plan_item.title_copy,
                            subtitle_copy=prompt_plan_item.subtitle_copy,
                            selling_points_for_render=prompt_plan_item.selling_points_for_render,
                            aspect_ratio=prompt_plan_item.target_aspect_ratio,
                            image_size=image_size,
                        )
                    ]
                ),
                output_dir=output_dir,
                reference_assets=reference_assets,
                background_style_assets=background_style_assets,
            )
        else:
            result = provider.generate_images(
                ImagePromptPlan(
                    prompts=[
                        ImagePrompt(
                            shot_id=shot_id,
                            shot_type="detail_page",
                            prompt=prompt_plan_item.prompt,
                            output_size=f"{prompt_plan_item.target_width}x{prompt_plan_item.target_height}",
                        )
                    ]
                ),
                output_dir=output_dir,
                reference_assets=reference_assets,
                background_style_assets=background_style_assets,
            )
        return self._first_image(result, shot_id)

    def _first_image(self, result: GenerationResult, shot_id: str) -> GeneratedImage:
        if not result.images:
            raise RuntimeError(f"详情图页 {shot_id} 未返回任何图片")
        image = result.images[0]
        if image.shot_id != shot_id:
            return image.model_copy(update={"shot_id": shot_id})
        return image

    def _build_assets(
        self,
        *,
        task_dir: Path,
        refs: list[DetailPageAssetRef],
    ) -> tuple[list[Asset], list[Asset]]:
        """把详情图引用转换成统一 Asset。"""

        product_assets: list[Asset] = []
        background_assets: list[Asset] = []
        for ref in refs:
            source = task_dir / ref.relative_path
            if not source.exists():
                continue
            asset = Asset(
                asset_id=ref.asset_id,
                filename=ref.file_name,
                local_path=str(source),
                mime_type=self._guess_mime_type(source),
                asset_type=AssetType.BACKGROUND_STYLE if ref.role in {"scene_ref", "bg_ref"} else AssetType.PRODUCT,
                width=ref.width,
                height=ref.height,
                tags=[ref.role],
            )
            if ref.role in {"scene_ref", "bg_ref"}:
                background_assets.append(asset)
            else:
                product_assets.append(asset)
        return product_assets, background_assets

    def _write_render_report(self, *, task_dir: Path, rows: list[DetailPageRenderResult]) -> None:
        report_path = task_dir / "generated" / "detail_render_report.json"
        report_path.write_text(
            json.dumps([item.model_dump(mode="json") for item in rows], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _read_image_size(self, path: Path) -> tuple[int | None, int | None]:
        try:
            with Image.open(path) as image:
                return image.size
        except OSError:
            return None, None

    def _guess_mime_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"
