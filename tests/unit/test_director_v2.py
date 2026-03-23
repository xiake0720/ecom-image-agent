"""director_v2 节点最小回归测试。"""

from __future__ import annotations

import json
from pathlib import Path

from src.core.config import ResolvedModelSelection
from src.domain.asset import Asset, AssetType
from src.domain.director_output import DirectorOutput
from src.domain.task import Task
from src.workflows.nodes.director_v2 import director_v2
from src.workflows.state import WorkflowDependencies


class FailingPlanningProvider:
    """用于验证 mock 模式不应误调用真实规划 provider。"""

    def generate_structured(self, *args, **kwargs):
        raise AssertionError("mock 模式下不应调用规划 provider。")


class FixedDirectorPlanningProvider:
    """返回固定导演输出，便于验证节点接线和落盘。"""

    def __init__(self) -> None:
        self.captured_prompt: str = ""
        self.captured_system_prompt: str = ""

    def generate_structured(self, prompt: str, response_model, *, system_prompt: str | None = None):
        self.captured_prompt = prompt
        self.captured_system_prompt = system_prompt or ""
        return response_model.model_validate(
            {
                "product_summary": "白金高山乌龙礼盒，强调礼赠体面与天猫首屏转化。",
                "category": "tea",
                "platform": "tmall",
                "visual_style": "高级克制、商业感强、整套统一。",
                "shots": [
                    {
                        "shot_id": "shot_01",
                        "shot_role": "hero",
                        "objective": "建立第一视觉与品牌记忆。",
                        "audience": "天猫首屏浏览用户。",
                        "selling_points": ["品牌识别", "礼盒质感"],
                        "scene": "高级白底主图场景。",
                        "composition": "主体居中偏下，顶部留白。",
                        "visual_focus": "礼盒正面、品牌名、整体轮廓。",
                        "copy_direction": "突出高级感与礼赠体面。",
                        "compliance_notes": ["不要虚构功效。"],
                    },
                    {
                        "shot_id": "shot_02",
                        "shot_role": "packaging_feature",
                        "objective": "放大包装结构与材质卖点。",
                        "audience": "关注包装质感的用户。",
                        "selling_points": ["结构细节", "材质工艺"],
                        "scene": "近景包装细节场景。",
                        "composition": "集中展示标签与材质，右侧留白。",
                        "visual_focus": "标签细节、边缘工艺。",
                        "copy_direction": "偏卖点转化。",
                        "compliance_notes": ["不要虚构认证。"],
                    },
                    {
                        "shot_id": "shot_03",
                        "shot_role": "dry_leaf_detail",
                        "objective": "展示干茶形态。",
                        "audience": "关注茶叶品质的用户。",
                        "selling_points": ["干茶条索", "品质感"],
                        "scene": "近景干茶细节场景。",
                        "composition": "干茶主体清楚，背景简洁。",
                        "visual_focus": "干茶条索与色泽。",
                        "copy_direction": "偏品质表达。",
                        "compliance_notes": ["不要做成概念摆拍。"],
                    },
                    {
                        "shot_id": "shot_04",
                        "shot_role": "tea_soup",
                        "objective": "展示茶汤表现。",
                        "audience": "关注冲泡结果的用户。",
                        "selling_points": ["汤色清透", "饮用氛围"],
                        "scene": "杯盏克制的茶汤场景。",
                        "composition": "杯盏稳定，侧方留白。",
                        "visual_focus": "茶汤颜色与杯盏。",
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
                        "composition": "叶底主体清楚，自然展开。",
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
                        "composition": "主体清楚，给说明文案留白。",
                        "visual_focus": "主体与品质符号组合。",
                        "copy_direction": "偏转化和品质说明。",
                        "compliance_notes": ["不要编造工艺。"],
                    },
                ],
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


def test_director_v2_writes_provider_output_back_to_state(tmp_path: Path) -> None:
    task = _build_task(tmp_path, task_id="task-director-v2-real")
    provider = FixedDirectorPlanningProvider()
    state = {
        "task": task,
        "assets": _build_assets(tmp_path),
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }
    deps = _build_deps(
        storage=TmpStorageService(tmp_path / "artifacts"),
        planning_provider=provider,
        text_mode="real",
    )

    updates = director_v2(state, deps)
    state = {**state, **updates}
    artifact_path = tmp_path / "artifacts" / task.task_id / "director_output.json"

    assert "director_output" in state
    assert isinstance(state["director_output"], DirectorOutput)
    assert len(state["director_output"].shots) == 8
    assert state["director_output"].shots[0].shot_role == "hero"
    assert state["director_output"].shots[-1].shot_role == "process_or_quality"
    assert artifact_path.exists()
    assert "shot_role_template" in provider.captured_prompt
    assert "DirectorOutput" in provider.captured_system_prompt
    assert any("[director_v2] saved director_output.json" in line for line in state["logs"])


def test_director_v2_mock_mode_builds_default_eight_shot_plan(tmp_path: Path) -> None:
    task = _build_task(tmp_path, task_id="task-director-v2-mock")
    state = {
        "task": task,
        "assets": _build_assets(tmp_path),
        "logs": [],
        "cache_enabled": False,
        "ignore_cache": False,
    }
    deps = _build_deps(
        storage=TmpStorageService(tmp_path / "artifacts"),
        planning_provider=FailingPlanningProvider(),
        text_mode="mock",
    )

    result = director_v2(state, deps)
    shot_roles = [shot.shot_role for shot in result["director_output"].shots]

    assert len(result["director_output"].shots) == 8
    assert shot_roles == [
        "hero",
        "packaging_feature",
        "dry_leaf_detail",
        "tea_soup",
        "brewed_leaf_detail",
        "gift_scene",
        "lifestyle",
        "process_or_quality",
    ]
    assert result["director_output"].platform == "tmall"
    assert any("selected_reference_asset_ids=['asset-01', 'asset-02']" in line for line in result["logs"])
    assert any("shot_roles=['hero', 'packaging_feature', 'dry_leaf_detail', 'tea_soup', 'brewed_leaf_detail', 'gift_scene', 'lifestyle', 'process_or_quality']" in line for line in result["logs"])


def _build_task(tmp_path: Path, *, task_id: str) -> Task:
    """构造 director_v2 测试任务。"""
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


def _build_assets(tmp_path: Path) -> list[Asset]:
    """构造主图和细节图元数据。"""
    return [
        Asset(
            asset_id="asset-01",
            filename="hero_main_packshot.png",
            local_path=str(tmp_path / "hero_main_packshot.png"),
            asset_type=AssetType.PRODUCT,
            width=2048,
            height=2048,
            tags=["packshot", "front"],
        ),
        Asset(
            asset_id="asset-02",
            filename="label_detail_open_box.png",
            local_path=str(tmp_path / "label_detail_open_box.png"),
            asset_type=AssetType.DETAIL,
            width=1600,
            height=1600,
            tags=["detail", "label", "structure"],
        ),
    ]


def _build_deps(
    *,
    storage: TmpStorageService,
    planning_provider,
    text_mode: str,
) -> WorkflowDependencies:
    """构造 director_v2 所需的最小依赖容器。"""
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
