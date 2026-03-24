from __future__ import annotations

import json
from pathlib import Path

from src.core.config import ResolvedModelSelection
from src.domain.asset import Asset, AssetType
from src.domain.director_output import DirectorOutput
from src.domain.task import Task
from src.workflows.nodes.director_v2 import director_v2
from src.workflows.state import WorkflowDependencies


class TmpStorageService:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    def save_json_artifact(self, task_id: str, filename: str, payload: object) -> Path:
        task_dir = self.root_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        target = task_dir / filename
        content = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
        target.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    def load_cached_json_artifact(self, node_name: str, cache_key: str, response_model):
        del node_name, cache_key, response_model
        return None

    def save_cached_json_artifact(self, node_name: str, cache_key: str, payload: object, *, metadata=None) -> None:
        del node_name, cache_key, payload, metadata


def test_director_v2_mock_mode_builds_eight_shot_plan(tmp_path: Path) -> None:
    task = Task(
        task_id="task-director",
        brand_name="示例品牌",
        product_name="高山乌龙",
        task_dir=str(tmp_path / "task-director"),
    )
    deps = WorkflowDependencies(
        storage=TmpStorageService(tmp_path / "artifacts"),
        planning_provider=object(),
        image_generation_provider=object(),
        text_renderer=object(),
        text_provider_mode="mock",
        image_provider_mode="mock",
        planning_model_selection=ResolvedModelSelection("planning", "mock", "mock-local", "Mock", "test"),
    )
    state = {
        "task": task,
        "assets": [
            Asset(asset_id="asset-01", filename="hero.png", local_path="hero.png", asset_type=AssetType.WHITE_BG),
            Asset(asset_id="asset-02", filename="detail.png", local_path="detail.png", asset_type=AssetType.DETAIL),
        ],
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }

    result = director_v2(state, deps)

    assert isinstance(result["director_output"], DirectorOutput)
    assert len(result["director_output"].shots) == 8
    assert result["director_output"].shots[0].shot_role == "hero"
    assert result["director_output"].shots[0].subject_occupancy_ratio == 0.66
    assert result["director_output"].shots[-1].shot_role == "process_or_quality"
    assert (tmp_path / "artifacts" / task.task_id / "director_output.json").exists()
