from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from PIL import Image

from src.core.paths import ensure_task_dirs
from src.domain.asset import Asset, AssetType
from src.domain.task import Task


class LocalStorageService:
    def create_task_id(self) -> str:
        return uuid4().hex

    def prepare_task_dirs(self, task_id: str) -> dict[str, Path]:
        return ensure_task_dirs(task_id)

    def save_task_manifest(self, task: Task) -> Path:
        task_path = Path(task.task_dir) / "task.json"
        task_path.write_text(task.model_dump_json(indent=2), encoding="utf-8")
        return task_path

    def save_uploads(self, task_id: str, uploads: Iterable[tuple[str, bytes]]) -> list[Asset]:
        task_dirs = ensure_task_dirs(task_id)
        assets: list[Asset] = []
        for index, (filename, payload) in enumerate(uploads, start=1):
            target = task_dirs["inputs"] / filename
            target.write_bytes(payload)
            width, height = self._read_image_size(target)
            assets.append(
                Asset(
                    asset_id=f"asset-{index:02d}",
                    filename=filename,
                    local_path=str(target),
                    mime_type="image/png",
                    asset_type=AssetType.PRODUCT if index == 1 else AssetType.DETAIL,
                    width=width,
                    height=height,
                )
            )
        return assets

    def save_json_artifact(self, task_id: str, filename: str, payload: object) -> Path:
        task_path = ensure_task_dirs(task_id)["task"] / filename
        task_path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(payload, "model_dump"):
            content = payload.model_dump(mode="json")
        else:
            content = payload
        task_path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        return task_path

    def create_preview(self, image_path: str, preview_path: Path, max_side: int = 480) -> Path:
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(image_path) as image:
            image.thumbnail((max_side, max_side))
            image.save(preview_path)
        return preview_path

    def create_zip(self, task_id: str, source_dir: Path, output_name: str = "results") -> Path:
        exports_dir = ensure_task_dirs(task_id)["exports"]
        archive_base = exports_dir / output_name
        zip_path = shutil.make_archive(str(archive_base), "zip", root_dir=source_dir)
        return Path(zip_path)

    def _read_image_size(self, image_path: Path) -> tuple[int | None, int | None]:
        try:
            with Image.open(image_path) as image:
                return image.size
        except OSError:
            return None, None
