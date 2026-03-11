from __future__ import annotations

from src.domain.qc_report import QCReport
from src.services.qc.image_qc import build_dimension_check
from src.services.qc.ocr_qc import build_ocr_check
from src.workflows.state import WorkflowDependencies, WorkflowState


def run_qc(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    checks = []
    copy_map = {item.shot_id: item for item in state["copy_plan"].items}
    for image in state["generation_result"].images:
        checks.append(build_dimension_check(image))
        checks.append(build_ocr_check(deps.ocr_service, image.image_path, copy_map[image.shot_id]))
    passed = all(check.passed for check in checks)
    report = QCReport(passed=passed, review_required=not passed, checks=checks)
    deps.storage.save_json_artifact(state["task"].task_id, "qc_report.json", report)
    return {"qc_report": report, "logs": [*state.get("logs", []), "Completed QC checks."]}

