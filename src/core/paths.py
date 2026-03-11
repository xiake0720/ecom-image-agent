from __future__ import annotations

from pathlib import Path

from src.core.config import get_settings


def get_task_dir(task_id: str) -> Path:
    return get_settings().tasks_dir / task_id


def get_task_inputs_dir(task_id: str) -> Path:
    return get_task_dir(task_id) / "inputs"


def get_task_generated_dir(task_id: str) -> Path:
    return get_task_dir(task_id) / "generated"


def get_task_final_dir(task_id: str) -> Path:
    return get_task_dir(task_id) / "final"


def get_task_preview_dir(task_id: str) -> Path:
    return get_task_dir(task_id) / "previews"


def get_task_exports_dir(task_id: str) -> Path:
    return get_task_dir(task_id) / "exports"


def ensure_task_dirs(task_id: str) -> dict[str, Path]:
    dirs = {
        "task": get_task_dir(task_id),
        "inputs": get_task_inputs_dir(task_id),
        "generated": get_task_generated_dir(task_id),
        "final": get_task_final_dir(task_id),
        "previews": get_task_preview_dir(task_id),
        "exports": get_task_exports_dir(task_id),
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs

