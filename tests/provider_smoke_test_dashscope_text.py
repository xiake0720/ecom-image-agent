from __future__ import annotations

import os

import pytest
from pydantic import BaseModel

from src.core.config import Settings
from src.providers.llm.dashscope_text import DashScopeTextProvider


class SmokePayload(BaseModel):
    ok: bool


pytestmark = pytest.mark.skipif(
    not os.getenv("DASHSCOPE_API_KEY"),
    reason="DASHSCOPE_API_KEY is not configured for DashScope smoke testing.",
)


def test_dashscope_text_provider_smoke() -> None:
    settings = Settings(
        text_provider_mode="real",
        text_provider="dashscope",
        text_model="qwen-plus",
    ).with_streamlit_secrets()
    provider = DashScopeTextProvider(settings)

    result = provider.generate_structured(
        'Return exactly {"ok": true}.',
        SmokePayload,
        system_prompt="You are a smoke test endpoint. Return valid JSON only.",
    )

    assert provider.last_response_status_code == 200
    assert provider.last_response_metadata["provider_name"] == "dashscope"
    assert provider.last_response_metadata["model_id"] == "qwen-plus"
    assert provider.last_response_metadata["capability"] == "text"
    assert result.ok is True
