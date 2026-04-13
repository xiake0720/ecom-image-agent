"""RunAPI Gemini 3.1 鍥剧墖 provider銆?

鏂囦欢浣嶇疆锛?
- `src/providers/image/runapi_gemini31_image.py`

鏍稿績鑱岃矗锛?
- 灏佽 RunAPI 鐨?Gemini 3.1 Flash Image Preview 鎺ュ彛
- 鏀寔鏂囨湰 + 澶氱粍鍙傝€冨浘鐨勫妯℃€佽姹?
- 鏀寔 v2 `PromptPlanV2` 鍜屽吋瀹瑰眰 `ImagePromptPlan`
- 瑙ｆ瀽杩斿洖涓殑 inlineData base64 鍥剧墖骞惰惤鐩樹负浠诲姟鍥剧墖
"""

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
from backend.engine.domain.prompt_plan_v2 import PromptPlanV2
from backend.engine.domain.usage import ProviderUsageSnapshot, normalize_usage_snapshot
from backend.engine.providers.image.base import BaseImageProvider

logger = logging.getLogger(__name__)

RUNAPI_GEMINI31_MODEL_ID = "gemini-3.1-flash-image-preview"


@dataclass(frozen=True)
class ImageGenerationContext:
    """褰撳墠鍥剧墖鐢熸垚璇锋眰鐨勬渶灏忔墽琛屼笂涓嬫枃銆?""

    generation_mode: str
    provider_alias: str
    model_id: str
    reference_asset_ids: list[str]
    selected_reference_assets: list[Asset]
    background_style_asset_ids: list[str]
    selected_background_style_assets: list[Asset]


class RunApiGemini31ImageProvider(BaseImageProvider):
    """閫氳繃 RunAPI 璋冪敤 Gemini 3.1 鍥剧墖鐢熸垚鎺ュ彛銆?""

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
        """杩斿洖褰撳墠鍥剧墖 provider 鐨勮繍琛屼笂涓嬫枃锛屼究浜?render/QC 璁板綍璋冭瘯淇℃伅銆?""

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
        """兼容旧的 `ImagePromptPlan` 调用方式。"""

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
                "寮€濮嬭皟鐢?Gemini 3.1 鍥剧墖鐢熸垚锛宮ode=legacy-v1, shot_id=%s, reference_count=%s, background_style_count=%s, output_name=%s",
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
                "寮€濮嬭皟鐢?Gemini 3.1 鍥剧墖鐢熸垚锛宮ode=v2, request_mode=%s, shot_id=%s, reference_count=%s, background_style_count=%s, output_name=%s",
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
            images.append(self._write_generated_image(index=index, shot_id=shot.shot_id, image_bytes=image_bytes, output_dir=output_dir))
        self.last_usage = usage
        return GenerationResult(images=images, usage=usage)

    def _compose_v2_prompt_text(self, shot) -> str:
        """鎶?v2 shot 缁撴瀯鍘嬫垚瀹為檯鍙戠粰鍥剧墖妯″瀷鐨勬枃鏈弿杩般€?""

        lines = [shot.render_prompt]
        lines.append(
            f"鍥惧唴鏂囧瓧绛栫暐锛歝opy_strategy={shot.copy_strategy}, text_density={shot.text_density}, should_render_text={str(shot.should_render_text).lower()}"
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
        if not shot.should_render_text or shot.copy_strategy == "none":
            lines.append("鏈浘涓嶅簲涓诲姩鐢熸垚骞垮憡澶у瓧锛岄噸鐐逛繚鐣欑敾闈㈣川鎰熷拰浜у搧缁嗚妭銆?)
        lines.append("骞垮憡鏂囨鍙厑璁镐娇鐢ㄤ笂杩版爣棰樸€佸壇鏍囬銆佸崠鐐癸紝涓ョ杞啓銆佸鐢ㄣ€佹鎷换浣曞弬鑰冨浘鍙鏂囧瓧銆?)
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

        payload = self._build_request_payload(
            prompt_text=prompt_text,
            reference_assets=reference_assets,
            background_style_assets=background_style_assets or [],
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
        self.last_request_payloads[shot_id] = payload
        self.last_usage = ProviderUsageSnapshot.unavailable(request_count=1)
        url = f"{self.settings.runapi_image_base_url.rstrip('/')}/v1/models/{self.model_id}:generateContent"
        logger.info(
            "鍙戦€?Gemini 3.1 鍥剧墖璇锋眰锛宻hot_id=%s, url=%s, aspect_ratio=%s, image_size=%s, reference_count=%s, background_style_count=%s, proxy=%s",
            shot_id,
            url,
            aspect_ratio,
            image_size,
            len(reference_assets),
            len(background_style_assets or []),
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
            logger.exception("Gemini 3.1 鍥剧墖璇锋眰澶辫触锛宻hot_id=%s, error=%s", shot_id, exc)
            raise RuntimeError(f"RunAPI Gemini 3.1 request failed for {shot_id}: {exc}") from exc

        if response.status_code >= 400:
            logger.error(
                "Gemini 3.1 鍥剧墖璇锋眰澶辫触锛宻hot_id=%s, status_code=%s, response=%s",
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
        logger.info(
            "Gemini 3.1 鍥剧墖璇锋眰鎴愬姛锛宻hot_id=%s, elapsed_ms=%s",
            shot_id,
            elapsed_ms,
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
        """鏋勯€犵鍚?Gemini 3.1 generateContent 鐨勮姹備綋銆?""

        parts: list[dict[str, object]] = [{"text": prompt_text}]
        if reference_assets:
            parts.append({"text": "浠ヤ笅鏄骇鍝佸弬鑰冨浘锛屽彧鑳界敤浜庝繚鎸佸寘瑁呯粨鏋勩€佹潗璐ㄣ€侀鑹蹭笌鏍囩涓€鑷达紝涓嶅緱鎻愬彇鍏朵腑鍙鏂囧瓧銆?})
            self._append_inline_assets(parts, reference_assets)
        if background_style_assets:
            parts.append({"text": "浠ヤ笅鏄儗鏅鏍煎弬鑰冨浘锛屽彧鑳界敤浜庡涔犺儗鏅皼鍥淬€佽壊璋冧笌鍦烘櫙璇█锛屼笉寰楁浛鎹骇鍝佸寘瑁咃紝涔熶笉寰楁彁鍙栧叾涓彲瑙佹枃瀛椼€?})
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
        """鎶婂弬鑰冨浘杩藉姞鍒拌姹?parts銆?""

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
        """浠?Gemini 3.1 鍝嶅簲閲屾彁鍙?inlineData 鍥剧墖銆?""

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
        """涓嬭浇 RunAPI 杩斿洖鐨勫浘鐗囨枃浠跺湴鍧€锛屽苟鏄惧紡绂佺敤鐜浠ｇ悊銆?""

        logger.info("妫€娴嬪埌 Gemini 3.1 fileUri 杩斿洖锛屽紑濮嬩笅杞藉浘鐗囨枃浠讹紝url=%s", file_uri)
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
            logger.exception("Gemini 3.1 fileUri 鍥剧墖涓嬭浇澶辫触锛寀rl=%s, error=%s", file_uri, exc)
            raise RuntimeError(f"RunAPI Gemini 3.1 file download failed: {exc}") from exc

        if response.status_code >= 400:
            logger.error(
                "Gemini 3.1 fileUri 鍥剧墖涓嬭浇澶辫触锛宻tatus_code=%s, url=%s, response=%s",
                response.status_code,
                file_uri,
                summarize_text(response.text, limit=240),
            )
            raise RuntimeError(f"RunAPI Gemini 3.1 file download failed: {response.status_code} {response.text[:1200]}")
        if not response.content:
            raise RuntimeError(f"RunAPI Gemini 3.1 file download returned empty body: {file_uri}")
        return response.content

    def _write_generated_image(self, *, index: int, shot_id: str, image_bytes: bytes, output_dir: Path) -> GeneratedImage:
        """鎶婅繑鍥炲浘鐗囧瓧鑺傚啓鍏ヨ緭鍑虹洰褰曪紝骞舵彁鍙栧疄闄呭儚绱犲昂瀵搞€?""

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
        """缁熶竴瑁佸壀鍒版渶澶氫袱寮犱骇鍝佸弬鑰冨浘銆?""

        prepared: list[Asset] = []
        for asset in reference_assets or []:
            if not asset.local_path:
                continue
            prepared.append(asset)
            if len(prepared) >= 2:
                break
        return prepared

    def _prepare_background_style_assets(self, background_style_assets: list[Asset] | None) -> list[Asset]:
        """缁熶竴瑁佸壀鍒版渶澶氫袱寮犺儗鏅鏍煎弬鑰冨浘銆?""

        prepared: list[Asset] = []
        for asset in background_style_assets or []:
            if not asset.local_path:
                continue
            prepared.append(asset)
            if len(prepared) >= 2:
                break
        return prepared

    def _guess_mime_type(self, path: Path) -> str:
        """鏍规嵁鏂囦欢鍚庣紑鎺ㄦ柇鏈€灏忓彲鐢?mime type銆?""

        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"

