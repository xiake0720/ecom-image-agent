from __future__ import annotations

from pathlib import Path

from src.ui.components.download_panel import build_download_widget_key
from src.ui.pages.result_view import resolve_result_image_paths


def test_download_widget_key_is_unique_across_panels_and_paths() -> None:
    preview_path = Path("outputs/tasks/task-a/previews/01_shot-01.png")
    final_path = Path("outputs/tasks/task-a/final/01_shot-01.png")

    preview_key = build_download_widget_key("preview", preview_path)
    final_key = build_download_widget_key("final", final_path)

    assert preview_key != final_key
    assert preview_key.startswith("download-preview-01_shot-01.png-")
    assert final_key.startswith("download-final-01_shot-01.png-")


def test_preview_mode_does_not_repeat_preview_images_in_final_area() -> None:
    task_state = {
        "render_variant": "preview",
        "preview_generation_result": {
            "images": [
                {"image_path": "outputs/tasks/task-a/final_preview/01_shot-01.png"},
            ]
        },
        "generation_result": {
            "images": [
                {"image_path": "outputs/tasks/task-a/final_preview/01_shot-01.png"},
            ]
        },
    }

    preview_paths, final_paths = resolve_result_image_paths(task_state)

    assert preview_paths == ["outputs/tasks/task-a/final_preview/01_shot-01.png"]
    assert final_paths == []
