"""NVIDIA 文本 provider。

该模块位于 `src/providers/llm/`，负责封装 NVIDIA NIM 的
OpenAI-compatible chat completions 调用，并将结果校验为指定的
Pydantic 结构化模型。

当前文件只处理“真实文本 provider”的封装，不负责节点编排。
mock / real 的选择由 workflow 依赖注入层决定。
"""

from __future__ import annotations

import json
from typing import Any

import requests

from src.core.config import Settings
from src.providers.llm.base import BaseTextProvider, StructuredModel


class NVIDIATextProvider(BaseTextProvider):
    """通过 NVIDIA NIM 获取结构化文本结果。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate_structured(
        self,
        prompt: str,
        response_model: type[StructuredModel],
        *,
        system_prompt: str | None = None,
    ) -> StructuredModel:
        """调用 NVIDIA NIM 并返回结构化结果。

        Args:
            prompt: 当前节点的用户提示词主体。
            response_model: 期望返回的 Pydantic schema。
            system_prompt: 节点级系统提示词。

        Returns:
            通过 `response_model` 校验后的结构化对象。

        Raises:
            RuntimeError: mock 模式误用、缺失 API key、HTTP 失败、响应格式错误、
                或 JSON 解析失败时显式抛错。
        """
        if self.settings.text_provider_mode == "mock":
            raise RuntimeError("NVIDIATextProvider cannot run in mock mode.")
        if not self.settings.nvidia_api_key:
            raise RuntimeError(
                "ECOM_IMAGE_AGENT_NVIDIA_API_KEY is required when "
                "ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE=real."
            )

        schema = response_model.model_json_schema()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"{prompt}\n\n"
                    # 明确要求 JSON-only，避免 workflow 退化成自由文本解析。
                    "You must return valid JSON only.\n"
                    f"Target JSON schema:\n{json.dumps(schema, ensure_ascii=False)}"
                ),
            }
        )
        payload = {
            "model": self.settings.nvidia_text_model,
            "messages": messages,
            "temperature": 0.2,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        response = requests.post(
            f"{self.settings.nvidia_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.settings.nvidia_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.settings.provider_timeout_seconds,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"NVIDIA text request failed: {response.status_code} {response.text[:800]}"
            )
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected NVIDIA response format: {data}") from exc
        if isinstance(content, list):
            # 个别兼容接口可能返回 content parts，这里统一拼接文本部分。
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        try:
            parsed: dict[str, Any] = json.loads(content)
        except json.JSONDecodeError as exc:
            # 当前项目禁止 silent fallback，解析失败必须直接暴露。
            raise RuntimeError(f"NVIDIA returned non-JSON content: {content[:800]}") from exc
        return response_model.model_validate(parsed)
