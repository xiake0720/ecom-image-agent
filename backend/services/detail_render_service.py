"""详情图渲染与导出服务。"""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from backend.engine.core.config import get_settings
from backend.schemas.detail import DetailPageCopyBlock, DetailPagePromptPlanItem


class DetailRenderService:
    """V1 详情图渲染器。"""

    def render_pages(
        self,
        *,
        task_dir: Path,
        prompt_plan: list[DetailPagePromptPlanItem],
        copy_blocks: list[DetailPageCopyBlock],
        image_size: str,
    ) -> list[Path]:
        """按 prompt 计划生成占位详情图成图。"""

        generated_dir = task_dir / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)
        copy_map = {f"{item.page_id}:{item.screen_id}": item for item in copy_blocks}
        font = self._load_font(44)
        small_font = self._load_font(32)
        paths: list[Path] = []
        width, height = self._resolve_size(image_size)
        for index, item in enumerate(prompt_plan, start=1):
            canvas = Image.new("RGB", (width, height), color=(243, 239, 230))
            draw = ImageDraw.Draw(canvas)
            draw.rectangle([(0, 0), (width, height // 2)], fill=(247, 244, 236))
            draw.rectangle([(0, height // 2), (width, height)], fill=(236, 231, 218))
            draw.text((64, 56), f"{item.page_title}", font=font, fill=(52, 47, 38))
            draw.text((64, 120), f"风格：{item.global_style_anchor}", font=small_font, fill=(88, 82, 72))
            y = 220
            for theme in item.screen_themes:
                draw.text((64, y), f"• {theme}", font=small_font, fill=(64, 58, 48))
                y += 50
            for screen_no in (1, 2):
                key = f"{item.page_id}:p{index:02d}s{screen_no}"
                block = copy_map.get(key)
                if block:
                    base_y = 420 if screen_no == 1 else height // 2 + 120
                    draw.text((64, base_y), block.headline[:30], font=font, fill=(45, 41, 34))
                    draw.text((64, base_y + 62), block.subheadline[:45], font=small_font, fill=(75, 69, 60))
            out_path = generated_dir / f"detail_{index:02d}.png"
            canvas.save(out_path)
            paths.append(out_path)
        return paths

    def build_bundle(self, task_dir: Path) -> Path:
        """打包详情图任务产物。"""

        exports_dir = task_dir / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        archive = shutil.make_archive(str(exports_dir / "detail_bundle"), "zip", root_dir=task_dir)
        return Path(archive)

    def _resolve_size(self, image_size: str) -> tuple[int, int]:
        """解析 1:3 输出尺寸。"""

        if image_size.upper() == "2K":
            return (1536, 4608)
        return (1080, 3240)

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """加载中文字体，失败时回退默认字体。"""

        settings = get_settings()
        for path in settings.resolve_project_font_candidates() + settings.resolve_system_chinese_font_candidates():
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size=size)
                except OSError:
                    continue
        return ImageFont.load_default()

