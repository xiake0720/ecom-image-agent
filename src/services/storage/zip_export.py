from __future__ import annotations

from pathlib import Path

from src.services.storage.local_storage import LocalStorageService


def export_task_zip(storage: LocalStorageService, task_id: str, final_dir: Path) -> Path:
    return storage.create_zip(task_id=task_id, source_dir=final_dir, output_name=f"{task_id}_images")

