"""NVIDIA 视觉商品分析 provider。"""

from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path
from typing import Any, TypeVar

import requests
from pydantic import BaseModel

from src.core.config import Settings
from src.core.logging import describe_proxy_status, summarize_text
from src.domain.asset import Asset
from src.providers.vision.base import BaseVisionAnalysisProvider

logger = logging.getLogger(__name__)

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class NVIDIAVisionProductAnalysisProvider(BaseVisionAnalysisProvider):
    """通过 NVIDIA 多模态模型执行 SKU 级视觉分析。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_selection = settings.resolve_vision_model_selection()

    def generate_structured_from_assets(
        self,
        prompt: str,
        response_model: type[StructuredModel],
        *,
        assets: list[Asset],
        system_prompt: str | None = None,
    ) -> StructuredModel:
        """结合上传商品图返回结构化视觉分析结果。"""
        logger.info(
            "开始调用视觉分析模型，provider=NVIDIA，mode=%s，模型标签=%s，model=%s，素材数量=%s，schema=%s，prompt摘要=%s",
            self.settings.vision_provider_mode,
            self.model_selection.label,
            self.model_selection.model_id,
            len(assets),
            response_model.__name__,
            summarize_text(prompt, limit=160),
        )
        if self.settings.vision_provider_mode == "mock":
            logger.error("调用视觉分析模型失败：当前 provider 模式为 mock，不能使用 NVIDIAVisionProductAnalysisProvider")
            raise RuntimeError("NVIDIAVisionProductAnalysisProvider cannot run in mock mode.")

        api_key = self.settings.nvidia_vision_api_key or self.settings.nvidia_api_key
        if not api_key:
            logger.error("调用视觉分析模型失败：缺少 ECOM_IMAGE_AGENT_NVIDIA_VISION_API_KEY 或 ECOM_IMAGE_AGENT_NVIDIA_API_KEY")
            raise RuntimeError(
                "ECOM_IMAGE_AGENT_NVIDIA_VISION_API_KEY or ECOM_IMAGE_AGENT_NVIDIA_API_KEY "
                "is required when ECOM_IMAGE_AGENT_VISION_PROVIDER_MODE=real."
            )
        if not assets:
            logger.error("调用视觉分析模型失败：至少需要 1 张上传商品图")
            raise RuntimeError("At least one uploaded asset is required for vision analysis.")

        schema = response_model.model_json_schema()
        messages = self._build_messages(prompt, schema, assets, system_prompt=system_prompt)
        payload = {
            "model": self.model_selection.model_id,
            "messages": messages,
            "temperature": 0.1,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        response = self._post_with_retry(payload, api_key=api_key)
        elapsed_seconds = getattr(response, "_ecom_elapsed_seconds", None)
        elapsed_text = f"{elapsed_seconds:.2f}" if isinstance(elapsed_seconds, (int, float)) else "unknown"
        if response.status_code >= 400:
            logger.error(
                "视觉分析模型调用失败：provider=NVIDIA，model=%s，状态码=%s，耗时=%ss，响应摘要=%s",
                self.model_selection.model_id,
                response.status_code,
                elapsed_text,
                summarize_text(response.text, limit=220),
            )
            raise RuntimeError(
                "NVIDIA vision request failed: "
                f"model={self.model_selection.model_id}, "
                f"status_code={response.status_code}, "
                f"elapsed_seconds={elapsed_text}, "
                f"response={response.text[:1200]}"
            )

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.exception(
                "视觉分析模型响应解析失败：provider=NVIDIA，model=%s，耗时=%ss，原因=返回格式不符合预期",
                self.model_selection.model_id,
                elapsed_text,
            )
            raise RuntimeError(
                "Unexpected NVIDIA vision response format: "
                f"model={self.model_selection.model_id}, "
                f"elapsed_seconds={elapsed_text}, "
                f"response={data}"
            ) from exc
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        try:
            parsed: dict[str, Any] = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.exception(
                "视觉分析模型调用失败：provider=NVIDIA，model=%s，耗时=%ss，原因=返回内容不是合法 JSON，内容摘要=%s",
                self.model_selection.model_id,
                elapsed_text,
                summarize_text(content, limit=240),
            )
            raise RuntimeError(
                "NVIDIA vision returned non-JSON content: "
                f"model={self.model_selection.model_id}, "
                f"elapsed_seconds={elapsed_text}, "
                f"content={content[:1200]}"
            ) from exc

        result = response_model.model_validate(parsed)
        logger.info(
            "视觉分析模型调用成功，provider=NVIDIA，模型标签=%s，model=%s，耗时=%ss",
            self.model_selection.label,
            self.model_selection.model_id,
            elapsed_text,
        )
        return result

    def _build_messages(
        self,
        prompt: str,
        schema: dict[str, Any],
        assets: list[Asset],
        *,
        system_prompt: str | None = None,
    ) -> list[dict[str, Any]]:
        """构造多模态 chat completions 请求消息。"""
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        user_parts: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    f"{prompt}\n\n"
                    "You must return valid JSON only.\n"
                    f"Target JSON schema:\n{json.dumps(schema, ensure_ascii=False)}"
                ),
            }
        ]
        attached_count = 0
        for asset in assets:
            path = Path(asset.local_path)
            if not path.exists():
                continue
            mime_type = asset.mime_type or self._guess_mime_type(path)
            image_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
            user_parts.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_b64}",
                    },
                }
            )
            attached_count += 1

        if attached_count == 0:
            logger.error("调用视觉分析模型失败：没有可读取的本地素材文件")
            raise RuntimeError("No readable local assets were found for vision analysis.")

        logger.info("视觉分析请求消息构建完成，附加图片数量=%s", attached_count)
        messages.append({"role": "user", "content": user_parts})
        return messages

    def _post_with_retry(self, payload: dict[str, Any], *, api_key: str) -> requests.Response:
        """执行 NVIDIA 视觉请求，并对网络层失败做一次重试。"""
        url = f"{self.settings.nvidia_vision_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        connect_timeout = 10
        read_timeout = max(int(self.settings.provider_timeout_seconds), 180)
        timeout = (connect_timeout, read_timeout)
        max_attempts = 2
        last_exception: Exception | None = None

        logger.info(
            "准备发送视觉分析请求，provider=NVIDIA，model=%s，base_url=%s，环境变量代理状态=%s，requests_session.trust_env=False，timeout=(connect=%s, read=%s)",
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
                    logger.info("视觉分析请求开始，第 %s/%s 次，provider=NVIDIA，model=%s", attempt, max_attempts, self.model_selection.model_id)
                    response = session.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=timeout,
                    )
                    response._ecom_elapsed_seconds = time.time() - started_at
                    logger.info(
                        "视觉分析请求已返回，第 %s/%s 次，状态码=%s，耗时=%.2fs",
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
                            "视觉分析请求失败：provider=NVIDIA，model=%s，重试已耗尽，耗时=%.2fs，原因=%s",
                            self.model_selection.model_id,
                            elapsed_seconds,
                            exc,
                        )
                        raise RuntimeError(
                            "NVIDIA vision request failed after retry: "
                            f"model={self.model_selection.model_id}, "
                            f"url={url}, "
                            f"attempt={attempt}/{max_attempts}, "
                            f"timeout=(connect={connect_timeout}, read={read_timeout}), "
                            f"elapsed_seconds={elapsed_seconds:.2f}, "
                            f"error={exc}"
                        ) from exc
                    logger.warning(
                        "视觉分析请求异常，准备重试：provider=NVIDIA，model=%s，第 %s/%s 次，耗时=%.2fs，原因=%s",
                        self.model_selection.model_id,
                        attempt,
                        max_attempts,
                        elapsed_seconds,
                        exc,
                    )
                    time.sleep(2)

        if last_exception is not None:
            logger.error(
                "视觉分析请求异常结束：provider=NVIDIA，model=%s，原因=%s",
                self.model_selection.model_id,
                last_exception,
            )
            raise RuntimeError(
                "NVIDIA vision request failed unexpectedly without response: "
                f"model={self.model_selection.model_id}, url={url}, error={last_exception}"
            ) from last_exception
        logger.error("视觉分析请求异常结束：provider=NVIDIA，model=%s，没有响应也没有异常对象", self.model_selection.model_id)
        raise RuntimeError(
            "NVIDIA vision request failed unexpectedly without response or exception."
        )

    def _guess_mime_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"
