from __future__ import annotations

import base64
import logging
from pathlib import Path
from urllib.parse import urlparse

from src.core.config import Settings
from src.core.logging import describe_proxy_status, summarize_text
from src.domain.asset import Asset
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.domain.image_prompt_plan import ImagePromptPlan
from src.providers.image.dashscope_image import DashScopeImageProvider

logger = logging.getLogger(__name__)


class DashScopeImageEditProvider(DashScopeImageProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.model_selection = settings.resolve_image_edit_model_selection()

    def generate_images(
        self,
        plan: ImagePromptPlan,
        *,
        output_dir: Path,
        reference_assets: list[Asset] | None = None,
    ) -> GenerationResult:
        try:
            return self._generate_images(plan=plan, output_dir=output_dir, reference_assets=reference_assets or [])
        except Exception as exc:
            if not self.settings.image_allow_mock_fallback:
                raise
            logger.warning(
                "DashScope image edit failed and explicit mock fallback is enabled. model=%s, error=%s",
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
        reference_assets: list[Asset],
    ) -> GenerationResult:
        if self.settings.resolve_image_provider_route().mode != "real":
            raise RuntimeError("DashScopeImageEditProvider cannot run in mock mode.")
        if not self.settings.dashscope_api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is required when the effective image provider route uses DashScope.")

        prepared_assets = self._prepare_reference_assets(reference_assets)
        if not prepared_assets:
            raise RuntimeError("DashScope image edit requires at least one valid reference asset.")

        reference_asset_ids = [asset.asset_id for asset in prepared_assets]
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "Starting DashScope image edit generation: mode=image_edit, model_id=%s, prompts=%s, reference_asset_ids=%s, output_dir=%s",
            self.model_selection.model_id,
            len(plan.prompts),
            reference_asset_ids,
            output_dir,
        )

        images: list[GeneratedImage] = []
        for index, prompt in enumerate(plan.prompts, start=1):
            width, height = [int(value) for value in prompt.output_size.split("x", maxsplit=1)]
            task_id = self._submit_task(
                prompt=prompt.prompt,
                output_size=prompt.output_size,
                reference_assets=prepared_assets,
            )
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
                "DashScope image edit succeeded: mode=image_edit, model_id=%s, shot_id=%s, task_id=%s, reference_asset_ids=%s, output_path=%s",
                self.model_selection.model_id,
                prompt.shot_id,
                task_id,
                reference_asset_ids,
                output_path,
            )

        return GenerationResult(images=images)

    def _submit_task(self, *, prompt: str, output_size: str, reference_assets: list[Asset]) -> str:
        url = f"{self._resolve_api_root()}/api/v1/services/aigc/image-generation/generation"
        content = [{"image": self._asset_to_image_input(asset)} for asset in reference_assets]
        content.append({"text": prompt})
        payload = {
            "model": self.model_selection.model_id,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": content,
                    }
                ]
            },
            "parameters": {
                "size": output_size.replace("x", "*"),
                "n": 1,
            },
        }
        logger.info(
            "Submitting DashScope image edit task: mode=image_edit, model_id=%s, url=%s, size=%s, reference_asset_ids=%s, proxy=%s, prompt_summary=%s",
            self.model_selection.model_id,
            url,
            output_size,
            [asset.asset_id for asset in reference_assets],
            describe_proxy_status(),
            summarize_text(prompt, limit=160),
        )
        return self._submit_json_task(url=url, payload=payload)

    def _prepare_reference_assets(self, reference_assets: list[Asset]) -> list[Asset]:
        max_images = self.settings.resolve_image_edit_max_reference_images()
        if not self.settings.image_edit_prefer_multi_image:
            max_images = 1
        prepared: list[Asset] = []
        for asset in reference_assets:
            if not asset.local_path:
                continue
            path = Path(asset.local_path)
            if path.exists() or self._is_remote_image(asset.local_path):
                prepared.append(asset)
            if len(prepared) >= max_images:
                break
        return prepared

    def _asset_to_image_input(self, asset: Asset) -> str:
        raw_path = str(asset.local_path or "").strip()
        if self._is_remote_image(raw_path) or raw_path.startswith("data:"):
            return raw_path
        path = Path(raw_path)
        mime_type = asset.mime_type or self._guess_mime_type(path)
        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _submit_json_task(self, *, url: str, payload: dict) -> str:
        import requests

        with requests.Session() as session:
            session.trust_env = False
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
            "capability": "image_edit",
            "status_code": response.status_code,
        }
        if response.status_code >= 400:
            raise RuntimeError(
                "DashScope image edit submit failed: "
                f"model={self.model_selection.model_id}, status_code={response.status_code}, "
                f"response={summarize_text(response.text, limit=800)}"
            )
        data = response.json()
        task_id = str((data.get("output") or {}).get("task_id") or "")
        if not task_id:
            raise RuntimeError(
                "DashScope image edit submit did not return task_id: "
                f"response={summarize_text(str(data), limit=800)}"
            )
        return task_id

    def _is_remote_image(self, value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"}

    def _guess_mime_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"
