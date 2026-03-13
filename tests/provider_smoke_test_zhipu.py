from __future__ import annotations

import os

import pytest
from pydantic import BaseModel

from src.core.config import Settings
from src.providers.llm.zhipu_text import ZhipuTextProvider


class SmokePayload(BaseModel):
    ok: bool
    provider: str
    model: str


pytestmark = pytest.mark.skipif(
    not os.getenv("ZHIPU_API_KEY"),
    reason="ZHIPU_API_KEY is not configured for smoke testing.",
)


def test_zhipu_provider_smoke() -> None:
    settings = Settings(
        budget_mode="local",
        text_provider_mode="real",
        text_provider="zhipu_glm47_flash",
        text_model="glm-4.7-flash",
    ).with_streamlit_secrets()
    provider = ZhipuTextProvider(settings)

    result = provider.generate_structured(
        'Return exactly {"ok": true, "provider": "zhipu", "model": "glm-4.7-flash"}.',
        SmokePayload,
        system_prompt="You are a smoke test endpoint. Return only the requested JSON object.",
    )

    assert provider.last_response_status_code == 200
    assert provider.last_response_metadata["provider_name"] == "zhipu"
    assert provider.last_response_metadata["model_id"] == "glm-4.7-flash"
    assert result.ok is True
    assert result.provider == "zhipu"
    assert result.model == "glm-4.7-flash"
    assert settings.zhipu_base_url.rstrip("/") == "https://open.bigmodel.cn/api/paas/v4"
