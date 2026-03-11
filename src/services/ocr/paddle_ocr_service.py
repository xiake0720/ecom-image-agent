from __future__ import annotations

from pathlib import Path


class PaddleOCRService:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def read_text(self, image_path: str) -> list[str]:
        if not self.enabled:
            return []
        # TODO: Plug PaddleOCR runtime here after the MVP skeleton is confirmed.
        return []
