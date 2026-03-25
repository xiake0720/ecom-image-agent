from __future__ import annotations

import json
from pathlib import Path

from src.core.config import ResolvedModelSelection
from src.domain.director_output import DirectorOutput
from src.domain.task import Task
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
        "director_output": _build_director_output(),
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }

    result = prompt_refine_v2(state, deps)
    shots = result["prompt_plan_v2"].shots

    assert len(shots) == 8
    assert shots[0].shot_role == "hero"
    assert shots[0].copy_strategy == "strong"
    assert shots[0].should_render_text is True
    assert 4 <= len(shots[0].title_copy) <= 8
    assert 8 <= len(shots[0].subtitle_copy) <= 15
    assert shots[0].subject_occupancy_ratio == 0.66
    assert shots[2].shot_role == "dry_leaf_detail"
    assert shots[2].copy_strategy == "none"
    assert shots[2].should_render_text is False
    assert shots[2].title_copy == ""
    assert shots[2].subtitle_copy == ""
    assert shots[2].selling_points_for_render == []
    assert all(shot.render_prompt for shot in shots)
    assert (tmp_path / "artifacts" / task.task_id / "prompt_plan_v2.json").exists()


def test_prompt_refine_v2_uses_brand_or_product_as_auto_copy_anchor(tmp_path: Path) -> None:
    task = Task(
        task_id="task-prompt-refine-anchor",
        brand_name="示例品牌",
        product_name="茶礼装",
        task_dir=str(tmp_path / "task-prompt-refine-anchor"),
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
                "product_summary": "茶礼装，面向天猫电商。",
                "category": "tea",
                "platform": "tmall",
                "visual_style": "高端极简，画面统一克制。",
                "series_strategy": "先包装识别，再细节和礼赠氛围。",
                "background_style_strategy": "背景图只学氛围。",
                "shots": [
                    {
                        "shot_id": "shot_01",
                        "shot_role": "hero",
                        "objective": "展示商品价值",
                        "audience": "目标消费人群",
                        "selling_point_direction": ["包装质感", "礼赠属性"],
                        "scene": "电商商品图场景",
                        "composition": "主体清晰，预留文案空间",
                        "visual_focus": "包装主体",
                        "copy_goal": "用短标题建立识别",
                        "copy_strategy": "strong",
                        "text_density": "medium",
                        "should_render_text": True,
                        "compliance_notes": ["不夸大功效"],
                        "product_scale_guideline": "产品主体约占画面 2/3",
                        "subject_occupancy_ratio": 0.66,
                        "layout_hint": "左上保留文案区",
                        "typography_hint": "主标题最大",
                        "style_reference_policy": "背景图只学氛围",
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

    assert shot.title_copy == "茶礼装"
    assert shot.copy_source == "system_brand_anchor"
    assert "严禁转写、复用、概括任何参考图可见文字" in shot.render_prompt


def _build_director_output() -> DirectorOutput:
    return DirectorOutput.model_validate(
        {
            "product_summary": "高山乌龙茶礼，面向天猫电商。",
            "category": "tea",
            "platform": "tmall",
            "visual_style": "克制高端，画面留白清晰。",
            "series_strategy": "先包装识别，再细节、茶汤、礼赠与品质说明。",
            "background_style_strategy": "背景图只学氛围和色调。",
            "shots": [
                {
                    "shot_id": f"shot_{index:02d}",
                    "shot_role": role,
                    "objective": "展示商品价值",
                    "audience": "目标消费人群",
                    "selling_point_direction": ["包装质感"],
                    "scene": "电商商品图场景",
                    "composition": "主体清晰，预留文案空间",
                    "visual_focus": "包装主体",
                    "copy_goal": "文案和画面协调",
                    "copy_strategy": "strong" if role in {"hero", "packaging_feature", "process_or_quality"} else ("light" if role == "gift_scene" else "none"),
                    "text_density": "medium" if role in {"hero", "packaging_feature", "process_or_quality"} else ("low" if role == "gift_scene" else "none"),
                    "should_render_text": role in {"hero", "packaging_feature", "gift_scene", "process_or_quality"},
                    "compliance_notes": ["不夸大功效"],
                    "product_scale_guideline": "hero 图主体约占画面 2/3" if role == "hero" else "主体识别清晰",
                    "subject_occupancy_ratio": 0.66 if role == "hero" else None,
                    "layout_hint": "左上保留文案区" if role == "hero" else "顶部保留信息区",
                    "typography_hint": "主标题最大" if role == "hero" else "信息清晰克制",
                    "style_reference_policy": "背景图只学氛围",
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
    )
