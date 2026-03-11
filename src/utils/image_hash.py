from __future__ import annotations

import hashlib
from pathlib import Path


def file_sha1(path: str) -> str:
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()

