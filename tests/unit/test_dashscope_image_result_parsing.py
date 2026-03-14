from __future__ import annotations

from src.core.config import Settings
from src.providers.image.dashscope_image import DashScopeImageProvider


def _provider() -> DashScopeImageProvider:
    return DashScopeImageProvider(
        Settings(
            image_provider="dashscope",
            image_provider_mode="real",
            dashscope_api_key="test-key",
        )
    )


def test_extract_result_url_supports_choices_message_content_image() -> None:
    provider = _provider()

    output = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "image", "image": "https://example.com/from-choice-image.png"},
                    ]
                }
            }
        ]
    }

    assert provider._extract_result_url(output) == "https://example.com/from-choice-image.png"


def test_extract_result_url_supports_results_url() -> None:
    provider = _provider()

    output = {
        "results": [
            {"url": "https://example.com/from-results-url.png"},
        ]
    }

    assert provider._extract_result_url(output) == "https://example.com/from-results-url.png"


def test_extract_result_url_supports_top_level_result_url() -> None:
    provider = _provider()

    output = {
        "result_url": "https://example.com/from-top-level-result-url.png",
    }

    assert provider._extract_result_url(output) == "https://example.com/from-top-level-result-url.png"


def test_extract_result_url_returns_none_when_missing() -> None:
    provider = _provider()

    output = {
        "task_status": "SUCCEEDED",
        "choices": [{"message": {"content": [{"type": "text", "text": "done"}]}}],
    }

    assert provider._extract_result_url(output) is None
