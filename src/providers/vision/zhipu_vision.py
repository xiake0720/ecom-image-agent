from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from src.core.config import Settings
from src.core.logging import summarize_text
from src.domain.asset import Asset
from src.providers.llm.openai_compatible_text import OpenAICompatibleChatClient
from src.providers.vision.base import BaseVisionAnalysisProvider

logger = logging.getLogger(__name__)

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class ZhipuVisionProvider(BaseVisionAnalysisProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_selection = settings.resolve_vision_model_selection()
        self.last_response_status_code: int | None = None
        self.last_response_metadata: dict[str, Any] = {}

    def generate_structured_from_assets(
        self,
        prompt: str,
        response_model: type[StructuredModel],
        *,
        assets: list[Asset],
        system_prompt: str | None = None,
    ) -> StructuredModel:
        logger.info(
            "开始调用视觉分析模型，provider=Zhipu，mode=%s，模型标签=%s，model=%s，素材数量=%s，schema=%s，prompt摘要=%s",
            self.settings.resolve_vision_provider_route().mode,
            self.model_selection.label,
            self.model_selection.model_id,
            len(assets),
            response_model.__name__,
            summarize_text(prompt, limit=160),
        )
        if self.settings.resolve_vision_provider_route().mode != "real":
            raise RuntimeError("ZhipuVisionProvider cannot run in mock mode.")
        if not self.settings.zhipu_api_key:
            raise RuntimeError("ZHIPU_API_KEY is required when the effective vision provider route uses Zhipu.")
        if not assets:
            raise RuntimeError("At least one uploaded asset is required for vision analysis.")

        client = OpenAICompatibleChatClient(
            provider_name="Zhipu Vision",
            base_url=self.settings.zhipu_base_url,
            api_key=self.settings.zhipu_api_key,
            timeout_seconds=self.settings.provider_timeout_seconds,
        )
        schema = response_model.model_json_schema()
        response = client.create_chat_completion(
            model_id=self.model_selection.model_id,
            messages=self._build_messages(prompt, schema, assets, system_prompt=system_prompt),
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        self.last_response_status_code = response.status_code
        self.last_response_metadata = {
            "provider_name": "zhipu",
            "capability": "vision",
            "model_id": self.model_selection.model_id,
            "status_code": response.status_code,
        }
        elapsed_seconds = getattr(response, "_ecom_elapsed_seconds", None)
        elapsed_text = f"{elapsed_seconds:.2f}" if isinstance(elapsed_seconds, (int, float)) else "unknown"
        if response.status_code >= 400:
            logger.error(
                "视觉分析模型调用失败，provider=Zhipu，model=%s，status_code=%s，elapsed=%ss，response摘要=%s",
                self.model_selection.model_id,
                response.status_code,
                elapsed_text,
                summarize_text(response.text, limit=220),
            )
            raise RuntimeError(
                "Zhipu vision request failed: "
                f"model={self.model_selection.model_id}, "
                f"status_code={response.status_code}, "
                f"elapsed_seconds={elapsed_text}, "
                f"response={response.text[:1200]}"
            )

        data = client.parse_response_json(response, model_id=self.model_selection.model_id)
        content = client.extract_message_content(data, model_id=self.model_selection.model_id)
        try:
            parsed: dict[str, Any] = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Zhipu vision returned non-JSON content: "
                f"model={self.model_selection.model_id}, "
                f"elapsed_seconds={elapsed_text}, "
                f"content={content[:1200]}"
            ) from exc

        result = response_model.model_validate(parsed)
        logger.info(
            "视觉分析模型调用成功，provider=Zhipu，模型标签=%s，model=%s，耗时=%ss",
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
        for asset in assets[:2]:
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
            raise RuntimeError("No readable local assets were found for vision analysis.")

        messages.append({"role": "user", "content": user_parts})
        return messages

    def _guess_mime_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"
