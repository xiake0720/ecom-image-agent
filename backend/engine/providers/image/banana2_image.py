"""Banana2 鍥剧墖 provider銆?""

from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
import logging
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse

from google import genai
from google.genai import types
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
    """褰撳墠 Banana2 璇锋眰鐨勬渶灏忔墽琛屼笂涓嬫枃銆?""

    generation_mode: str
    provider_alias: str
    model_id: str
    transport: str
    reference_asset_ids: list[str]
    selected_reference_assets: list[Asset]
    background_style_asset_ids: list[str]
    selected_background_style_assets: list[Asset]


class Banana2ImageProvider(BaseImageProvider):
    """缁熶竴鍥剧墖 provider銆?
    褰撳墠 real 妯″紡浼樺厛閫氳繃 Google 瀹樻柟 `google.genai` SDK 璋冪敤 Gemini 鍥剧墖妯″瀷銆?    鑻ユ湭閰嶇疆 Google API Key锛屽垯鍥為€€鍒扮幇鏈?RunAPI 杞彂閫氶亾銆?    """

    provider_alias = "banana2"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_id = settings.resolve_image_model_selection().model_id
        self.last_request_payloads: dict[str, dict[str, object]] = {}
        self.last_reference_asset_ids: list[str] = []
        self.last_background_style_asset_ids: list[str] = []
        self.last_usage: ProviderUsageSnapshot | None = None
        self._google_client: genai.Client | None = None

    def resolve_generation_context(
        self,
        *,
        reference_assets: list[Asset] | None = None,
        background_style_assets: list[Asset] | None = None,
    ) -> Banana2GenerationContext:
        """杩斿洖褰撳墠 provider 鐨勮繍琛屼笂涓嬫枃銆?""

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
        """鍏煎鏃х殑 `ImagePromptPlan` 璋冪敤鏂瑰紡銆?""

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
            images.append(self._write_generated_image(index=index, shot_id=prompt.shot_id, image_bytes=image_bytes, output_dir=output_dir))
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
        """鎸?v2 prompt plan 閫愬紶鐢熸垚骞惰惤鐩樸€?""

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
            images.append(self._write_generated_image(index=index, shot_id=shot.shot_id, image_bytes=image_bytes, output_dir=output_dir))
        self.last_usage = usage
        return GenerationResult(images=images, usage=usage)

    def _compose_v2_prompt_text(self, shot: PromptShot) -> str:
        """鎶?v2 shot 鏀跺彛涓烘渶缁堟枃鏈寚浠ゃ€?""

        lines = [shot.render_prompt]
        lines.append(
            "鍥惧唴鏂囧瓧绛栫暐锛?
            f"copy_strategy={shot.copy_strategy}, text_density={shot.text_density}, should_render_text={str(shot.should_render_text).lower()}"
        )
        if shot.should_render_text and shot.title_copy:
            lines.append(f"涓绘爣棰橈細{shot.title_copy}")
        if shot.should_render_text and shot.subtitle_copy:
            lines.append(f"鍓爣棰橈細{shot.subtitle_copy}")
        if shot.should_render_text and shot.selling_points_for_render:
            lines.append(f"鍗栫偣锛歿'锛?.join(shot.selling_points_for_render)}")
        if shot.layout_hint:
            lines.append(f"鐗堝紡鎻愮ず锛歿shot.layout_hint}")
        if shot.typography_hint:
            lines.append(f"鏂囧瓧灞傜骇锛歿shot.typography_hint}")
        if shot.subject_occupancy_ratio:
            lines.append(f"涓讳綋鍗犳瘮锛氱害 {int(shot.subject_occupancy_ratio * 100)}%")
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
            "鍙戦€?Banana2 鍥剧墖璇锋眰锛宻hot_id=%s transport=%s model=%s aspect_ratio=%s image_size=%s reference_count=%s background_style_count=%s proxy=%s",
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
                logger.exception("Google 瀹樻柟鍥剧墖璇锋眰澶辫触锛宻hot_id=%s error=%s", shot_id, exc)
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
                logger.exception("RunAPI 鍥剧墖璇锋眰澶辫触锛宻hot_id=%s error=%s", shot_id, exc)
                raise RuntimeError(f"RunAPI image request failed for {shot_id}: {exc}") from exc
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        usage = usage.model_copy(update={"latency_ms": elapsed_ms})
        self.last_usage = usage
        logger.info(
            "Banana2 鍥剧墖璇锋眰鎴愬姛锛宻hot_id=%s transport=%s elapsed_ms=%s",
            shot_id,
            transport,
            elapsed_ms,
        )
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
                "RunAPI 鍥剧墖璇锋眰澶辫触锛宻hot_id=%s status_code=%s response=%s aspect_ratio=%s image_size=%s",
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
        """浼樺厛浣跨敤 Google 瀹樻柟 SDK锛岀己澶辨椂鍥為€€鍒?RunAPI銆?""

        if self.settings.google_api_key:
            return "google_official_sdk"
        if self.settings.runapi_api_key:
            return "runapi"
        raise RuntimeError(
            "Banana2 real mode requires ECOM_IMAGE_AGENT_GOOGLE_API_KEY or ECOM_IMAGE_AGENT_RUNAPI_API_KEY."
        )

    def _get_google_client(self) -> genai.Client:
        """鎳掑姞杞?Google 瀹樻柟 SDK client銆?""

        if not self.settings.google_api_key:
            raise RuntimeError("ECOM_IMAGE_AGENT_GOOGLE_API_KEY is required for Google official SDK transport.")
        if self._google_client is None:
            self._google_client = genai.Client(
                api_key=self.settings.google_api_key,
                http_options=self._build_google_http_options(),
            )
        return self._google_client

    def _build_google_http_options(self) -> types.HttpOptions:
        """鎶婄幇鏈夐厤缃槧灏勫埌 Google 瀹樻柟 SDK 鐨?http options銆?""

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
        """鏋勯€犱粎鐢ㄤ簬璋冭瘯钀界洏鐨?Google SDK 璇锋眰鎽樿銆?""

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
        """缁勮 Google 瀹樻柟 SDK 鐨?contents銆?""

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
        """鎶婃湰鍦板弬鑰冨浘杞垚 SDK 鐨勫妯℃€?Part銆?""

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
        """杩斿洖 RunAPI 杞彂閫氶亾鍦板潃銆?""

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
        """鏋勯€?RunAPI generateContent 璇锋眰浣撱€?""

        parts: list[dict[str, object]] = [{"text": prompt_text}]
        if reference_assets:
            parts.append(
                {
                    "text": "浠ヤ笅鏄骇鍝佸弬鑰冨浘锛屽彧鑳界敤浜庝繚鎸佸寘瑁呯粨鏋勩€佹潗璐ㄣ€侀鑹蹭笌鍝佺墝璇嗗埆涓€鑷达紝涓嶅緱杞啓鍏朵腑鍙鏂囧瓧銆?
                }
            )
            self._append_runapi_inline_assets(parts, reference_assets)
        if background_style_assets:
            parts.append(
                {
                    "text": "浠ヤ笅鏄儗鏅笌鍦烘櫙鍙傝€冨浘锛屽彧鑳界敤浜庡涔犳皼鍥淬€佽壊璋冧笌绌洪棿璇█锛屼笉寰楁浛鎹骇鍝佷富浣撱€?
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
        """鎶婃湰鍦拌祫浜х紪鐮佹垚 RunAPI inlineData銆?""

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
        """浠?Google 瀹樻柟 SDK 鍝嶅簲涓彁鍙栧浘鐗囧瓧鑺傘€?""

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
        """浠?RunAPI 鍝嶅簲涓彁鍙栧浘鐗囧瓧鑺傘€?""

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
        """涓嬭浇 RunAPI fileUri銆?""

        headers: dict[str, str] = {}
        if self.settings.runapi_api_key:
            headers["Authorization"] = f"Bearer {self.settings.runapi_api_key}"
        try:
            with requests.Session() as session:
                session.trust_env = False
                session.proxies.clear()
                response = session.get(file_uri, headers=headers, timeout=self.settings.provider_timeout_seconds)
        except requests.RequestException as exc:
            logger.exception("RunAPI fileUri 涓嬭浇澶辫触锛寀rl=%s error=%s", file_uri, exc)
            raise RuntimeError(f"RunAPI file download failed: {exc}") from exc

        if response.status_code >= 400:
            raise RuntimeError(f"RunAPI file download failed: {response.status_code} {response.text[:1200]}")
        if not response.content:
            raise RuntimeError(f"RunAPI file download returned empty body: {file_uri}")
        return response.content

    def _write_generated_image(self, *, index: int, shot_id: str, image_bytes: bytes, output_dir: Path) -> GeneratedImage:
        """鎶婄敓鎴愮粨鏋滀繚瀛樹负浠诲姟鍥剧墖銆?""

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
        """detail 椤靛厑璁稿悓鏃剁粦瀹氭洿澶氫骇鍝佸弬鑰冨浘銆?""

        prepared: list[Asset] = []
        for asset in reference_assets or []:
            if not asset.local_path:
                continue
            prepared.append(asset)
            if len(prepared) >= 4:
                break
        return prepared

    def _prepare_background_style_assets(self, background_style_assets: list[Asset] | None) -> list[Asset]:
        """闄愬埗鑳屾櫙椋庢牸鍥炬暟閲忋€?""

        prepared: list[Asset] = []
        for asset in background_style_assets or []:
            if not asset.local_path:
                continue
            prepared.append(asset)
            if len(prepared) >= 2:
                break
        return prepared

    def _guess_mime_type(self, path: Path) -> str:
        """鎸夋枃浠跺悗缂€鎺ㄦ柇 MIME銆?""

        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"


