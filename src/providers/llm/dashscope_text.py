from __future__ import annotations

from typing import Any

from src.providers.llm.openai_compatible_text import (
    OpenAICompatibleStructuredTextProvider,
    StructuredModel,
    build_json_schema_response_format,
)


class DashScopeTextProvider(OpenAICompatibleStructuredTextProvider):
    provider_key = "dashscope"
    provider_display_name = "DashScope"

    def _resolve_api_key(self) -> str | None:
        return self.settings.dashscope_api_key

    def _resolve_base_url(self) -> str:
        return self.settings.dashscope_base_url

    def _missing_api_key_message(self) -> str:
        return "DASHSCOPE_API_KEY is required when the effective text provider route uses DashScope."

    def _build_response_format(
        self,
        *,
        schema: dict[str, Any],
        response_model: type[StructuredModel],
    ) -> dict[str, Any]:
        return build_json_schema_response_format(schema_name=response_model.__name__, schema=schema)

    def _build_extra_body(self) -> dict[str, Any]:
        return {"enable_thinking": False}
