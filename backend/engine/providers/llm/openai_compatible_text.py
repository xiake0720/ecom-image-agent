from __future__ import annotations

from abc import ABC, abstractmethod
import json
import logging
import time
from typing import Any

from pydantic import ValidationError
import requests

from backend.engine.core.config import Settings
from backend.engine.core.logging import describe_proxy_status, summarize_text
from backend.core.logging import format_log_event
from backend.engine.domain.usage import ProviderUsageSnapshot, normalize_usage_snapshot
from backend.engine.providers.llm.base import BaseTextProvider, StructuredModel

logger = logging.getLogger(__name__)


def build_json_schema_response_format(*, schema_name: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema_name,
            "schema": schema,
        },
    }


def extract_json_candidate(raw_text: str) -> str | None:
    start_positions = [pos for pos in (raw_text.find("{"), raw_text.find("[")) if pos >= 0]
    if not start_positions:
        return None
    start = min(start_positions)
    end_object = raw_text.rfind("}")
    end_array = raw_text.rfind("]")
    end = max(end_object, end_array)
    if end < start:
        return None
    return raw_text[start : end + 1].strip()


def parse_structured_output_content(
    *,
    provider_name: str,
    capability: str,
    model_id: str,
    content: str,
    elapsed_text: str,
) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        logger.warning(
            "%s %s returned non-JSON content, attempting minimal repair. model=%s, elapsed_seconds=%s, raw_summary=%s",
            provider_name,
            capability,
            model_id,
            elapsed_text,
            summarize_text(content, limit=320),
        )
        candidate = extract_json_candidate(content)
        if candidate:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                logger.warning(
                    "%s %s minimal JSON repair failed. model=%s, candidate_summary=%s",
                    provider_name,
                    capability,
                    model_id,
                    summarize_text(candidate, limit=320),
                )
        raise RuntimeError(
            f"{provider_name} {capability} returned non-JSON content: "
            f"model={model_id}, elapsed_seconds={elapsed_text}, raw_summary={summarize_text(content, limit=600)}"
        ) from exc


class OpenAICompatibleChatClient:
    def __init__(
        self,
        *,
        provider_name: str,
        base_url: str,
        api_key: str,
        timeout_seconds: int,
    ) -> None:
        self.provider_name = provider_name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def create_chat_completion(
        self,
        *,
        model_id: str,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.2,
        extra_body: dict[str, Any] | None = None,
    ) -> requests.Response:
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        if extra_body:
            payload.update(extra_body)
        return self._post_with_retry(payload=payload, model_id=model_id)

    def parse_response_json(self, response: requests.Response, *, model_id: str) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"{self.provider_name} text response is not valid JSON: "
                f"model={model_id}, response={summarize_text(response.text, limit=800)}"
            ) from exc

    def extract_message_content(self, data: dict[str, Any], *, model_id: str) -> str:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"Unexpected {self.provider_name} response format: model={model_id}, response={data}"
            ) from exc
        if isinstance(content, list):
            return "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content)

    def _post_with_retry(self, *, payload: dict[str, Any], model_id: str) -> requests.Response:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        connect_timeout = 10
        read_timeout = max(int(self.timeout_seconds), 180)
        timeout = (connect_timeout, read_timeout)
        max_attempts = 2
        last_exception: Exception | None = None

        logger.info(
            "鍑嗗鍙戦€佹枃鏈ā鍨嬭姹傦紝provider=%s锛宮odel=%s锛宐ase_url=%s锛屼唬鐞嗙姸鎬?%s锛宼imeout=(connect=%s, read=%s)锛宺equests_session.trust_env=False",
            self.provider_name,
            model_id,
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
                    logger.info(
                        "鏂囨湰妯″瀷璇锋眰寮€濮嬶紝绗?%s/%s 娆★紝provider=%s锛宮odel=%s",
                        attempt,
                        max_attempts,
                        self.provider_name,
                        model_id,
                    )
                    response = session.post(url, headers=headers, json=payload, timeout=timeout)
                    response._ecom_elapsed_seconds = time.time() - started_at
                    logger.info(
                        "鏂囨湰妯″瀷璇锋眰宸茶繑鍥烇紝绗?%s/%s 娆★紝provider=%s锛宮odel=%s锛宻tatus_code=%s锛宔lapsed=%.2fs",
                        attempt,
                        max_attempts,
                        self.provider_name,
                        model_id,
                        response.status_code,
                        response._ecom_elapsed_seconds,
                    )
                    return response
                except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as exc:
                    elapsed_seconds = time.time() - started_at
                    last_exception = exc
                    if attempt >= max_attempts:
                        raise RuntimeError(
                            f"{self.provider_name} text request failed after retry: "
                            f"model={model_id}, url={url}, attempt={attempt}/{max_attempts}, "
                            f"timeout=(connect={connect_timeout}, read={read_timeout}), "
                            f"elapsed_seconds={elapsed_seconds:.2f}, error={exc}"
                        ) from exc
                    logger.warning(
                        "鏂囨湰妯″瀷璇锋眰寮傚父锛屽噯澶囬噸璇曪紝provider=%s锛宮odel=%s锛岀 %s/%s 娆★紝elapsed=%.2fs锛宔rror=%s",
                        self.provider_name,
                        model_id,
                        attempt,
                        max_attempts,
                        elapsed_seconds,
                        exc,
                    )
                    time.sleep(2)

        if last_exception is not None:
            raise RuntimeError(
                f"{self.provider_name} text request failed unexpectedly without response: "
                f"model={model_id}, url={url}, error={last_exception}"
            ) from last_exception
        raise RuntimeError(f"{self.provider_name} text request failed unexpectedly without response or exception.")


class OpenAICompatibleStructuredTextProvider(BaseTextProvider, ABC):
    provider_key = ""
    provider_display_name = ""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_selection = settings.resolve_text_model_selection()
        self.last_response_status_code: int | None = None
        self.last_response_metadata: dict[str, Any] = {}
        self.last_usage: ProviderUsageSnapshot | None = None

    def generate_structured(
        self,
        prompt: str,
        response_model: type[StructuredModel],
        *,
        system_prompt: str | None = None,
    ) -> StructuredModel:
        self.last_usage = ProviderUsageSnapshot.unavailable(request_count=1)
        logger.info(
            format_log_event(
                "provider_text_request_started",
                provider=self.provider_display_name,
                mode=self._resolve_route_mode(),
                model=self.model_selection.model_id,
                schema=response_model.__name__,
                prompt_length=len(prompt),
                system_prompt_length=len(system_prompt or ""),
            )
        )
        if self._resolve_route_mode() != "real":
            logger.error(
                format_log_event(
                    "provider_text_request_failed",
                    provider=self.provider_display_name,
                    mode=self._resolve_route_mode(),
                    model=self.model_selection.model_id,
                    schema=response_model.__name__,
                    reason="provider_not_real_mode",
                )
            )
            raise RuntimeError(f"{self.provider_display_name} text provider cannot run in mock mode.")

        api_key = self._resolve_api_key()
        if not api_key:
            logger.error(
                format_log_event(
                    "provider_text_request_failed",
                    provider=self.provider_display_name,
                    model=self.model_selection.model_id,
                    schema=response_model.__name__,
                    reason="missing_api_key",
                )
            )
            raise RuntimeError(self._missing_api_key_message())

        schema = response_model.model_json_schema()
        client = OpenAICompatibleChatClient(
            provider_name=self.provider_display_name,
            base_url=self._resolve_base_url(),
            api_key=api_key,
            timeout_seconds=self.settings.provider_timeout_seconds,
        )
        response = client.create_chat_completion(
            model_id=self.model_selection.model_id,
            messages=self._build_messages(prompt, schema, system_prompt=system_prompt),
            response_format=self._build_response_format(schema=schema, response_model=response_model),
            extra_body=self._build_extra_body(),
        )
        self.last_response_status_code = response.status_code
        self.last_response_metadata = {
            "provider_name": self.provider_key,
            "model_id": self.model_selection.model_id,
            "capability": "text",
            "status_code": response.status_code,
        }
        elapsed_seconds = getattr(response, "_ecom_elapsed_seconds", None)
        elapsed_ms = int(elapsed_seconds * 1000) if isinstance(elapsed_seconds, (int, float)) else 0
        elapsed_text = f"{elapsed_seconds:.2f}" if isinstance(elapsed_seconds, (int, float)) else "unknown"
        if response.status_code >= 400:
            self.last_usage = ProviderUsageSnapshot.unavailable(request_count=1, latency_ms=elapsed_ms)
            logger.error(
                format_log_event(
                    "provider_text_request_failed",
                    provider=self.provider_display_name,
                    model=self.model_selection.model_id,
                    status_code=response.status_code,
                    elapsed_ms=elapsed_ms,
                    response_length=len(response.text),
                )
            )
            raise RuntimeError(
                f"{self.provider_display_name} text request failed: "
                f"model={self.model_selection.model_id}, status_code={response.status_code}, "
                f"elapsed_seconds={elapsed_text}, response={summarize_text(response.text, limit=800)}"
            )

        data = client.parse_response_json(response, model_id=self.model_selection.model_id)
        self.last_usage = normalize_usage_snapshot(
            data.get("usage"),
            latency_ms=elapsed_ms,
            request_count=1,
        )
        content = client.extract_message_content(data, model_id=self.model_selection.model_id)
        parsed = parse_structured_output_content(
            provider_name=self.provider_display_name,
            capability="text",
            model_id=self.model_selection.model_id,
            content=content,
            elapsed_text=elapsed_text,
        )
        try:
            result = response_model.model_validate(parsed)
        except ValidationError as exc:
            logger.warning(
                format_log_event(
                    "provider_text_request_failed",
                    provider=self.provider_display_name,
                    model=self.model_selection.model_id,
                    schema=response_model.__name__,
                    reason="schema_validation_failed",
                    elapsed_ms=elapsed_ms,
                    response_length=len(content),
                )
            )
            raise RuntimeError(
                f"{self.provider_display_name} text schema validation failed: "
                f"model={self.model_selection.model_id}, raw_summary={summarize_text(content, limit=800)}"
            ) from exc

        logger.info(
            format_log_event(
                "provider_text_request_succeeded",
                provider=self.provider_display_name,
                model=self.model_selection.model_id,
                schema=response_model.__name__,
                elapsed_ms=elapsed_ms,
            )
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

    def _build_response_format(
        self,
        *,
        schema: dict[str, Any],
        response_model: type[StructuredModel],
    ) -> dict[str, Any]:
        return {"type": "json_object"}

    def _build_extra_body(self) -> dict[str, Any]:
        return {}

    def _resolve_route_mode(self) -> str:
        return self.settings.resolve_text_provider_route().mode

    @abstractmethod
    def _resolve_api_key(self) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def _resolve_base_url(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def _missing_api_key_message(self) -> str:
        raise NotImplementedError


