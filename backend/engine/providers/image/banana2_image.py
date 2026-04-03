"""Banana2 图片 provider。"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
import logging
from pathlib import Path
from time import perf_counter

from PIL import Image
import requests

from backend.engine.core.config import Settings
from backend.engine.core.logging import describe_proxy_status, summarize_text
from backend.engine.domain.asset import Asset
from backend.engine.domain.generation_result import GeneratedImage, GenerationResult
from backend.engine.domain.image_prompt_plan import ImagePromptPlan
from backend.engine.domain.prompt_plan_v2 import PromptPlanV2, PromptShot
from backend.engine.providers.image.base import BaseImageProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Banana2GenerationContext:
    """当前 Banana2 请求的最小执行上下文。"""

    generation_mode: str
    provider_alias: str
    model_id: str
    transport: str
    reference_asset_ids: list[str]
    selected_reference_assets: list[Asset]
    background_style_asset_ids: list[str]
    selected_background_style_assets: list[Asset]


class Banana2ImageProvider(BaseImageProvider):
    """通过统一 provider/router 接入 Banana2。

    真实调用优先使用官方 Gemini API；若未配置 Google API Key，则回退到
    现有 RunAPI 转发通道，保持主图与详情图共用同一套 provider 体系。
    """

    provider_alias = "banana2"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_id = settings.resolve_image_model_selection().model_id
        self.last_request_payloads: dict[str, dict[str, object]] = {}
        self.last_reference_asset_ids: list[str] = []
        self.last_background_style_asset_ids: list[str] = []

    def resolve_generation_context(
        self,
        *,
        reference_assets: list[Asset] | None = None,
        background_style_assets: list[Asset] | None = None,
    ) -> Banana2GenerationContext:
        """返回当前 provider 的运行上下文。"""

        prepared_assets = self._prepare_reference_assets(reference_assets)
        prepared_background_assets = self._prepare_background_style_assets(background_style_assets)
        return Banana2GenerationContext(
            generation_mode="multimodal_t2i_with_refs",
            provider_alias=self.provider_alias,
            model_id=self.model_id,
            transport=self._resolve_transport(),
            reference_asset_ids=[asset.asset_id for asset in prepared_assets],
            selected_reference_assets=prepared_assets,
            background_style_asset_ids=[asset.asset_id for asset in prepared_background_assets],
            selected_background_style_assets=prepared_background_assets,
        )

    def generate_images(
        self,
        plan: ImagePromptPlan,
        *,
        output_dir: Path,
        reference_assets: list[Asset] | None = None,
        background_style_assets: list[Asset] | None = None,
    ) -> GenerationResult:
        """兼容旧的 `ImagePromptPlan` 调用方式。"""

        output_dir.mkdir(parents=True, exist_ok=True)
        prepared_assets = self._prepare_reference_assets(reference_assets)
        prepared_background_assets = self._prepare_background_style_assets(background_style_assets)
        self.last_reference_asset_ids = [asset.asset_id for asset in prepared_assets]
        self.last_background_style_asset_ids = [asset.asset_id for asset in prepared_background_assets]
        images: list[GeneratedImage] = []
        for index, prompt in enumerate(plan.prompts, start=1):
            prompt_text = prompt.edit_instruction or prompt.prompt
            image_bytes = self._generate_single(
                shot_id=prompt.shot_id,
                prompt_text=prompt_text,
                reference_assets=prepared_assets,
                background_style_assets=prepared_background_assets,
                aspect_ratio=self.settings.default_image_aspect_ratio,
                image_size=self.settings.default_image_size,
            )
            images.append(self._write_generated_image(index=index, shot_id=prompt.shot_id, image_bytes=image_bytes, output_dir=output_dir))
        return GenerationResult(images=images)

    def generate_images_v2(
        self,
        prompt_plan: PromptPlanV2,
        *,
        output_dir: Path,
        reference_assets: list[Asset] | None = None,
        background_style_assets: list[Asset] | None = None,
    ) -> GenerationResult:
        """按 v2 prompt plan 逐张生成并落盘。"""

        output_dir.mkdir(parents=True, exist_ok=True)
        prepared_assets = self._prepare_reference_assets(reference_assets)
        prepared_background_assets = self._prepare_background_style_assets(background_style_assets)
        self.last_reference_asset_ids = [asset.asset_id for asset in prepared_assets]
        self.last_background_style_asset_ids = [asset.asset_id for asset in prepared_background_assets]
        images: list[GeneratedImage] = []
        for index, shot in enumerate(prompt_plan.shots, start=1):
            image_bytes = self._generate_single(
                shot_id=shot.shot_id,
                prompt_text=self._compose_v2_prompt_text(shot),
                reference_assets=prepared_assets,
                background_style_assets=prepared_background_assets,
                aspect_ratio=shot.aspect_ratio,
                image_size=shot.image_size,
            )
            images.append(self._write_generated_image(index=index, shot_id=shot.shot_id, image_bytes=image_bytes, output_dir=output_dir))
        return GenerationResult(images=images)

    def _compose_v2_prompt_text(self, shot: PromptShot) -> str:
        """把 v2 shot 收口为最终文本指令。"""

        lines = [shot.render_prompt]
        lines.append(
            "图内文字策略："
            f"copy_strategy={shot.copy_strategy}, text_density={shot.text_density}, should_render_text={str(shot.should_render_text).lower()}"
        )
        if shot.should_render_text and shot.title_copy:
            lines.append(f"主标题：{shot.title_copy}")
        if shot.should_render_text and shot.subtitle_copy:
            lines.append(f"副标题：{shot.subtitle_copy}")
        if shot.should_render_text and shot.selling_points_for_render:
            lines.append(f"卖点：{'；'.join(shot.selling_points_for_render)}")
        if shot.layout_hint:
            lines.append(f"版式提示：{shot.layout_hint}")
        if shot.typography_hint:
            lines.append(f"文字层级：{shot.typography_hint}")
        if shot.subject_occupancy_ratio:
            lines.append(f"主体占比：约 {int(shot.subject_occupancy_ratio * 100)}%")
        return "\n".join(lines).strip()

    def _generate_single(
        self,
        *,
        shot_id: str,
        prompt_text: str,
        reference_assets: list[Asset],
        background_style_assets: list[Asset],
        aspect_ratio: str,
        image_size: str,
    ) -> bytes:
        """执行单次 Banana2 请求。"""

        transport = self._resolve_transport()
        payload = self._build_request_payload(
            prompt_text=prompt_text,
            reference_assets=reference_assets,
            background_style_assets=background_style_assets,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
        self.last_request_payloads[shot_id] = payload
        url, headers = self._resolve_request_target(transport)
        started_at = perf_counter()
        logger.info(
            "发送 Banana2 图片请求，shot_id=%s transport=%s url=%s aspect_ratio=%s image_size=%s reference_count=%s background_style_count=%s proxy=%s",
            shot_id,
            transport,
            url,
            aspect_ratio,
            image_size,
            len(reference_assets),
            len(background_style_assets),
            describe_proxy_status(),
        )
        try:
            with requests.Session() as session:
                session.trust_env = False
                session.proxies.clear()
                response = session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.settings.provider_timeout_seconds,
                )
        except requests.RequestException as exc:
            logger.exception("Banana2 请求失败，shot_id=%s transport=%s error=%s", shot_id, transport, exc)
            raise RuntimeError(f"Banana2 request failed for {shot_id}: {exc}") from exc

        if response.status_code >= 400:
            logger.error(
                "Banana2 请求失败，shot_id=%s transport=%s status_code=%s response=%s",
                shot_id,
                transport,
                response.status_code,
                summarize_text(response.text, limit=320),
            )
            raise RuntimeError(f"Banana2 request failed: {response.status_code} {response.text[:1200]}")

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Banana2 response is not valid JSON: {response.text[:1200]}") from exc

        logger.info(
            "Banana2 请求成功，shot_id=%s transport=%s elapsed_ms=%s",
            shot_id,
            transport,
            int((perf_counter() - started_at) * 1000),
        )
        return self._extract_image_bytes(data, transport=transport)

    def _resolve_transport(self) -> str:
        """优先使用官方 API，缺失时回退到 RunAPI 转发。"""

        if self.settings.google_api_key:
            return "google"
        if self.settings.runapi_api_key:
            return "runapi"
        raise RuntimeError(
            "Banana2 real mode requires ECOM_IMAGE_AGENT_GOOGLE_API_KEY or ECOM_IMAGE_AGENT_RUNAPI_API_KEY."
        )

    def _resolve_request_target(self, transport: str) -> tuple[str, dict[str, str]]:
        if transport == "google":
            return (
                f"{self.settings.google_image_base_url.rstrip('/')}/models/{self.model_id}:generateContent?key={self.settings.google_api_key}",
                {"Content-Type": "application/json"},
            )
        return (
            f"{self.settings.runapi_image_base_url.rstrip('/')}/v1/models/{self.model_id}:generateContent",
            {
                "Authorization": f"Bearer {self.settings.runapi_api_key}",
                "Content-Type": "application/json",
            },
        )

    def _build_request_payload(
        self,
        *,
        prompt_text: str,
        reference_assets: list[Asset],
        background_style_assets: list[Asset],
        aspect_ratio: str,
        image_size: str,
    ) -> dict[str, object]:
        """构造 generateContent 请求体。"""

        parts: list[dict[str, object]] = [{"text": prompt_text}]
        if reference_assets:
            parts.append({"text": "以下是产品参考图，只能用于保持包装结构、材质、颜色与品牌识别一致，不得转写其中可见文字。"})
            self._append_inline_assets(parts, reference_assets)
        if background_style_assets:
            parts.append({"text": "以下是背景与场景参考图，只能用于学习氛围、色调与空间语言，不得替换产品主体。"})
            self._append_inline_assets(parts, background_style_assets)
        return {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {
                    "aspectRatio": aspect_ratio or self.settings.default_image_aspect_ratio,
                    "imageSize": image_size or self.settings.default_image_size,
                },
            },
        }

    def _append_inline_assets(self, parts: list[dict[str, object]], assets: list[Asset]) -> None:
        for asset in assets:
            asset_path = Path(asset.local_path)
            if not asset.local_path or not asset_path.exists():
                continue
            parts.append(
                {
                    "inlineData": {
                        "mimeType": asset.mime_type or self._guess_mime_type(asset_path),
                        "data": base64.b64encode(asset_path.read_bytes()).decode("utf-8"),
                    }
                }
            )

    def _extract_image_bytes(self, response_json: dict[str, object], *, transport: str) -> bytes:
        for candidate in response_json.get("candidates", []):
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return base64.b64decode(inline["data"])
                file_data = part.get("fileData") or part.get("file_data")
                if file_data:
                    file_uri = file_data.get("fileUri") or file_data.get("file_uri")
                    if file_uri:
                        return self._download_generated_file(str(file_uri), transport=transport)
        raise RuntimeError(f"Banana2 response did not contain image data: {response_json}")

    def _download_generated_file(self, file_uri: str, *, transport: str) -> bytes:
        headers: dict[str, str] = {}
        if transport == "runapi" and self.settings.runapi_api_key:
            headers["Authorization"] = f"Bearer {self.settings.runapi_api_key}"
        try:
            with requests.Session() as session:
                session.trust_env = False
                session.proxies.clear()
                response = session.get(file_uri, headers=headers, timeout=self.settings.provider_timeout_seconds)
        except requests.RequestException as exc:
            logger.exception("Banana2 fileUri 下载失败，url=%s error=%s", file_uri, exc)
            raise RuntimeError(f"Banana2 file download failed: {exc}") from exc

        if response.status_code >= 400:
            raise RuntimeError(f"Banana2 file download failed: {response.status_code} {response.text[:1200]}")
        if not response.content:
            raise RuntimeError(f"Banana2 file download returned empty body: {file_uri}")
        return response.content

    def _write_generated_image(self, *, index: int, shot_id: str, image_bytes: bytes, output_dir: Path) -> GeneratedImage:
        output_path = output_dir / f"{index:02d}_{shot_id}.png"
        output_path.write_bytes(image_bytes)
        with Image.open(BytesIO(image_bytes)) as image:
            width, height = image.size
        return GeneratedImage(
            shot_id=shot_id,
            image_path=str(output_path),
            preview_path=str(output_path),
            width=width,
            height=height,
        )

    def _prepare_reference_assets(self, reference_assets: list[Asset] | None) -> list[Asset]:
        """Banana2 detail 页允许同时绑定更多产品参考图。"""

        prepared: list[Asset] = []
        for asset in reference_assets or []:
            if not asset.local_path:
                continue
            prepared.append(asset)
            if len(prepared) >= 4:
                break
        return prepared

    def _prepare_background_style_assets(self, background_style_assets: list[Asset] | None) -> list[Asset]:
        prepared: list[Asset] = []
        for asset in background_style_assets or []:
            if not asset.local_path:
                continue
            prepared.append(asset)
            if len(prepared) >= 2:
                break
        return prepared

    def _guess_mime_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"
