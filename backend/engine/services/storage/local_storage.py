"""本地存储服务。

文件位置：
- `src/services/storage/local_storage.py`

职责：
- 管理任务目录与输入输出落盘
- 保存上传素材并补齐最小资产清单
- 提供节点缓存与导出能力
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Iterable, TypeVar
from uuid import uuid4

from PIL import Image

from backend.engine.core.paths import ensure_task_dirs, get_cache_dir
from backend.engine.domain.asset import Asset, AssetType
from backend.engine.domain.task import Task

ModelT = TypeVar("ModelT")


class LocalStorageService:
    """任务本地文件存储实现。"""

    def create_task_id(self) -> str:
        """生成唯一任务 ID。"""

        return uuid4().hex

    def prepare_task_dirs(self, task_id: str) -> dict[str, Path]:
        """确保任务目录结构存在。"""

        return ensure_task_dirs(task_id)

    def save_task_manifest(self, task: Task) -> Path:
        """把任务 manifest 写入任务目录。"""

        task_path = Path(task.task_dir) / "task.json"
        task_path.write_text(task.model_dump_json(indent=2), encoding="utf-8")
        return task_path

    def save_uploads(self, task_id: str, uploads: Iterable[tuple[str, bytes, AssetType]]) -> list[Asset]:
        """把上传文件写入任务目录，并生成素材清单。"""

        task_dirs = ensure_task_dirs(task_id)
        assets: list[Asset] = []
        for index, (filename, payload, asset_type) in enumerate(uploads, start=1):
            target = task_dirs["inputs"] / filename
            target.write_bytes(payload)
            width, height = self._read_image_size(target)
            assets.append(
                Asset(
                    asset_id=f"asset-{index:02d}",
                    filename=filename,
                    local_path=str(target),
                    mime_type=self._guess_mime_type(target),
                    asset_type=asset_type,
                    width=width,
                    height=height,
                )
            )
        return assets

    def save_json_artifact(self, task_id: str, filename: str, payload: object) -> Path:
        """把结构化产物写入任务目录。"""

        task_path = ensure_task_dirs(task_id)["task"] / filename
        task_path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(payload, "model_dump"):
            content = payload.model_dump(mode="json")
        else:
            content = payload
        task_path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        return task_path

    def create_preview(self, image_path: str, preview_path: Path, max_side: int = 480) -> Path:
        """生成统一尺寸的预览图。"""

        preview_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(image_path) as image:
            image.thumbnail((max_side, max_side))
            image.save(preview_path)
        return preview_path

    def create_zip(self, task_id: str, source_dir: Path, output_name: str = "results") -> Path:
        """把结果目录打包为 ZIP。"""

        exports_dir = ensure_task_dirs(task_id)["exports"]
        archive_base = exports_dir / output_name
        zip_path = shutil.make_archive(str(archive_base), "zip", root_dir=source_dir)
        return Path(zip_path)

    def load_cached_json_artifact(self, node_name: str, cache_key: str, response_model: type[ModelT]) -> ModelT | None:
        """读取节点缓存。"""

        cache_path = self._get_cache_path(node_name, cache_key)
        if not cache_path.exists():
            return None
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        data = payload.get("payload", payload)
        if hasattr(response_model, "model_validate"):
            return response_model.model_validate(data)
        return data

    def save_cached_json_artifact(
        self,
        node_name: str,
        cache_key: str,
        payload: object,
        *,
        metadata: dict[str, object] | None = None,
    ) -> Path:
        """保存节点缓存。"""

        cache_path = self._get_cache_path(node_name, cache_key)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(payload, "model_dump"):
            content = payload.model_dump(mode="json")
        else:
            content = payload
        wrapped = {
            "metadata": metadata or {},
            "payload": content,
        }
        cache_path.write_text(json.dumps(wrapped, ensure_ascii=False, indent=2), encoding="utf-8")
        return cache_path

    def _get_cache_path(self, node_name: str, cache_key: str) -> Path:
        """返回缓存文件路径。"""

        return get_cache_dir() / node_name / f"{cache_key}.json"

    def _read_image_size(self, image_path: Path) -> tuple[int | None, int | None]:
        """读取图片尺寸。"""

        try:
            with Image.open(image_path) as image:
                return image.size
        except OSError:
            return None, None

    def _guess_mime_type(self, image_path: Path) -> str:
        """根据后缀推断最小可用 mime type。"""

        suffix = image_path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"
