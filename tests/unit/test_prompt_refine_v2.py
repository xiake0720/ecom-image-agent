from __future__ import annotations

import json
from pathlib import Path

from src.core.config import ResolvedModelSelection
from src.domain.director_output import DirectorOutput
from src.domain.task import CopyMode, Task
from src.workflows.nodes.prompt_refine_v2 import prompt_refine_v2
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


def test_prompt_refine_v2_mock_mode_generates_v2_prompt_plan(tmp_path: Path) -> None:
    task = Task(
        task_id="task-prompt-refine",
        brand_name="示例品牌",
        product_name="高山乌龙",
        task_dir=str(tmp_path / "task-prompt-refine"),
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
        "director_output": DirectorOutput.model_validate(
            {
                "product_summary": "高山乌龙茶礼，面向天猫电商。",
                "category": "tea",
                "platform": "tmall",
                "visual_style": "克制高端，画面留白清晰。",
                "shots": [
                    {
                        "shot_id": f"shot_{index:02d}",
                        "shot_role": role,
                        "objective": "展示商品价值",
                        "audience": "目标消费人群",
                        "selling_points": ["包装质感"],
                        "scene": "电商商品图场景",
                        "composition": "主体清晰，预留文案空间",
                        "visual_focus": "包装主体",
                        "copy_direction": "文案简洁有力",
                        "compliance_notes": ["不夸大功效"],
                    }
                    for index, role in enumerate(
                        [
                            "hero",
                            "packaging_feature",
                            "dry_leaf_detail",
                            "tea_soup",
                            "brewed_leaf_detail",
                            "gift_scene",
                            "lifestyle",
                            "process_or_quality",
                        ],
                        start=1,
                    )
                ],
            }
        ),
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }

    result = prompt_refine_v2(state, deps)
    shots = result["prompt_plan_v2"].shots

    assert len(shots) == 8
    assert all(4 <= len(shot.title_copy) <= 8 for shot in shots)
    assert all(8 <= len(shot.subtitle_copy) <= 15 for shot in shots)
    assert all(shot.render_prompt for shot in shots)
    assert shots[0].subject_occupancy_ratio == 0.66
    assert shots[0].copy_source == "auto"
    assert (tmp_path / "artifacts" / task.task_id / "prompt_plan_v2.json").exists()


def test_prompt_refine_v2_preserves_user_copy_inputs(tmp_path: Path) -> None:
    task = Task(
        task_id="task-prompt-refine-user-copy",
        brand_name="示例品牌",
        product_name="高山乌龙",
        task_dir=str(tmp_path / "task-prompt-refine-user-copy"),
        copy_mode=CopyMode.MIXED,
        title_text="东方茶礼",
        subtitle_text="原盒好茶送礼得体",
        selling_points=["高山原料", "包装挺括"],
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
        "director_output": DirectorOutput.model_validate(
            {
                "product_summary": "高山乌龙茶礼，面向天猫电商。",
                "category": "tea",
                "platform": "tmall",
                "visual_style": "克制高端，画面留白清晰。",
                "shots": [
                    {
                        "shot_id": "shot_01",
                        "shot_role": "hero",
                        "objective": "展示商品价值",
                        "audience": "目标消费人群",
                        "selling_points": ["包装质感"],
                        "scene": "电商商品图场景",
                        "composition": "主体清晰，预留文案空间",
                        "visual_focus": "包装主体",
                        "copy_direction": "文案简洁有力",
                        "compliance_notes": ["不夸大功效"],
                        "product_scale_guideline": "产品主体约占画面 2/3",
                        "subject_occupancy_ratio": 0.66,
                        "layout_hint": "左上保留文案区",
                        "typography_hint": "主标题最大",
                    }
                ],
            }
        ),
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }

    result = prompt_refine_v2(state, deps)
    shot = result["prompt_plan_v2"].shots[0]

    assert shot.title_copy == "东方茶礼"
    assert shot.subtitle_copy == "原盒好茶送礼得体"
    assert shot.selling_points_for_render == ["高山原料", "包装挺括"]
    assert shot.copy_source == "user"
