"""详情图渲染与导出服务。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from backend.engine.core.config import get_settings
from backend.engine.domain.asset import Asset, AssetType
from backend.engine.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from backend.engine.domain.prompt_plan_v2 import PromptPlanV2, PromptShot
from backend.engine.providers.router import build_capability_bindings
from backend.schemas.detail import DetailPageAssetRef, DetailPageCopyBlock, DetailPagePromptPlanItem


class DetailRenderService:
    """详情图渲染器（强制走真实模型生成，不允许占位图）。"""

    def render_pages(
        self,
        *,
        task_dir: Path,
        prompt_plan: list[DetailPagePromptPlanItem],
        copy_blocks: list[DetailPageCopyBlock],
        image_size: str,
    ) -> list[Path]:
        """按 prompt 计划调用图片 provider 逐页生成详情图。"""

        settings = get_settings()
        bindings = build_capability_bindings(settings)
        if bindings.image_route.mode != "real":
            raise RuntimeError("详情图正式渲染要求真实图片 provider，当前为 mock 模式。")
        generated_dir = task_dir / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)
        copy_map = self._group_copy_blocks(copy_blocks)
        paths: list[Path] = []
        render_report: list[dict[str, object]] = []
        for index, item in enumerate(prompt_plan, start=1):
            try:
                prompt_text = self._assemble_page_prompt(item=item, page_copy_blocks=copy_map.get(item.page_id, []))
                reference_assets, background_assets = self._build_assets(task_dir=task_dir, refs=item.references)
                generated = self._render_single_page(
                    provider=bindings.image_generation_provider,
                    prompt_text=prompt_text,
                    shot_id=f"detail-{index:02d}",
                    image_size=image_size,
                    output_dir=generated_dir,
                    reference_assets=reference_assets,
                    background_style_assets=background_assets,
                )
                target = generated_dir / f"detail_{index:02d}.png"
                target.write_bytes(Path(generated).read_bytes())
                paths.append(target)
                render_report.append({"page_id": item.page_id, "status": "completed", "file_name": target.name})
            except Exception as exc:
                render_report.append({"page_id": item.page_id, "status": "failed", "error_message": str(exc)})
                (task_dir / "generated" / "detail_render_report.json").write_text(
                    json.dumps(render_report, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                raise RuntimeError(f"详情图第 {index} 张渲染失败：{exc}") from exc
        (task_dir / "generated" / "detail_render_report.json").write_text(
            json.dumps(render_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return paths

    def build_bundle(self, task_dir: Path) -> Path:
        """打包详情图任务产物。"""

        exports_dir = task_dir / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        archive = shutil.make_archive(str(exports_dir / "detail_bundle"), "zip", root_dir=task_dir)
        return Path(archive)

    def _group_copy_blocks(self, copy_blocks: list[DetailPageCopyBlock]) -> dict[str, list[DetailPageCopyBlock]]:
        """按 page_id 聚合文案，便于构建单页 prompt。"""

        grouped: dict[str, list[DetailPageCopyBlock]] = {}
        for item in copy_blocks:
            grouped.setdefault(item.page_id, []).append(item)
        return grouped

    def _assemble_page_prompt(self, *, item: DetailPagePromptPlanItem, page_copy_blocks: list[DetailPageCopyBlock]) -> str:
        """把页面 prompt、主题和文案约束收口为最终生图指令。"""

        lines = [item.prompt, f"风格锚点：{item.global_style_anchor}"]
        if item.screen_themes:
            lines.append(f"双屏主题：{'；'.join(item.screen_themes)}")
        for block in page_copy_blocks:
            lines.append(f"{block.screen_id}主标题：{block.headline}")
            if block.subheadline:
                lines.append(f"{block.screen_id}副标题：{block.subheadline}")
            if block.selling_points:
                lines.append(f"{block.screen_id}卖点：{'；'.join(block.selling_points)}")
        lines.append("输出要求：生成 1:3 电商详情长图，文字清晰可读，禁止输出无关文案。")
        if item.negative_prompt:
            lines.append(f"负向约束：{item.negative_prompt}")
        return "\n".join(lines).strip()

    def _build_assets(self, *, task_dir: Path, refs: list[DetailPageAssetRef]) -> tuple[list[Asset], list[Asset]]:
        """把详情图引用转换为引擎统一 Asset。"""

        product_assets: list[Asset] = []
        bg_assets: list[Asset] = []
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
                tags=[ref.role],
            )
            if ref.role in {"scene_ref", "bg_ref"}:
                bg_assets.append(asset)
            else:
                product_assets.append(asset)
        return product_assets, bg_assets

    def _render_single_page(
        self,
        *,
        provider,
        prompt_text: str,
        shot_id: str,
        image_size: str,
        output_dir: Path,
        reference_assets: list[Asset],
        background_style_assets: list[Asset],
    ) -> str:
        """执行单页真实模型渲染并返回落盘图片路径。"""

        if hasattr(provider, "generate_images_v2"):
            result = provider.generate_images_v2(
                PromptPlanV2(
                    shots=[
                        PromptShot(
                            shot_id=shot_id,
                            shot_role="detail_page",
                            render_prompt=prompt_text,
                            copy_strategy="light",
                            text_density="medium",
                            should_render_text=True,
                            aspect_ratio="1:3",
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
                            prompt=prompt_text,
                            output_size="1080x3240",
                        )
                    ]
                ),
                output_dir=output_dir,
                reference_assets=reference_assets,
                background_style_assets=background_style_assets,
            )
        if not result.images:
            raise RuntimeError("模型返回为空，未生成任何图片。")
        return result.images[0].image_path

    def _guess_mime_type(self, path: Path) -> str:
        """按后缀推断图片 mime。"""

        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"
