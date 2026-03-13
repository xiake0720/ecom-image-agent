from __future__ import annotations

import logging
from pathlib import Path
import time
from urllib.parse import urlparse

import requests

from src.core.config import Settings
from src.core.logging import describe_proxy_status, summarize_text
from src.domain.asset import Asset
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.domain.image_prompt_plan import ImagePromptPlan
from src.providers.image.base import BaseImageProvider
from src.providers.image.gemini_image import GeminiImageProvider

logger = logging.getLogger(__name__)


class DashScopeImageProvider(BaseImageProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_selection = settings.resolve_image_model_selection()
        self.last_response_status_code: int | None = None
        self.last_response_metadata: dict[str, str | int] = {}
        self._mock_provider = GeminiImageProvider()

    def generate_images(
        self,
        plan: ImagePromptPlan,
        *,
        output_dir: Path,
        reference_assets: list[Asset] | None = None,
    ) -> GenerationResult:
        try:
            return self._generate_images(plan=plan, output_dir=output_dir)
        except Exception as exc:
            if not self.settings.image_allow_mock_fallback:
                raise
            logger.warning(
                "DashScope image generation failed and explicit mock fallback is enabled. model=%s, error=%s",
                self.model_selection.model_id,
                exc,
            )
            return self._mock_provider.generate_images(
                plan,
                output_dir=output_dir,
                reference_assets=reference_assets,
            )

    def _generate_images(
        self,
        *,
        plan: ImagePromptPlan,
        output_dir: Path,
    ) -> GenerationResult:
        logger.info(
            "开始调用图片模型，provider=DashScope，mode=%s，model=%s，图片数量=%s，输出目录=%s",
            self.settings.resolve_image_provider_route().mode,
            self.model_selection.model_id,
            len(plan.prompts),
            output_dir,
        )
        if self.settings.resolve_image_provider_route().mode != "real":
            raise RuntimeError("DashScopeImageProvider cannot run in mock mode.")
        if not self.settings.dashscope_api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is required when the effective image provider route uses DashScope.")

        output_dir.mkdir(parents=True, exist_ok=True)
        images: list[GeneratedImage] = []
        for index, prompt in enumerate(plan.prompts, start=1):
            width, height = [int(value) for value in prompt.output_size.split("x", maxsplit=1)]
            task_id = self._submit_task(prompt=prompt.prompt, output_size=prompt.output_size)
            image_url = self._poll_task(task_id)
            image_bytes = self._download_image(image_url)
            output_path = output_dir / f"{index:02d}_{prompt.shot_id}.png"
            output_path.write_bytes(image_bytes)
            images.append(
                GeneratedImage(
                    shot_id=prompt.shot_id,
                    image_path=str(output_path),
                    preview_path=str(output_path),
                    width=width,
                    height=height,
                )
            )
            logger.info(
                "图片生成成功，provider=DashScope，model=%s，shot_id=%s，task_id=%s，输出=%s",
                self.model_selection.model_id,
                prompt.shot_id,
                task_id,
                output_path,
            )

        return GenerationResult(images=images)

    def _submit_task(self, *, prompt: str, output_size: str) -> str:
        url = f"{self._resolve_api_root()}/api/v1/services/aigc/text2image/image-synthesis"
        payload = {
            "model": self.model_selection.model_id,
            "input": {"prompt": prompt},
            "parameters": {
                "size": output_size.replace("x", "*"),
                "n": 1,
            },
        }
        with requests.Session() as session:
            session.trust_env = False
            logger.info(
                "提交 DashScope 文生图任务，model=%s，url=%s，size=%s，代理状态=%s，prompt摘要=%s",
                self.model_selection.model_id,
                url,
                output_size,
                describe_proxy_status(),
                summarize_text(prompt, limit=160),
            )
            response = session.post(
                url,
                headers=self._build_headers(async_mode=True),
                json=payload,
                timeout=(10, max(int(self.settings.provider_timeout_seconds), 180)),
            )
        self.last_response_status_code = response.status_code
        self.last_response_metadata = {
            "provider_name": "dashscope",
            "model_id": self.model_selection.model_id,
            "capability": "image",
            "status_code": response.status_code,
        }
        if response.status_code >= 400:
            raise RuntimeError(
                "DashScope image submit failed: "
                f"model={self.model_selection.model_id}, status_code={response.status_code}, "
                f"response={summarize_text(response.text, limit=800)}"
            )
        data = response.json()
        task_id = str((data.get("output") or {}).get("task_id") or "")
        if not task_id:
            raise RuntimeError(
                "DashScope image submit did not return task_id: "
                f"response={summarize_text(str(data), limit=800)}"
            )
        return task_id

    def _poll_task(self, task_id: str) -> str:
        url = f"{self._resolve_api_root()}/api/v1/tasks/{task_id}"
        deadline = time.monotonic() + max(int(self.settings.provider_timeout_seconds), 180)
        with requests.Session() as session:
            session.trust_env = False
            while time.monotonic() < deadline:
                response = session.get(
                    url,
                    headers=self._build_headers(async_mode=False),
                    timeout=(10, max(int(self.settings.provider_timeout_seconds), 180)),
                )
                if response.status_code >= 400:
                    raise RuntimeError(
                        "DashScope image task polling failed: "
                        f"task_id={task_id}, status_code={response.status_code}, "
                        f"response={summarize_text(response.text, limit=800)}"
                    )
                data = response.json()
                output = data.get("output") or {}
                status = str(output.get("task_status") or output.get("status") or "").upper()
                if status in {"SUCCEEDED", "SUCCESS"}:
                    image_url = self._extract_result_url(output)
                    if not image_url:
                        raise RuntimeError(
                            "DashScope image task succeeded but no result URL was found: "
                            f"task_id={task_id}, response={summarize_text(str(data), limit=800)}"
                        )
                    return image_url
                if status in {"FAILED", "CANCELED", "CANCELLED"}:
                    raise RuntimeError(
                        "DashScope image task failed: "
                        f"task_id={task_id}, response={summarize_text(str(data), limit=800)}"
                    )
                time.sleep(2)
        raise RuntimeError(f"DashScope image task polling timed out: task_id={task_id}")

    def _download_image(self, image_url: str) -> bytes:
        parsed = urlparse(image_url)
        if not parsed.scheme or not parsed.netloc:
            raise RuntimeError(f"DashScope image result URL is invalid: {image_url}")
        with requests.Session() as session:
            session.trust_env = False
            response = session.get(image_url, timeout=(10, max(int(self.settings.provider_timeout_seconds), 180)))
        if response.status_code >= 400:
            raise RuntimeError(
                f"DashScope image download failed: status_code={response.status_code}, url={image_url}"
            )
        return response.content

    def _extract_result_url(self, output: dict) -> str | None:
        results = output.get("results") or []
        for item in results:
            if isinstance(item, dict):
                url = item.get("url") or item.get("result_url")
                if url:
                    return str(url)
        result_url = output.get("result_url")
        if result_url:
            return str(result_url)
        return None

    def _resolve_api_root(self) -> str:
        base_url = self.settings.dashscope_base_url.rstrip("/")
        suffix = "/compatible-mode/v1"
        if base_url.endswith(suffix):
            return base_url[: -len(suffix)]
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

    def _build_headers(self, *, async_mode: bool) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.settings.dashscope_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if async_mode:
            headers["X-DashScope-Async"] = "enable"
        return headers
