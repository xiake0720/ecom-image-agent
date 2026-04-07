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
from backend.schemas.detail import DetailPageAssetRef, DetailPagePromptPlanItem, DetailPageRenderResult

RenderProgressCallback = Callable[[int, int, list[DetailPageRenderResult]], None]


class DetailRenderService:
    """详情图正式渲染器。

    职责只限于：
    - 把 prompt plan 转成 provider 调用；
    - 统一落盘真实模型结果或 mock provider 结果；
    - 写出逐页 render report。

    这里不做任何本地叠字、拼图或占位图合成。
    """

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
            try:
                reference_assets, background_assets = self._build_assets(task_dir=task_dir, refs=item.references)
                generated = self._render_single_page(
                    provider=image_provider,
                    prompt_plan_item=item,
                    shot_id=item.page_id,
                    image_size=image_size,
                    output_dir=generated_dir,
                    reference_assets=reference_assets,
                    background_style_assets=background_assets,
                )
                target = generated_dir / f"{index:02d}_{item.page_id}.png"
                source_path = Path(generated.image_path)
                if source_path.resolve() != target.resolve():
                    shutil.copyfile(source_path, target)
                width, height = self._read_image_size(target)
                render_results.append(
                    DetailPageRenderResult(
                        render_id=f"detail-render-{index:02d}",
                        page_id=item.page_id,
                        page_title=item.page_title,
                        status="completed",
                        file_name=target.name,
                        relative_path=target.relative_to(task_dir).as_posix(),
                        width=width,
                        height=height,
                        reference_roles=[ref.role for ref in item.references],
                        provider_name=provider_name,
                        model_name=model_name,
                        started_at=started_at,
                        completed_at=datetime.utcnow().isoformat(),
                    )
                )
                self._write_render_report(task_dir=task_dir, rows=render_results)
                if progress_callback is not None:
                    progress_callback(index, total_count, list(render_results))
            except Exception as exc:
                render_results.append(
                    DetailPageRenderResult(
                        render_id=f"detail-render-{index:02d}",
                        page_id=item.page_id,
                        page_title=item.page_title,
                        status="failed",
                        reference_roles=[ref.role for ref in item.references],
                        provider_name=provider_name,
                        model_name=model_name,
                        error_message=str(exc),
                        started_at=started_at,
                        completed_at=datetime.utcnow().isoformat(),
                    )
                )
                self._write_render_report(task_dir=task_dir, rows=render_results)
                raise RuntimeError(f"详情图第 {index} 张渲染失败：{exc}") from exc
        return render_results

    def build_bundle(self, task_dir: Path) -> Path:
        """打包详情图任务产物。"""

        exports_dir = task_dir / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        archive = shutil.make_archive(str(exports_dir / "detail_bundle"), "zip", root_dir=task_dir)
        return Path(archive)

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
                            shot_role="detail_page",
                            render_prompt=prompt_plan_item.prompt,
                            copy_strategy="strong",
                            text_density="medium",
                            should_render_text=True,
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
