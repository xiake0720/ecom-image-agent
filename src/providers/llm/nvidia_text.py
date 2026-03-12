"""NVIDIA 文本 provider。

该模块位于 `src/providers/llm/`，负责封装 NVIDIA NIM 的
OpenAI-compatible chat completions 调用，并将结果校验为指定的
Pydantic 结构化模型。

当前文件只处理“真实文本 provider”的封装，不负责节点编排。
mock / real 的选择由 workflow 依赖注入层决定。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests

from src.core.config import Settings
from src.core.logging import describe_proxy_status, summarize_text
from src.providers.llm.base import BaseTextProvider, StructuredModel

logger = logging.getLogger(__name__)


class NVIDIATextProvider(BaseTextProvider):
    """通过 NVIDIA NIM 获取结构化文本结果。"""

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
        logger.info(
            "开始调用文本模型，provider=NVIDIA，mode=%s，模型标签=%s，model=%s，schema=%s，prompt摘要=%s",
            self.settings.text_provider_mode,
            self.model_selection.label,
            self.model_selection.model_id,
            response_model.__name__,
            summarize_text(prompt, limit=120),
        )
        if self.settings.text_provider_mode == "mock":
            logger.error("调用文本模型失败：当前 provider 模式为 mock，不能使用 NVIDIATextProvider")
            raise RuntimeError("NVIDIATextProvider cannot run in mock mode.")
        if not self.settings.nvidia_api_key:
            logger.error("调用文本模型失败：缺少 ECOM_IMAGE_AGENT_NVIDIA_API_KEY")
            raise RuntimeError(
                "ECOM_IMAGE_AGENT_NVIDIA_API_KEY is required when "
                "ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE=real."
            )

        schema = response_model.model_json_schema()
        messages = self._build_messages(prompt, schema, system_prompt=system_prompt)
        payload = {
            "model": self.model_selection.model_id,
            "messages": messages,
            "temperature": 0.2,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        response = self._post_with_retry(payload)
        elapsed_seconds = getattr(response, "_ecom_elapsed_seconds", None)
        elapsed_text = f"{elapsed_seconds:.2f}" if isinstance(elapsed_seconds, (int, float)) else "unknown"
        if response.status_code >= 400:
            logger.error(
                "文本模型调用失败：provider=NVIDIA，model=%s，状态码=%s，耗时=%ss，响应摘要=%s",
                self.model_selection.model_id,
                response.status_code,
                elapsed_text,
                summarize_text(response.text, limit=200),
            )
            raise RuntimeError(
                "NVIDIA text request failed: "
                f"model={self.model_selection.model_id}, "
                f"status_code={response.status_code}, "
                f"elapsed_seconds={elapsed_text}, "
                f"response={response.text[:800]}"
            )
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.exception(
                "文本模型响应解析失败：provider=NVIDIA，model=%s，耗时=%ss，原因=返回格式不符合预期",
                self.model_selection.model_id,
                elapsed_text,
            )
            raise RuntimeError(
                "Unexpected NVIDIA response format: "
                f"model={self.model_selection.model_id}, "
                f"elapsed_seconds={elapsed_text}, "
                f"response={data}"
            ) from exc
        if isinstance(content, list):
            # 个别兼容接口可能返回 content parts，这里统一拼接文本部分。
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        try:
            parsed: dict[str, Any] = json.loads(content)
        except json.JSONDecodeError as exc:
            # 当前项目禁止 silent fallback，解析失败必须直接暴露。
            logger.exception(
                "文本模型调用失败：provider=NVIDIA，model=%s，耗时=%ss，原因=返回内容不是合法 JSON，内容摘要=%s",
                self.model_selection.model_id,
                elapsed_text,
                summarize_text(content, limit=200),
            )
            raise RuntimeError(
                "NVIDIA returned non-JSON content: "
                f"model={self.model_selection.model_id}, "
                f"elapsed_seconds={elapsed_text}, "
                f"content={content[:800]}"
            ) from exc
        result = response_model.model_validate(parsed)
        logger.info(
            "文本模型调用成功，provider=NVIDIA，模型标签=%s，model=%s，耗时=%ss",
            self.model_selection.label,
            self.model_selection.model_id,
            elapsed_text,
        )
        return result

    def _build_messages(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        system_prompt: str | None = None,
    ) -> list[dict[str, str]]:
        """构造 chat completions 请求消息。"""
        messages: list[dict[str, str]] = []
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
        return messages

    def _post_with_retry(self, payload: dict[str, Any]) -> requests.Response:
        """执行 NVIDIA 请求，并对网络层超时/连接失败做一次重试。"""
        url = f"{self.settings.nvidia_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.nvidia_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        connect_timeout = 10
        read_timeout = max(int(self.settings.provider_timeout_seconds), 180)
        timeout = (connect_timeout, read_timeout)
        max_attempts = 2
        last_exception: Exception | None = None

        logger.info(
            "准备发送文本模型请求，provider=NVIDIA，model=%s，base_url=%s，环境变量代理状态=%s，requests_session.trust_env=False，timeout=(connect=%s, read=%s)",
            self.model_selection.model_id,
            url,
            describe_proxy_status(),
            connect_timeout,
            read_timeout,
        )
        with requests.Session() as session:
            session.trust_env = False
            for attempt in range(1, max_attempts + 1):
                started_at = time.time()
                try:
                    logger.info("文本模型请求开始，第 %s/%s 次，provider=NVIDIA，model=%s", attempt, max_attempts, self.model_selection.model_id)
                    response = session.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=timeout,
                    )
                    response._ecom_elapsed_seconds = time.time() - started_at
                    logger.info(
                        "文本模型请求已返回，第 %s/%s 次，状态码=%s，耗时=%.2fs",
                        attempt,
                        max_attempts,
                        response.status_code,
                        response._ecom_elapsed_seconds,
                    )
                    return response
                except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as exc:
                    elapsed_seconds = time.time() - started_at
                    last_exception = exc
                    if attempt >= max_attempts:
                        logger.exception(
                        "文本模型请求失败：provider=NVIDIA，model=%s，重试已耗尽，耗时=%.2fs，原因=%s",
                        self.model_selection.model_id,
                        elapsed_seconds,
                        exc,
                    )
                    raise RuntimeError(
                        "NVIDIA text request failed after retry: "
                        f"model={self.model_selection.model_id}, "
                        f"url={url}, "
                        f"attempt={attempt}/{max_attempts}, "
                            f"timeout=(connect={connect_timeout}, read={read_timeout}), "
                            f"elapsed_seconds={elapsed_seconds:.2f}, "
                            f"error={exc}"
                        ) from exc
                    logger.warning(
                        "文本模型请求异常，准备重试：provider=NVIDIA，model=%s，第 %s/%s 次，耗时=%.2fs，原因=%s",
                        self.model_selection.model_id,
                        attempt,
                        max_attempts,
                        elapsed_seconds,
                        exc,
                    )
                    time.sleep(2)

        if last_exception is not None:
            logger.error(
                "文本模型请求异常结束：provider=NVIDIA，model=%s，原因=%s",
                self.model_selection.model_id,
                last_exception,
            )
            raise RuntimeError(
                "NVIDIA text request failed unexpectedly without response: "
                f"model={self.model_selection.model_id}, url={url}, error={last_exception}"
            ) from last_exception
        logger.error("文本模型请求异常结束：provider=NVIDIA，model=%s，没有响应也没有异常对象", self.model_selection.model_id)
        raise RuntimeError(
            "NVIDIA text request failed unexpectedly without response or exception."
        )
