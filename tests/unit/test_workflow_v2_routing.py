from __future__ import annotations

from pathlib import Path

from src.domain.task import Task
from src.ui.pages import home as home_module
from src.ui.pages import task_form as task_form_module
from src.workflows import graph as graph_module
from src.workflows.state import WorkflowDependencies


class _FakeUpload:
    """模拟 Streamlit 上传对象，仅提供 `name` 和 `getvalue()`。"""

    def __init__(self, name: str, content: bytes) -> None:
        self.name = name
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


class _FakeWorkflow:
    """记录 home._run_task 传入的初始 state。"""

    def __init__(self) -> None:
        self.last_state: dict | None = None

    def invoke(self, state: dict) -> dict:
        self.last_state = dict(state)
        return {
            **state,
            "logs": [*state.get("logs", []), "[fake_workflow] completed"],
        }


class _FakeStorage:
    """最小存储桩，用于验证 home 层的入参与 task 落盘。"""

    def __init__(self, task_dir: Path) -> None:
        self.task_dir = task_dir
        self.saved_task = None

    def create_task_id(self) -> str:
        return "task-home-v2"

    def save_task_manifest(self, task) -> None:
        self.saved_task = task

    def save_uploads(self, task_id: str, uploads_payload) -> list:
        del task_id
        assets = []
        for index, (filename, content) in enumerate(uploads_payload, start=1):
            asset_path = self.task_dir / "inputs" / filename
            asset_path.parent.mkdir(parents=True, exist_ok=True)
            asset_path.write_bytes(content)
            assets.append(
                {
                    "asset_id": f"asset-{index:02d}",
                    "filename": filename,
                    "local_path": str(asset_path),
                }
            )
        return assets


class _FakeExpander:
    """兼容 `with st.expander(...)` 语法的空上下文。"""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeStreamlit:
    """返回默认值，便于验证 task_form 的 v2 默认项。"""

    def text_input(self, label, value=""):
        del label
        return value

    def selectbox(self, label, options, index=0, help=None):
        del label, help
        return options[index]

    def slider(self, label, min_value, max_value, value):
        del label, min_value, max_value
        return value

    def checkbox(self, label, value=False, help=None):
        del label, help
        return value

    def caption(self, text):
        del text

    def warning(self, text):
        del text

    def info(self, text):
        del text

    def expander(self, label, expanded=False):
        del label, expanded
        return _FakeExpander()


def _build_dummy_deps() -> WorkflowDependencies:
    """为 graph 测试构造最小依赖，避免触发真实 provider 初始化。"""
    return WorkflowDependencies(
        storage=object(),
        planning_provider=object(),
        vision_analysis_provider=None,
        image_generation_provider=object(),
        text_renderer=object(),
        ocr_service=object(),
        text_provider_mode="mock",
        vision_provider_mode="mock",
        image_provider_mode="mock",
    )


def _make_node(node_name: str):
    """构造最小 workflow 节点，记录执行路径。"""

    def _node(state, deps):
        del deps
        return {
            "logs": [*state.get("logs", []), f"[test_route] {node_name}"],
        }

    return _node


def _build_task(task_id: str, task_dir: Path) -> Task:
    """构造 graph/home 测试复用的最小任务对象。"""
    return Task(
        task_id=task_id,
        brand_name="品牌A",
        product_name="凤凰单丛",
        platform="tmall",
        output_size="1440x1440",
        shot_count=8,
        copy_tone="专业自然",
        workflow_version="v2",
        enable_overlay_fallback=True,
        task_dir=str(task_dir),
    )


def test_build_workflow_routes_v1_and_v2_to_different_chains(monkeypatch, tmp_path: Path) -> None:
    """验证动态 workflow 会根据 workflow_version 分流到不同主链。"""
    graph_module.build_workflow.cache_clear()
    graph_module.build_workflow_v1.cache_clear()
    graph_module.build_workflow_v2.cache_clear()
    monkeypatch.setattr(graph_module, "build_dependencies", _build_dummy_deps)
    monkeypatch.setattr(graph_module, "ingest_assets", _make_node("ingest_assets"))
    monkeypatch.setattr(graph_module, "analyze_product", _make_node("analyze_product"))
    monkeypatch.setattr(graph_module, "style_director", _make_node("style_director"))
    monkeypatch.setattr(graph_module, "plan_shots", _make_node("plan_shots"))
    monkeypatch.setattr(graph_module, "generate_copy", _make_node("generate_copy"))
    monkeypatch.setattr(graph_module, "generate_layout", _make_node("generate_layout"))
    monkeypatch.setattr(graph_module, "shot_prompt_refiner", _make_node("shot_prompt_refiner"))
    monkeypatch.setattr(graph_module, "build_prompts", _make_node("build_prompts"))
    monkeypatch.setattr(graph_module, "director_v2", _make_node("director_v2"))
    monkeypatch.setattr(graph_module, "prompt_refine_v2", _make_node("prompt_refine_v2"))
    monkeypatch.setattr(graph_module, "render_images", _make_node("render_images"))
    monkeypatch.setattr(graph_module, "overlay_text", _make_node("overlay_text"))
    monkeypatch.setattr(graph_module, "run_qc", _make_node("run_qc"))
    monkeypatch.setattr(graph_module, "finalize", _make_node("finalize"))

    workflow = graph_module.build_workflow()
    v1_state = workflow.invoke({"task": _build_task("task-v1", tmp_path / "task-v1"), "workflow_version": "v1", "logs": []})
    v2_state = workflow.invoke({"task": _build_task("task-v2", tmp_path / "task-v2"), "workflow_version": "v2", "logs": []})

    assert any("[test_route] analyze_product" in log for log in v1_state["logs"])
    assert not any("[test_route] director_v2" in log for log in v1_state["logs"])
    assert any("[test_route] director_v2" in log for log in v2_state["logs"])
    assert not any("[test_route] analyze_product" in log for log in v2_state["logs"])
    assert any("[test_route] prompt_refine_v2" in log for log in v2_state["logs"])


def test_render_task_form_uses_v2_defaults(monkeypatch) -> None:
    """验证 task_form 默认值已切到 v2、tmall、8 张图和 overlay fallback。"""
    monkeypatch.setattr(task_form_module, "st", _FakeStreamlit())

    form_data = task_form_module.render_task_form()

    assert form_data["platform"] == "tmall"
    assert form_data["shot_count"] == 8
    assert form_data["workflow_version"] == "v2"
    assert form_data["enable_overlay_fallback"] is True


def test_home_run_task_passes_v2_flags_into_workflow(monkeypatch, tmp_path: Path) -> None:
    """验证 home 提交任务时，会把 v2 开关写入 task 和初始 state。"""
    task_dir = tmp_path / "task-home-v2"
    fake_storage = _FakeStorage(task_dir)
    fake_workflow = _FakeWorkflow()

    monkeypatch.setattr(home_module, "LocalStorageService", lambda: fake_storage)
    monkeypatch.setattr(home_module, "ensure_task_dirs", lambda task_id: {"task": task_dir})
    monkeypatch.setattr(home_module, "attach_task_file_handler", lambda task_id, task_dir, settings=None: task_dir / "task.log")
    monkeypatch.setattr(home_module, "detach_task_file_handler", lambda task_id: None)
    monkeypatch.setattr(home_module, "initialize_logging", lambda settings: None)
    monkeypatch.setattr(home_module, "build_workflow", lambda: fake_workflow)
    monkeypatch.setattr(home_module, "_build_debug_info", lambda task, settings, task_log_path: {"task_id": task.task_id})

    result = home_module._run_task(
        {
            "brand_name": "品牌A",
            "product_name": "凤凰单丛",
            "platform": "tmall",
            "output_size": "1440x1440",
            "shot_count": 8,
            "copy_tone": "专业自然",
            "workflow_version": "v2",
            "enable_overlay_fallback": True,
            "cache_enabled": True,
            "ignore_cache": False,
            "prompt_build_mode": "per_shot",
            "analyze_max_reference_images": 2,
            "render_max_reference_images": 2,
        },
        [_FakeUpload("product.png", b"demo-image")],
        forced_render_mode="full_auto",
    )

    assert fake_storage.saved_task.workflow_version == "v2"
    assert fake_storage.saved_task.enable_overlay_fallback is True
    assert fake_workflow.last_state is not None
    assert fake_workflow.last_state["workflow_version"] == "v2"
    assert fake_workflow.last_state["enable_overlay_fallback"] is True
    assert fake_workflow.last_state["direct_text_on_image"] is True
    assert result["task"]["workflow_version"] == "v2"
    assert result["task"]["enable_overlay_fallback"] is True
