"""RunAPI Gemini 3.1 图片 provider。"""

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
from backend.core.logging import format_log_event
from backend.engine.domain.asset import Asset
from backend.engine.domain.generation_result import GeneratedImage, GenerationResult
from backend.engine.domain.image_prompt_plan import ImagePromptPlan
from backend.engine.domain.prompt_plan_v2 import PromptPlanV2, PromptShot
from backend.engine.domain.usage import ProviderUsageSnapshot, normalize_usage_snapshot
from backend.engine.providers.image.base import BaseImageProvider

logger = logging.getLogger(__name__)

RUNAPI_GEMINI31_MODEL_ID = "gemini-3.1-flash-image-preview"


@dataclass(frozen=True)
class ImageGenerationContext:
    """图片生成请求的最小上下文。"""

    generation_mode: str
    provider_alias: str
    model_id: str
    reference_asset_ids: list[str]
    selected_reference_assets: list[Asset]
    background_style_asset_ids: list[str]
    selected_background_style_assets: list[Asset]


class RunApiGemini31ImageProvider(BaseImageProvider):
    """通过 RunAPI 调用 Gemini 3.1 图片生成接口。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if settings.resolve_image_provider_route().alias == "runapi_gemini31":
            self.model_id = settings.resolve_image_model_selection().model_id
        else:
            self.model_id = RUNAPI_GEMINI31_MODEL_ID
        self.last_request_payloads: dict[str, dict[str, object]] = {}
        self.last_reference_asset_ids: list[str] = []
        self.last_background_style_asset_ids: list[str] = []
        self.last_usage: ProviderUsageSnapshot | None = None

    def resolve_generation_context(
        self,
        *,
        reference_assets: list[Asset] | None = None,
        background_style_assets: list[Asset] | None = None,
    ) -> ImageGenerationContext:
        """返回当前图片 provider 的运行上下文。"""

        prepared_assets = self._prepare_reference_assets(reference_assets)
        prepared_background_assets = self._prepare_background_style_assets(background_style_assets)
        return ImageGenerationContext(
            generation_mode="t2i",
            provider_alias="runapi_gemini31",
            model_id=self.model_id,
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
        """兼容旧版 `ImagePromptPlan` 调用方式。"""

        output_dir.mkdir(parents=True, exist_ok=True)
        prepared_assets = self._prepare_reference_assets(reference_assets)
        prepared_background_assets = self._prepare_background_style_assets(background_style_assets)
        self.last_reference_asset_ids = [asset.asset_id for asset in prepared_assets]
        self.last_background_style_asset_ids = [asset.asset_id for asset in prepared_background_assets]
        images: list[GeneratedImage] = []
        usage = ProviderUsageSnapshot.empty()
        for index, prompt in enumerate(plan.prompts, start=1):
            prompt_text = prompt.edit_instruction or prompt.prompt
            logger.info(
                "开始调用 Gemini 3.1 图片生成，mode=legacy-v1, shot_id=%s, reference_count=%s, background_style_count=%s, output_name=%s",
                prompt.shot_id,
                len(prepared_assets),
                len(prepared_background_assets),
                f"{index:02d}_{prompt.shot_id}.png",
            )
            image_bytes, shot_usage = self._generate_single(
                shot_id=prompt.shot_id,
                prompt_text=prompt_text,
                reference_assets=prepared_assets,
                background_style_assets=prepared_background_assets,
                aspect_ratio=self.settings.default_image_aspect_ratio,
                image_size=self.settings.default_image_size,
            )
            usage = usage.merged(shot_usage)
            images.append(
                self._write_generated_image(
                    index=index,
                    shot_id=prompt.shot_id,
                    image_bytes=image_bytes,
                    output_dir=output_dir,
                )
            )
        self.last_usage = usage
        return GenerationResult(images=images, usage=usage)

    def generate_images_v2(
        self,
        prompt_plan: PromptPlanV2,
        *,
        output_dir: Path,
        reference_assets: list[Asset] | None = None,
        background_style_assets: list[Asset] | None = None,
    ) -> GenerationResult:
        """按 v2 prompt plan 逐张生图并落盘。"""

        output_dir.mkdir(parents=True, exist_ok=True)
        prepared_assets = self._prepare_reference_assets(reference_assets)
        prepared_background_assets = self._prepare_background_style_assets(background_style_assets)
        self.last_reference_asset_ids = [asset.asset_id for asset in prepared_assets]
        self.last_background_style_asset_ids = [asset.asset_id for asset in prepared_background_assets]
        images: list[GeneratedImage] = []
        usage = ProviderUsageSnapshot.empty()
        for index, shot in enumerate(prompt_plan.shots, start=1):
            request_mode = "multimodal_t2i_with_refs" if prepared_assets or prepared_background_assets else "t2i_text_only"
            logger.info(
                "开始调用 Gemini 3.1 图片生成，mode=v2, request_mode=%s, shot_id=%s, reference_count=%s, background_style_count=%s, output_name=%s",
                request_mode,
                shot.shot_id,
                len(prepared_assets),
                len(prepared_background_assets),
                f"{index:02d}_{shot.shot_id}.png",
            )
            prompt_text = self._compose_v2_prompt_text(shot)
            image_bytes, shot_usage = self._generate_single(
                shot_id=shot.shot_id,
                prompt_text=prompt_text,
                reference_assets=prepared_assets,
                background_style_assets=prepared_background_assets,
                aspect_ratio=shot.aspect_ratio,
                image_size=shot.image_size,
            )
            usage = usage.merged(shot_usage)
            images.append(
                self._write_generated_image(
                    index=index,
                    shot_id=shot.shot_id,
                    image_bytes=image_bytes,
                    output_dir=output_dir,
                )
            )
        self.last_usage = usage
        return GenerationResult(images=images, usage=usage)

    def _compose_v2_prompt_text(self, shot: PromptShot) -> str:
        """把 v2 shot 结构压成最终发给图片模型的文本提示。"""

        lines = [shot.render_prompt]
        lines.append(
            f"图内文字策略: copy_strategy={shot.copy_strategy}, text_density={shot.text_density}, should_render_text={str(shot.should_render_text).lower()}"
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
        if not shot.should_render_text or shot.copy_strategy == "none":
            lines.append("本图不应主动生成广告大字，重点保留画面质感和产品细节。")
        lines.append("广告文案只允许使用上述标题、副标题、卖点，严禁转写、复用或概括任何参考图可见文字。")
        return "\n".join(lines).strip()

    def _generate_single(
        self,
        *,
        shot_id: str,
        prompt_text: str,
        reference_assets: list[Asset],
        background_style_assets: list[Asset] | None = None,
        aspect_ratio: str,
        image_size: str,
    ) -> tuple[bytes, ProviderUsageSnapshot]:
        """执行单次图片生成请求，并从响应中提取图片字节。"""

        if self.settings.image_provider_mode == "mock":
            raise RuntimeError("RunApiGemini31ImageProvider cannot run in mock mode.")
        if not self.settings.runapi_api_key:
            raise RuntimeError("ECOM_IMAGE_AGENT_RUNAPI_API_KEY is required when using runapi_gemini31.")

        background_assets = background_style_assets or []
        payload = self._build_request_payload(
            prompt_text=prompt_text,
            reference_assets=reference_assets,
            background_style_assets=background_assets,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
        self.last_request_payloads[shot_id] = payload
        self.last_usage = ProviderUsageSnapshot.unavailable(request_count=1)
        url = f"{self.settings.runapi_image_base_url.rstrip('/')}/v1/models/{self.model_id}:generateContent"
        logger.info(
            format_log_event(
                "provider_image_request_started",
                provider="runapi_gemini31",
                model=self.model_id,
                shot_id=shot_id,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                reference_count=len(reference_assets),
                background_style_count=len(background_assets),
            )
        )
        logger.info(
            "发送 Gemini 3.1 图片请求，shot_id=%s, url=%s, aspect_ratio=%s, image_size=%s, reference_count=%s, background_style_count=%s, proxy=%s",
            shot_id,
            url,
            aspect_ratio,
            image_size,
            len(reference_assets),
            len(background_assets),
            describe_proxy_status(),
        )
        started_at = perf_counter()
        try:
            with requests.Session() as session:
                session.trust_env = False
                session.proxies.clear()
                response = session.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.settings.runapi_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=self.settings.provider_timeout_seconds,
                )
        except requests.RequestException as exc:
            self.last_usage = ProviderUsageSnapshot.unavailable(
                request_count=1,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )
            logger.exception("Gemini 3.1 图片请求失败，shot_id=%s, error=%s", shot_id, exc)
            raise RuntimeError(f"RunAPI Gemini 3.1 request failed for {shot_id}: {exc}") from exc

        if response.status_code >= 400:
            logger.error(
                "Gemini 3.1 图片请求失败，shot_id=%s, status_code=%s, response=%s",
                shot_id,
                response.status_code,
                summarize_text(response.text, limit=240),
            )
            self.last_usage = ProviderUsageSnapshot.unavailable(
                request_count=1,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )
            raise RuntimeError(f"RunAPI Gemini 3.1 request failed: {response.status_code} {response.text[:1200]}")

        try:
            data = response.json()
        except ValueError as exc:
            self.last_usage = ProviderUsageSnapshot.unavailable(
                request_count=1,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )
            raise RuntimeError(f"RunAPI Gemini 3.1 response is not valid JSON: {response.text[:1200]}") from exc

        elapsed_ms = int((perf_counter() - started_at) * 1000)
        usage = normalize_usage_snapshot(
            data.get("usageMetadata") or data.get("usage_metadata") or data.get("usage"),
            latency_ms=elapsed_ms,
            request_count=1,
            image_count=1,
        )
        self.last_usage = usage
        logger.info("Gemini 3.1 图片请求成功，shot_id=%s, elapsed_ms=%s", shot_id, elapsed_ms)
        logger.info(
            format_log_event(
                "provider_image_request_succeeded",
                provider="runapi_gemini31",
                model=self.model_id,
                shot_id=shot_id,
                elapsed_ms=elapsed_ms,
            )
        )
        return self._extract_image_bytes(data), usage

    def _build_request_payload(
        self,
        *,
        prompt_text: str,
        reference_assets: list[Asset],
        background_style_assets: list[Asset],
        aspect_ratio: str,
        image_size: str,
    ) -> dict[str, object]:
        """构造符合 Gemini 3.1 generateContent 的请求体。"""

        parts: list[dict[str, object]] = [{"text": prompt_text}]
        if reference_assets:
            parts.append(
                {
                    "text": "以下是产品参考图，只能用于保持包装结构、材质、颜色和品牌识别稳定，不得提取或改写其中可见文字。"
                }
            )
            self._append_inline_assets(parts, reference_assets)
        if background_style_assets:
            parts.append(
                {
                    "text": "以下是背景与风格参考图，只能用于学习氛围、配色和空间语言，不得替代产品主体，也不得提取其中可见文字。"
                }
            )
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
        """把参考图编码为 RunAPI inlineData。"""

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

    def _extract_image_bytes(self, response_json: dict[str, object]) -> bytes:
        """从 Gemini 3.1 响应中提取图片字节。"""

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
                        return self._download_generated_file(str(file_uri))
        raise RuntimeError(f"RunAPI Gemini 3.1 response did not contain image data: {response_json}")

    def _download_generated_file(self, file_uri: str) -> bytes:
        """下载 RunAPI 返回的 fileUri。"""

        logger.info("检测到 Gemini 3.1 fileUri 返回，开始下载图片文件，url=%s", file_uri)
        try:
            with requests.Session() as session:
                session.trust_env = False
                session.proxies.clear()
                response = session.get(
                    file_uri,
                    headers={"Authorization": f"Bearer {self.settings.runapi_api_key}"},
                    timeout=self.settings.provider_timeout_seconds,
                )
        except requests.RequestException as exc:
            logger.exception("Gemini 3.1 fileUri 图片下载失败，url=%s, error=%s", file_uri, exc)
            raise RuntimeError(f"RunAPI Gemini 3.1 file download failed: {exc}") from exc

        if response.status_code >= 400:
            logger.error(
                "Gemini 3.1 fileUri 图片下载失败，status_code=%s, url=%s, response=%s",
                response.status_code,
                file_uri,
                summarize_text(response.text, limit=240),
            )
            raise RuntimeError(f"RunAPI Gemini 3.1 file download failed: {response.status_code} {response.text[:1200]}")
        if not response.content:
            raise RuntimeError(f"RunAPI Gemini 3.1 file download returned empty body: {file_uri}")
        return response.content

    def _write_generated_image(self, *, index: int, shot_id: str, image_bytes: bytes, output_dir: Path) -> GeneratedImage:
        """把返回图片字节写入输出目录，并提取实际像素尺寸。"""

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
        """统一裁剪到最多两张产品参考图。"""

        prepared: list[Asset] = []
        for asset in reference_assets or []:
            if not asset.local_path:
                continue
            prepared.append(asset)
            if len(prepared) >= 2:
                break
        return prepared

    def _prepare_background_style_assets(self, background_style_assets: list[Asset] | None) -> list[Asset]:
        """统一裁剪到最多两张背景风格参考图。"""

        prepared: list[Asset] = []
        for asset in background_style_assets or []:
            if not asset.local_path:
                continue
            prepared.append(asset)
            if len(prepared) >= 2:
                break
        return prepared

    def _guess_mime_type(self, path: Path) -> str:
        """按文件后缀推断最小可用 MIME。"""

        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"
