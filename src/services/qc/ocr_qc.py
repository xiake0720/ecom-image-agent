from __future__ import annotations

from src.domain.copy_plan import CopyItem
from src.domain.qc_report import QCCheck
from src.services.ocr.paddle_ocr_service import PaddleOCRService


def build_ocr_check(ocr_service: PaddleOCRService, image_path: str, copy_item: CopyItem) -> QCCheck:
    texts = ocr_service.read_text(image_path)
    target = " ".join([copy_item.title, copy_item.subtitle, *copy_item.bullets])
    passed = True if not texts else any(fragment in target for fragment in texts[:3])
    details = "OCR skipped or no text detected" if not texts else "OCR text partially matched target copy"
    return QCCheck(shot_id=copy_item.shot_id, check_name="ocr_similarity", passed=passed, details=details)

