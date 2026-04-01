"""RunAPI OpenAI 兼容文本 provider。

该模块位于 `src/providers/llm/`，负责在不引入新抽象的前提下，
复用现有 OpenAI 兼容 chat completions 封装，接入 RunAPI 的文本能力。

当前职责：
- 为 v2 预留 `gpt-5-nano` 结构化输出能力
- 兼容后续可能需要的普通文本输出场景
- 统一复用 `Settings` 中的 RunAPI 文本配置与共享 API Key 兜底逻辑
"""

from __future__ import annotations

import logging

from backend.engine.core.logging import summarize_text
from backend.engine.providers.llm.openai_compatible_text import (
    OpenAICompatibleChatClient,
    OpenAICompatibleStructuredTextProvider,
)

logger = logging.getLogger(__name__)


class RunApiOpenAITextProvider(OpenAICompatibleStructuredTextProvider):
    """基于 RunAPI OpenAI 兼容接口的文本 provider。"""

    provider_key = "runapi_openai"
    provider_display_name = "RunAPI OpenAI"

    def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        """为后续普通文本节点预留直接文本输出接口。"""
        logger.info(
            "开始调用普通文本输出，provider=%s，model=%s，prompt摘要=%s",
            self.provider_display_name,
            self.model_selection.model_id,
            summarize_text(prompt, limit=120),
        )
        if self._resolve_route_mode() != "real":
            raise RuntimeError(f"{self.provider_display_name} text provider cannot run in mock mode.")

        api_key = self._resolve_api_key()
        if not api_key:
            raise RuntimeError(self._missing_api_key_message())

        client = OpenAICompatibleChatClient(
            provider_name=self.provider_display_name,
            base_url=self._resolve_base_url(),
            api_key=api_key,
            timeout_seconds=self.settings.provider_timeout_seconds,
        )
        response = client.create_chat_completion(
            model_id=self.model_selection.model_id,
            messages=self._build_text_messages(prompt, system_prompt=system_prompt),
            temperature=temperature,
        )
        self.last_response_status_code = response.status_code
        self.last_response_metadata = {
            "provider_name": self.provider_key,
            "model_id": self.model_selection.model_id,
            "capability": "text_plain",
            "status_code": response.status_code,
        }
        elapsed_seconds = getattr(response, "_ecom_elapsed_seconds", None)
        elapsed_text = f"{elapsed_seconds:.2f}" if isinstance(elapsed_seconds, (int, float)) else "unknown"
        if response.status_code >= 400:
            raise RuntimeError(
                f"{self.provider_display_name} text request failed: "
                f"model={self.model_selection.model_id}, status_code={response.status_code}, "
                f"elapsed_seconds={elapsed_text}, response={summarize_text(response.text, limit=800)}"
            )

        data = client.parse_response_json(response, model_id=self.model_selection.model_id)
        content = client.extract_message_content(data, model_id=self.model_selection.model_id).strip()
        logger.info(
            "普通文本输出调用成功，provider=%s，model=%s，elapsed_seconds=%s",
            self.provider_display_name,
            self.model_selection.model_id,
            elapsed_text,
        )
        return content

    def _build_text_messages(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> list[dict[str, str]]:
        """构建普通文本调用所需的消息列表。"""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _resolve_api_key(self) -> str | None:
        """优先使用文本专属 API Key，缺失时回退到共享 RunAPI Key。"""
        return self.settings.runapi_text_api_key or self.settings.runapi_api_key

    def _resolve_base_url(self) -> str:
        """返回 RunAPI OpenAI 兼容文本接口的基地址。"""
        return self.settings.runapi_text_base_url

    def _missing_api_key_message(self) -> str:
        """返回缺失 API Key 时的显式错误信息。"""
        return (
            "ECOM_IMAGE_AGENT_RUNAPI_TEXT_API_KEY or ECOM_IMAGE_AGENT_RUNAPI_API_KEY "
            "is required when the effective text provider route uses RunAPI OpenAI."
        )
