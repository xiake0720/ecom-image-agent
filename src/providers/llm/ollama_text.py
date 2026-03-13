"""Ollama 文本 provider。

当前文件只接 Ollama 本地结构化文本能力，不改 workflow 节点逻辑。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests

from src.core.config import Settings
from src.core.logging import summarize_text
from src.providers.llm.base import BaseTextProvider, StructuredModel

logger = logging.getLogger(__name__)


class OllamaTextProvider(BaseTextProvider):
    """通过 Ollama 本地接口获取结构化文本结果。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_selection = settings.resolve_text_model_selection()

    def generate_structured(
        self,
        prompt: str,
        response_model: type[StructuredModel],
        *,
        system_prompt: str | None = None,
    ) -> StructuredModel:
        logger.info(
            "开始调用文本模型，provider=Ollama，mode=%s，model=%s，schema=%s，prompt摘要=%s",
            self.settings.resolve_text_provider_route().mode,
            self.model_selection.model_id,
            response_model.__name__,
            summarize_text(prompt, limit=120),
        )
        if self.settings.resolve_text_provider_route().mode != "real":
            raise RuntimeError("OllamaTextProvider cannot run when effective text provider mode is mock.")

        schema = response_model.model_json_schema()
        payload = {
            "model": self.model_selection.model_id,
            "stream": False,
            "format": schema,
            "messages": self._build_messages(prompt, schema, system_prompt=system_prompt),
            "options": {
                "temperature": 0.2,
            },
        }
        url = f"{self.settings.ollama_base_url.rstrip('/')}/api/chat"
        started_at = time.time()
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.settings.provider_timeout_seconds,
            )
        except requests.RequestException as exc:
            logger.exception("Ollama 文本请求失败，url=%s，错误=%s", url, exc)
            raise RuntimeError(f"Ollama text request failed: url={url}, error={exc}") from exc

        if response.status_code >= 400:
            logger.error(
                "Ollama 文本请求失败，状态码=%s，耗时=%.2fs，响应摘要=%s",
                response.status_code,
                time.time() - started_at,
                summarize_text(response.text, limit=200),
            )
            raise RuntimeError(f"Ollama text request failed: {response.status_code} {response.text[:800]}")

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Ollama text response is not valid JSON: {response.text[:800]}") from exc

        content = data.get("message", {}).get("content", "")
        try:
            parsed: dict[str, Any] = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Ollama returned non-JSON content: {content[:800]}") from exc

        result = response_model.model_validate(parsed)
        logger.info(
            "Ollama 文本请求成功，model=%s，耗时=%.2fs",
            self.model_selection.model_id,
            time.time() - started_at,
        )
        return result

    def _build_messages(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        system_prompt: str | None = None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"{prompt}\n\n"
                    "You must return valid JSON only.\n"
                    f"Target JSON schema:\n{json.dumps(schema, ensure_ascii=False)}"
                ),
            }
        )
        return messages
