from __future__ import annotations

from backend.engine.providers.llm.openai_compatible_text import OpenAICompatibleStructuredTextProvider


class NVIDIATextProvider(OpenAICompatibleStructuredTextProvider):
    provider_key = "nvidia"
    provider_display_name = "NVIDIA"

    def _resolve_api_key(self) -> str | None:
        return self.settings.nvidia_api_key

    def _resolve_base_url(self) -> str:
        return self.settings.nvidia_base_url

    def _missing_api_key_message(self) -> str:
        return "ECOM_IMAGE_AGENT_NVIDIA_API_KEY is required when the effective text provider route uses NVIDIA."
