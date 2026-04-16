"""Banana2 图片 provider。"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
import logging
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlparse

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover - optional dependency
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]
from PIL import Image
import requests

from backend.engine.core.config import Settings
from backend.engine.core.logging import describe_proxy_status, summarize_text
from backend.engine.domain.asset import Asset
from backend.engine.domain.generation_result import GeneratedImage, GenerationResult
from backend.engine.domain.image_prompt_plan import ImagePromptPlan
from backend.engine.domain.prompt_plan_v2 import PromptPlanV2, PromptShot
from backend.engine.domain.usage import ProviderUsageSnapshot, normalize_usage_snapshot
from backend.engine.providers.image.base import BaseImageProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Banana2GenerationContext:
    """Banana2 请求的最小运行上下文。"""

    generation_mode: str
    provider_alias: str
    model_id: str
    transport: str
    reference_asset_ids: list[str]
    selected_reference_assets: list[Asset]
    background_style_asset_ids: list[str]
    selected_background_style_assets: list[Asset]


class Banana2ImageProvider(BaseImageProvider):
    """统一图片 provider。"""

    provider_alias = "banana2"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_id = settings.resolve_image_model_selection().model_id
        self.last_request_payloads: dict[str, dict[str, object]] = {}
        self.last_reference_asset_ids: list[str] = []
        self.last_background_style_asset_ids: list[str] = []
        self.last_usage: ProviderUsageSnapshot | None = None
        self._google_client: Any | None = None

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
            image_bytes, shot_usage = self._generate_single(
                shot_id=shot.shot_id,
                prompt_text=self._compose_v2_prompt_text(shot),
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
        background_style_assets: list[Asset],
        aspect_ratio: str,
        image_size: str,
    ) -> tuple[bytes, ProviderUsageSnapshot]:
        """执行单次图片请求，并返回图片字节与 usage 快照。"""

        transport = self._resolve_transport()
        started_at = perf_counter()
        self.last_usage = ProviderUsageSnapshot.unavailable(request_count=1)
        logger.info(
            "发送 Banana2 图片请求，shot_id=%s transport=%s model=%s aspect_ratio=%s image_size=%s reference_count=%s background_style_count=%s proxy=%s",
            shot_id,
            transport,
            self.model_id,
            aspect_ratio,
            image_size,
            len(reference_assets),
            len(background_style_assets),
            describe_proxy_status(),
        )
        if transport == "google_official_sdk":
            payload = self._build_google_request_payload(
                prompt_text=prompt_text,
                reference_assets=reference_assets,
                background_style_assets=background_style_assets,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            )
            self.last_request_payloads[shot_id] = payload
            try:
                image_bytes, usage = self._generate_single_via_google_sdk(
                    prompt_text=prompt_text,
                    reference_assets=reference_assets,
                    background_style_assets=background_style_assets,
                    aspect_ratio=aspect_ratio,
                    image_size=image_size,
                )
            except Exception as exc:
                self.last_usage = ProviderUsageSnapshot.unavailable(
                    request_count=1,
                    latency_ms=int((perf_counter() - started_at) * 1000),
                )
                logger.exception("Google 官方图片请求失败，shot_id=%s error=%s", shot_id, exc)
                raise RuntimeError(f"Google official image request failed for {shot_id}: {exc}") from exc
        else:
            payload = self._build_runapi_request_payload(
                prompt_text=prompt_text,
                reference_assets=reference_assets,
                background_style_assets=background_style_assets,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            )
            self.last_request_payloads[shot_id] = payload
            try:
                image_bytes, usage = self._generate_single_via_runapi(
                    shot_id=shot_id,
                    payload=payload,
                    aspect_ratio=aspect_ratio,
                    image_size=image_size,
                )
            except Exception as exc:
                self.last_usage = ProviderUsageSnapshot.unavailable(
                    request_count=1,
                    latency_ms=int((perf_counter() - started_at) * 1000),
                )
                logger.exception("RunAPI 图片请求失败，shot_id=%s error=%s", shot_id, exc)
                raise RuntimeError(f"RunAPI image request failed for {shot_id}: {exc}") from exc
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        usage = usage.model_copy(update={"latency_ms": elapsed_ms})
        self.last_usage = usage
        logger.info("Banana2 图片请求成功，shot_id=%s transport=%s elapsed_ms=%s", shot_id, transport, elapsed_ms)
        return image_bytes, usage

    def _generate_single_via_google_sdk(
        self,
        *,
        prompt_text: str,
        reference_assets: list[Asset],
        background_style_assets: list[Asset],
        aspect_ratio: str,
        image_size: str,
    ) -> tuple[bytes, ProviderUsageSnapshot]:
        """通过 Google 官方 SDK 调用图片模型。"""

        client = self._get_google_client()
        response = client.models.generate_content(
            model=self.model_id,
            contents=self._build_google_contents(
                prompt_text=prompt_text,
                reference_assets=reference_assets,
                background_style_assets=background_style_assets,
            ),
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio or self.settings.default_image_aspect_ratio,
                    image_size=image_size or self.settings.default_image_size,
                ),
            ),
        )
        return (
            self._extract_google_image_bytes(response),
            normalize_usage_snapshot(
                getattr(response, "usage_metadata", None),
                request_count=1,
                image_count=1,
            ),
        )

    def _generate_single_via_runapi(
        self,
        *,
        shot_id: str,
        payload: dict[str, object],
        aspect_ratio: str,
        image_size: str,
    ) -> tuple[bytes, ProviderUsageSnapshot]:
        """通过 RunAPI 转发通道调用图片模型。"""

        if not self.settings.runapi_api_key:
            raise RuntimeError("ECOM_IMAGE_AGENT_RUNAPI_API_KEY is required when using RunAPI transport.")
        url, headers = self._resolve_runapi_request_target()
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
            raise RuntimeError(f"RunAPI image request failed for {shot_id}: {exc}") from exc

        if response.status_code >= 400:
            logger.error(
                "RunAPI 图片请求失败，shot_id=%s status_code=%s response=%s aspect_ratio=%s image_size=%s",
                shot_id,
                response.status_code,
                summarize_text(response.text, limit=320),
                aspect_ratio,
                image_size,
            )
            raise RuntimeError(f"RunAPI image request failed: {response.status_code} {response.text[:1200]}")

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f"RunAPI response is not valid JSON: {response.text[:1200]}") from exc
        raw_usage = data.get("usageMetadata") or data.get("usage_metadata") or data.get("usage")
        return (
            self._extract_runapi_image_bytes(data),
            normalize_usage_snapshot(
                raw_usage,
                request_count=1,
                image_count=1,
            ),
        )

    def _resolve_transport(self) -> str:
        """优先使用 Google 官方 SDK，缺失时回退到 RunAPI。"""

        if self.settings.google_api_key:
            if genai is not None and types is not None:
                return "google_official_sdk"
            logger.warning("检测到 Google API Key，但当前环境未安装 google-genai，已回退到 RunAPI 通道。")
        if self.settings.runapi_api_key:
            return "runapi"
        if self.settings.google_api_key:
            raise RuntimeError("google-genai is required for Google official SDK transport.")
        raise RuntimeError(
            "Banana2 real mode requires ECOM_IMAGE_AGENT_GOOGLE_API_KEY or ECOM_IMAGE_AGENT_RUNAPI_API_KEY."
        )

    def _get_google_client(self) -> genai.Client:
        """惰性初始化 Google 官方 SDK client。"""

        if genai is None or types is None:
            raise RuntimeError("google-genai is required for Google official SDK transport.")
        if not self.settings.google_api_key:
            raise RuntimeError("ECOM_IMAGE_AGENT_GOOGLE_API_KEY is required for Google official SDK transport.")
        if self._google_client is None:
            self._google_client = genai.Client(
                api_key=self.settings.google_api_key,
                http_options=self._build_google_http_options(),
            )
        return self._google_client

    def _build_google_http_options(self) -> types.HttpOptions:
        """把配置映射到 Google 官方 SDK 的 HTTP 选项。"""

        configured_url = str(self.settings.google_image_base_url or "").strip()
        default_root = "https://generativelanguage.googleapis.com"
        options: dict[str, object] = {
            "timeout": self.settings.provider_timeout_seconds * 1000,
            "client_args": {"trust_env": False},
        }
        if configured_url:
            parsed = urlparse(configured_url)
            segments = [segment for segment in parsed.path.split("/") if segment]
            if segments and segments[-1].startswith("v"):
                options["api_version"] = segments[-1]
                segments = segments[:-1]
            if parsed.scheme and parsed.netloc:
                root_path = "/" + "/".join(segments) if segments else ""
                root_url = f"{parsed.scheme}://{parsed.netloc}{root_path}"
                if root_url.rstrip("/") != default_root:
                    options["base_url"] = root_url.rstrip("/")
        return types.HttpOptions(**options)

    def _build_google_request_payload(
        self,
        *,
        prompt_text: str,
        reference_assets: list[Asset],
        background_style_assets: list[Asset],
        aspect_ratio: str,
        image_size: str,
    ) -> dict[str, object]:
        """构造仅用于调试落盘的 Google SDK 请求摘要。"""

        contents = [{"type": "text", "text": prompt_text}]
        if reference_assets:
            contents.append({"type": "text", "text": "Product reference images for package identity only."})
            contents.extend(
                {
                    "type": "image_part",
                    "asset_id": asset.asset_id,
                    "filename": asset.filename,
                    "mime_type": asset.mime_type or self._guess_mime_type(Path(asset.local_path)),
                }
                for asset in reference_assets
            )
        if background_style_assets:
            contents.append({"type": "text", "text": "Background and style reference images for atmosphere only."})
            contents.extend(
                {
                    "type": "image_part",
                    "asset_id": asset.asset_id,
                    "filename": asset.filename,
                    "mime_type": asset.mime_type or self._guess_mime_type(Path(asset.local_path)),
                }
                for asset in background_style_assets
            )
        return {
            "transport": "google_official_sdk",
            "model": self.model_id,
            "contents": contents,
            "config": {
                "response_modalities": ["IMAGE"],
                "image_config": {
                    "aspect_ratio": aspect_ratio or self.settings.default_image_aspect_ratio,
                    "image_size": image_size or self.settings.default_image_size,
                },
            },
        }

    def _build_google_contents(
        self,
        *,
        prompt_text: str,
        reference_assets: list[Asset],
        background_style_assets: list[Asset],
    ) -> list[str | types.Part]:
        """组装 Google 官方 SDK 的 contents。"""

        contents: list[str | types.Part] = [prompt_text]
        if reference_assets:
            contents.append(
                "Product reference images: keep package structure, material, color, label placement and brand identity stable. Do not rewrite visible package text."
            )
            self._append_google_asset_parts(contents, reference_assets)
        if background_style_assets:
            contents.append(
                "Background and scene reference images: learn atmosphere, palette and spatial language only. Do not replace the product subject."
            )
            self._append_google_asset_parts(contents, background_style_assets)
        return contents

    def _append_google_asset_parts(
        self,
        contents: list[str | types.Part],
        assets: list[Asset],
    ) -> None:
        """把本地参考图转换成 SDK 的多模态 Part。"""

        for asset in assets:
            asset_path = Path(asset.local_path)
            if not asset.local_path or not asset_path.exists():
                continue
            contents.append(
                types.Part.from_bytes(
                    data=asset_path.read_bytes(),
                    mime_type=asset.mime_type or self._guess_mime_type(asset_path),
                )
            )

    def _resolve_runapi_request_target(self) -> tuple[str, dict[str, str]]:
        """返回 RunAPI 转发通道地址。"""

        return (
            f"{self.settings.runapi_image_base_url.rstrip('/')}/v1/models/{self.model_id}:generateContent",
            {
                "Authorization": f"Bearer {self.settings.runapi_api_key}",
                "Content-Type": "application/json",
            },
        )

    def _build_runapi_request_payload(
        self,
        *,
        prompt_text: str,
        reference_assets: list[Asset],
        background_style_assets: list[Asset],
        aspect_ratio: str,
        image_size: str,
    ) -> dict[str, object]:
        """构造 RunAPI generateContent 请求体。"""

        parts: list[dict[str, object]] = [{"text": prompt_text}]
        if reference_assets:
            parts.append(
                {
                    "text": "以下是产品参考图，只能用于保持包装结构、材质、颜色和品牌识别稳定，不得转写其中可见文字。"
                }
            )
            self._append_runapi_inline_assets(parts, reference_assets)
        if background_style_assets:
            parts.append(
                {
                    "text": "以下是背景与风格参考图，只能用于学习氛围、配色和空间语言，不得替换产品主体。"
                }
            )
            self._append_runapi_inline_assets(parts, background_style_assets)
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

    def _append_runapi_inline_assets(self, parts: list[dict[str, object]], assets: list[Asset]) -> None:
        """把本地资产编码成 RunAPI inlineData。"""

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

    def _extract_google_image_bytes(self, response: types.GenerateContentResponse) -> bytes:
        """从 Google 官方 SDK 响应中提取图片字节。"""

        for part in response.parts or []:
            inline_data = getattr(part, "inline_data", None)
            if inline_data is not None and getattr(inline_data, "data", None):
                data = inline_data.data
                if isinstance(data, bytes):
                    return data
                if isinstance(data, str):
                    return base64.b64decode(data)
                return bytes(data)
            try:
                image = part.as_image()
            except Exception:
                continue
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            return buffer.getvalue()
        raise RuntimeError(f"Google official response did not contain image data: {response}")

    def _extract_runapi_image_bytes(self, response_json: dict[str, object]) -> bytes:
        """从 RunAPI 响应中提取图片字节。"""

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
        raise RuntimeError(f"RunAPI response did not contain image data: {response_json}")

    def _download_generated_file(self, file_uri: str) -> bytes:
        """下载 RunAPI fileUri。"""

        headers: dict[str, str] = {}
        if self.settings.runapi_api_key:
            headers["Authorization"] = f"Bearer {self.settings.runapi_api_key}"
        try:
            with requests.Session() as session:
                session.trust_env = False
                session.proxies.clear()
                response = session.get(file_uri, headers=headers, timeout=self.settings.provider_timeout_seconds)
        except requests.RequestException as exc:
            logger.exception("RunAPI fileUri 下载失败，url=%s error=%s", file_uri, exc)
            raise RuntimeError(f"RunAPI file download failed: {exc}") from exc

        if response.status_code >= 400:
            raise RuntimeError(f"RunAPI file download failed: {response.status_code} {response.text[:1200]}")
        if not response.content:
            raise RuntimeError(f"RunAPI file download returned empty body: {file_uri}")
        return response.content

    def _write_generated_image(self, *, index: int, shot_id: str, image_bytes: bytes, output_dir: Path) -> GeneratedImage:
        """把生成结果保存为任务图片。"""

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
        """详情页允许同时绑定更多产品参考图。"""

        prepared: list[Asset] = []
        for asset in reference_assets or []:
            if not asset.local_path:
                continue
            prepared.append(asset)
            if len(prepared) >= 4:
                break
        return prepared

    def _prepare_background_style_assets(self, background_style_assets: list[Asset] | None) -> list[Asset]:
        """限制背景风格参考图数量。"""

        prepared: list[Asset] = []
        for asset in background_style_assets or []:
            if not asset.local_path:
                continue
            prepared.append(asset)
            if len(prepared) >= 2:
                break
        return prepared

    def _guess_mime_type(self, path: Path) -> str:
        """按文件后缀推断 MIME。"""

        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"
