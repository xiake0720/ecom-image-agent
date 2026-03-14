from __future__ import annotations

import zipfile
from pathlib import Path

from src.core.paths import ensure_task_dirs
from src.services.storage.local_storage import LocalStorageService


def export_task_zip(storage: LocalStorageService, task_id: str, final_dir: Path, suffix: str = "images") -> Path:
    return storage.create_zip(task_id=task_id, source_dir=final_dir, output_name=f"{task_id}_{suffix}")


def export_full_task_bundle(storage: LocalStorageService, task_id: str, task_dir: Path) -> Path:
    exports_dir = ensure_task_dirs(task_id)["exports"]
    bundle_path = exports_dir / f"{task_id}_full_task_bundle.zip"
    with zipfile.ZipFile(bundle_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in _iter_bundle_paths(task_dir):
            if path.resolve() == bundle_path.resolve():
                continue
            if path.is_file():
                archive.write(path, arcname=path.relative_to(task_dir))
    return bundle_path


def _iter_bundle_paths(task_dir: Path) -> list[Path]:
    include_paths = [
        task_dir / "inputs",
        task_dir / "task.json",
        task_dir / "product_analysis.json",
        task_dir / "style_architecture.json",
        task_dir / "shot_plan.json",
        task_dir / "copy_plan.json",
        task_dir / "layout_plan.json",
        task_dir / "shot_prompt_specs.json",
        task_dir / "image_prompt_plan.json",
        task_dir / "qc_report.json",
        task_dir / "qc_report_preview.json",
        task_dir / "generated",
        task_dir / "generated_preview",
        task_dir / "final",
        task_dir / "final_preview",
        task_dir / "previews",
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
