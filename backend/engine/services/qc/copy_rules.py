from __future__ import annotations


def normalize_copy_length(text: str, max_chars: int = 28) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"

