from __future__ import annotations

from backend.engine.providers.llm.openai_compatible_text import OpenAICompatibleStructuredTextProvider


class ZhipuTextProvider(OpenAICompatibleStructuredTextProvider):
    provider_key = "zhipu"
    provider_display_name = "Zhipu"

    def _resolve_api_key(self) -> str | None:
        return self.settings.zhipu_api_key

    def _resolve_base_url(self) -> str:
        return self.settings.zhipu_base_url

    def _missing_api_key_message(self) -> str:
        return "ZHIPU_API_KEY is required when the effective text provider route uses Zhipu."
