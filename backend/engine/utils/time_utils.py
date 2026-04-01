from __future__ import annotations

from datetime import datetime


def utc_timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d%H%M%S")

