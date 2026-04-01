from __future__ import annotations

from backend.engine.domain.task import Task
from backend.engine.workflows import graph as graph_module
from backend.engine.workflows.state import WorkflowDependencies


class FakeStorage:
    def __init__(self) -> None:
        self.saved_tasks = []

    def save_task_manifest(self, task) -> None:
        self.saved_tasks.append(task)


def test_run_workflow_reports_progress_by_stage(monkeypatch, tmp_path) -> None:
    storage = FakeStorage()

    def _make_node(name: str):
        def _node(state, deps):
            del deps
            if name == "finalize":
                return {"task": state["task"]}
            return {}

        return _node

    monkeypatch.setattr(
        graph_module,
        "NODE_SEQUENCE",
        (
            ("ingest_assets", _make_node("ingest_assets")),
            ("director_v2", _make_node("director_v2")),
            ("prompt_refine_v2", _make_node("prompt_refine_v2")),
            ("render_images", _make_node("render_images")),
            ("run_qc", _make_node("run_qc")),
            ("finalize", _make_node("finalize")),
        ),
    )
    monkeypatch.setattr(
        graph_module,
        "build_dependencies",
        lambda: WorkflowDependencies(
            storage=storage,
            planning_provider=object(),
            image_generation_provider=object(),
            text_renderer=object(),
            text_provider_mode="mock",
            image_provider_mode="mock",
        ),
    )

    progress_updates: list[int] = []
    initial_state = {
        "task": Task(task_id="task-progress", brand_name="品牌", product_name="商品", task_dir=str(tmp_path / "task-progress")),
        "logs": [],
    }

    graph_module.run_workflow(initial_state, on_progress=lambda state: progress_updates.append(state["progress_percent"]))

    deduped = [progress_updates[0]]
    for value in progress_updates[1:]:
        if value != deduped[-1]:
            deduped.append(value)

    assert deduped == [10, 30, 55, 85, 100]
