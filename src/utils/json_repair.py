from __future__ import annotations

import json


def safe_json_loads(raw_text: str) -> dict:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {}

