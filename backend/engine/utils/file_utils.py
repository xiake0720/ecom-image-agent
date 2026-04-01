from __future__ import annotations

from pathlib import Path


def ensure_parent(path: str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target

