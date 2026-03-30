"""ZIP 导出服务。"""

from __future__ import annotations

import zipfile
from pathlib import Path

from src.core.paths import ensure_task_dirs
from src.services.storage.local_storage import LocalStorageService


def export_task_zip(storage: LocalStorageService, task_id: str, final_dir: Path, suffix: str = "images") -> Path:
    """导出最终图片 ZIP。"""

    return storage.create_zip(task_id=task_id, source_dir=final_dir, output_name=f"{task_id}_{suffix}")


def export_full_task_bundle(storage: LocalStorageService, task_id: str, task_dir: Path) -> Path:
    """导出完整任务目录 ZIP。"""

    exports_dir = ensure_task_dirs(task_id)["exports"]
    bundle_path = exports_dir / f"{task_id}_full_task_bundle.zip"
    with zipfile.ZipFile(bundle_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in _iter_bundle_paths(task_dir):
            if path.resolve() == bundle_path.resolve():
                continue
            archive.write(path, arcname=path.relative_to(task_dir))
    return bundle_path


def _iter_bundle_paths(task_dir: Path) -> list[Path]:
    """返回完整任务包需要打入的文件。"""

    include_paths = [
        task_dir / "inputs",
        task_dir / "task.json",
        task_dir / "director_output.json",
        task_dir / "prompt_plan_v2.json",
        task_dir / "qc_report.json",
        task_dir / "final_text_regions.json",
        task_dir / "generated",
        task_dir / "final",
        task_dir / "exports",
    ]
    paths: list[Path] = []
    for base in include_paths:
        if not base.exists():
            continue
        if base.is_file():
            paths.append(base)
            continue
        paths.extend(sorted(path for path in base.rglob("*") if path.is_file()))
    return paths
