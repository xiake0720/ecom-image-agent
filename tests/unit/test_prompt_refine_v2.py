"""prompt_refine_v2 节点最小回归测试。"""

from __future__ import annotations

import json
from pathlib import Path

from src.core.config import ResolvedModelSelection
from src.domain.director_output import DirectorOutput
from src.domain.prompt_plan_v2 import PromptPlanV2
from src.domain.task import Task
from src.workflows.nodes.prompt_refine_v2 import prompt_refine_v2
from src.workflows.state import WorkflowDependencies


class FailingPlanningProvider:
    """用于验证 mock 模式不应误调用真实规划 provider。"""

    def generate_structured(self, *args, **kwargs):
        raise AssertionError("mock 模式下不应调用规划 provider。")


class FixedPromptPlanProvider:
    """返回固定的 PromptPlanV2，便于验证节点接线和归一化行为。"""

    def __init__(self) -> None:
        self.captured_prompt: str = ""
        self.captured_system_prompt: str = ""

    def generate_structured(self, prompt: str, response_model, *, system_prompt: str | None = None):
        self.captured_prompt = prompt
        self.captured_system_prompt = system_prompt or ""
        return response_model.model_validate(
            {
                "shots": [
                    {
                        "shot_id": "shot_01",
                        "shot_role": "hero",
                        "render_prompt": "高级天猫茶叶 hero 图，整套风格统一，图内融字。",
                        "title_copy": "东方茶礼",
                        "subtitle_copy": "礼盒质感一眼高级",
                        "layout_hint": "顶部留白融字，不遮挡主包装。",
                        "aspect_ratio": "1:1",
                        "image_size": "2K",
                    },
                    {
                        "shot_id": "shot_02",
                        "shot_role": "packaging_feature",
                        "render_prompt": "放大包装细节，保留品牌识别。",
                        "title_copy": "包装细节真的很重要",
                        "subtitle_copy": "包装结构细节清晰可见",
                        "layout_hint": "右上留白，不遮挡标签。",
                        "aspect_ratio": "1:1",
                        "image_size": "2K",
                    },
                    {
                        "shot_id": "shot_03",
                        "shot_role": "dry_leaf_detail",
                        "render_prompt": "强调干茶形态和条索细节。",
                        "title_copy": "条索清晰",
                        "subtitle_copy": "干茶形态细节更直观",
                        "layout_hint": "背景干净区融字。",
                        "aspect_ratio": "1:1",
                        "image_size": "2K",
                    },
                    {
                        "shot_id": "shot_04",
                        "shot_role": "tea_soup",
                        "render_prompt": "展示汤色清透和饮用氛围。",
                        "title_copy": "汤色透亮",
                        "subtitle_copy": "冲泡观感清透有质感",
                        "layout_hint": "上方留白融字。",
                        "aspect_ratio": "1:1",
                        "image_size": "2K",
                    },
                    {
                        "shot_id": "shot_05",
                        "shot_role": "brewed_leaf_detail",
                        "render_prompt": "突出叶底真实细节。",
                        "title_copy": "叶底鲜活",
                        "subtitle_copy": "叶底细节真实可辨识",
                        "layout_hint": "顶部留白，避开叶底主体。",
                        "aspect_ratio": "1:1",
                        "image_size": "2K",
                    },
                    {
                        "shot_id": "shot_06",
                        "shot_role": "gift_scene",
                        "render_prompt": "礼赠场景，高级感，商品主导。",
                        "title_copy": "礼赠有面",
                        "subtitle_copy": "送礼场景更显高级体面",
                        "layout_hint": "左上留白融字。",
                        "aspect_ratio": "1:1",
                        "image_size": "2K",
                    },
                    {
                        "shot_id": "shot_07",
                        "shot_role": "lifestyle",
                        "render_prompt": "日常生活方式场景，保持商品主角。",
                        "title_copy": "日常雅饮",
                        "subtitle_copy": "轻松融入日常饮茶时刻",
                        "layout_hint": "桌面留白区融字。",
                        "aspect_ratio": "1:1",
                        "image_size": "2K",
                    },
                    {
                        "shot_id": "shot_08",
                        "shot_role": "process_or_quality",
                        "render_prompt": "表达品质与工艺可信度。",
                        "title_copy": "工艺把关",
                        "subtitle_copy": "品质卖点表达更可信",
                        "layout_hint": "顶部稳定留白融字。",
                        "aspect_ratio": "1:1",
                        "image_size": "2K",
                    },
                ]
            }
        )


class TmpStorageService:
    """最小临时存储实现，避免测试写入真实 outputs 目录。"""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    def save_json_artifact(self, task_id: str, filename: str, payload: object) -> Path:
        target_dir = self.root_dir / task_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        if hasattr(payload, "model_dump"):
            content = payload.model_dump(mode="json")
        else:
            content = payload
        target.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    def load_cached_json_artifact(self, node_name: str, cache_key: str, response_model):
        del node_name, cache_key, response_model
        return None

    def save_cached_json_artifact(self, node_name: str, cache_key: str, payload: object, *, metadata=None) -> None:
        del node_name, cache_key, payload, metadata


class DummyRenderer:
    pass


class DummyOCRService:
    pass


def test_prompt_refine_v2_writes_provider_output_back_to_state(tmp_path: Path) -> None:
    task = _build_task(tmp_path, task_id="task-prompt-refine-v2-real")
    provider = FixedPromptPlanProvider()
    state = {
        "task": task,
        "director_output": _build_director_output(),
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }
    deps = _build_deps(
        storage=TmpStorageService(tmp_path / "artifacts"),
        planning_provider=provider,
        text_mode="real",
    )

    updates = prompt_refine_v2(state, deps)
    state = {**state, **updates}
    artifact_path = tmp_path / "artifacts" / task.task_id / "prompt_plan_v2.json"

    assert "prompt_plan_v2" in state
    assert isinstance(state["prompt_plan_v2"], PromptPlanV2)
    assert len(state["prompt_plan_v2"].shots) == 8
    assert state["prompt_plan_v2"].shots[0].shot_role == "hero"
    assert state["prompt_plan_v2"].shots[1].title_copy == "细节见真"
    assert artifact_path.exists()
    assert "director_output" in provider.captured_prompt
    assert "PromptPlanV2" in provider.captured_system_prompt
    assert any("[prompt_refine_v2] saved prompt_plan_v2.json" in line for line in state["logs"])


def test_prompt_refine_v2_mock_mode_builds_default_plan(tmp_path: Path) -> None:
    task = _build_task(tmp_path, task_id="task-prompt-refine-v2-mock")
    state = {
        "task": task,
        "director_output": _build_director_output(),
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }
    deps = _build_deps(
        storage=TmpStorageService(tmp_path / "artifacts"),
        planning_provider=FailingPlanningProvider(),
        text_mode="mock",
    )

    result = prompt_refine_v2(state, deps)

    assert len(result["prompt_plan_v2"].shots) == 8
    assert all(shot.render_prompt for shot in result["prompt_plan_v2"].shots)
    assert all(shot.title_copy for shot in result["prompt_plan_v2"].shots)
    assert all(shot.subtitle_copy for shot in result["prompt_plan_v2"].shots)
    assert all(shot.layout_hint for shot in result["prompt_plan_v2"].shots)
    assert any("shot=shot_01 role=hero" in line for line in result["logs"])
    assert "文案融入画面" in result["prompt_plan_v2"].shots[0].render_prompt


def _build_task(tmp_path: Path, *, task_id: str) -> Task:
    """构造 prompt_refine_v2 测试任务。"""
    return Task(
        task_id=task_id,
        brand_name="醒千峰",
        product_name="高山乌龙礼盒",
        category="tea",
        platform="tmall",
        output_size="2048x2048",
        shot_count=8,
        copy_tone="高级礼赠",
        task_dir=str(tmp_path / task_id),
    )


def _build_director_output() -> DirectorOutput:
    """构造最小导演规划输入。"""
    return DirectorOutput.model_validate(
        {
            "product_summary": "高山乌龙礼盒，强调品牌感和礼赠场景。",
            "category": "tea",
            "platform": "tmall",
            "visual_style": "高级克制、统一、转化导向。",
            "shots": [
                {
                    "shot_id": "shot_01",
                    "shot_role": "hero",
                    "objective": "建立第一视觉和品牌记忆。",
                    "audience": "天猫首屏浏览用户。",
                    "selling_points": ["品牌识别", "礼盒质感"],
                    "scene": "高级白底主图场景。",
                    "composition": "主体居中偏下，顶部留白。",
                    "visual_focus": "礼盒正面和品牌名。",
                    "copy_direction": "突出高级感和礼赠体面。",
                    "compliance_notes": ["不要虚构功效。"],
                },
                {
                    "shot_id": "shot_02",
                    "shot_role": "packaging_feature",
                    "objective": "放大包装结构和材质细节。",
                    "audience": "关注包装质感的用户。",
                    "selling_points": ["结构细节", "材质工艺"],
                    "scene": "近景细节场景。",
                    "composition": "标签细节清晰，右侧留白。",
                    "visual_focus": "标签工艺和边缘细节。",
                    "copy_direction": "偏卖点转化。",
                    "compliance_notes": ["不要虚构认证。"],
                },
                {
                    "shot_id": "shot_03",
                    "shot_role": "dry_leaf_detail",
                    "objective": "展示干茶形态。",
                    "audience": "关注干茶品质的用户。",
                    "selling_points": ["干茶条索", "品质感"],
                    "scene": "近景干茶细节场景。",
                    "composition": "干茶主体清晰，背景简洁。",
                    "visual_focus": "干茶条索和色泽。",
                    "copy_direction": "偏品质表达。",
                    "compliance_notes": ["不要做成概念摆拍。"],
                },
                {
                    "shot_id": "shot_04",
                    "shot_role": "tea_soup",
                    "objective": "展示汤色表现。",
                    "audience": "关注冲泡结果的用户。",
                    "selling_points": ["汤色清透", "饮用氛围"],
                    "scene": "克制茶汤场景。",
                    "composition": "杯盏稳定，侧边留白。",
                    "visual_focus": "汤色和杯盏。",
                    "copy_direction": "偏体验表达。",
                    "compliance_notes": ["不要夸大功能。"],
                },
                {
                    "shot_id": "shot_05",
                    "shot_role": "brewed_leaf_detail",
                    "objective": "展示叶底状态。",
                    "audience": "关注真实品质的用户。",
                    "selling_points": ["叶底状态", "真实感"],
                    "scene": "近景叶底细节场景。",
                    "composition": "叶底主体清晰，自然展开。",
                    "visual_focus": "叶底纹理与色泽。",
                    "copy_direction": "偏品质背书。",
                    "compliance_notes": ["不要修成假细节。"],
                },
                {
                    "shot_id": "shot_06",
                    "shot_role": "gift_scene",
                    "objective": "强化礼赠场景价值。",
                    "audience": "送礼用户。",
                    "selling_points": ["礼赠属性", "体面感"],
                    "scene": "克制礼赠场景。",
                    "composition": "主体主导，礼赠元素弱辅助。",
                    "visual_focus": "礼盒与礼赠氛围关系。",
                    "copy_direction": "偏品牌感和礼赠感。",
                    "compliance_notes": ["不要节庆堆砌。"],
                },
                {
                    "shot_id": "shot_07",
                    "shot_role": "lifestyle",
                    "objective": "建立日常饮茶语境。",
                    "audience": "关注生活方式的用户。",
                    "selling_points": ["生活方式", "日常可用性"],
                    "scene": "克制桌面生活方式场景。",
                    "composition": "产品主导，场景真实可用。",
                    "visual_focus": "产品与场景关系。",
                    "copy_direction": "偏品牌感和生活方式。",
                    "compliance_notes": ["不要喧宾夺主。"],
                },
                {
                    "shot_id": "shot_08",
                    "shot_role": "process_or_quality",
                    "objective": "建立品质背书图。",
                    "audience": "需要转化证据的用户。",
                    "selling_points": ["品质背书", "可信度"],
                    "scene": "洁净品质说明场景。",
                    "composition": "主体清晰，给说明文案留白。",
                    "visual_focus": "主体与品质符号组合。",
                    "copy_direction": "偏转化和品质说明。",
                    "compliance_notes": ["不要编造工艺。"],
                },
            ],
        }
    )


def _build_deps(
    *,
    storage: TmpStorageService,
    planning_provider,
    text_mode: str,
) -> WorkflowDependencies:
    """构造 prompt_refine_v2 所需的最小依赖容器。"""
    return WorkflowDependencies(
        storage=storage,
        planning_provider=planning_provider,
        vision_analysis_provider=None,
        image_generation_provider=object(),
        text_renderer=DummyRenderer(),
        ocr_service=DummyOCRService(),
        text_provider_mode=text_mode,
        vision_provider_mode="mock",
        image_provider_mode="mock",
        planning_model_selection=ResolvedModelSelection("planning", "mock", "mock-plan", "mock", "test"),
        vision_model_selection=ResolvedModelSelection("vision", "mock", "mock-vision", "mock", "test"),
        image_model_selection=ResolvedModelSelection("image", "mock", "mock-image", "mock", "test"),
    )
