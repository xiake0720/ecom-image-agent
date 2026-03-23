"""RunAPI Gemini 3.1 图片 provider。

文件位置：
- `src/providers/image/runapi_gemini31_image.py`

核心职责：
- 封装 RunAPI 的 Gemini 3.1 Flash Image Preview 接口
- 支持 text + inlineData 的多模态请求
- 支持 v2 `PromptPlanV2` 和兼容层 `ImagePromptPlan`
- 解析返回中的 inlineData base64 图片并落盘为任务图片
"""

from __future__ import annotations

import base64
from io import BytesIO
import logging
from pathlib import Path
from time import perf_counter

from PIL import Image
import requests

from src.core.config import Settings
from src.core.logging import describe_proxy_status, summarize_text
from src.domain.asset import Asset
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.domain.image_prompt_plan import ImagePromptPlan
from src.domain.prompt_plan_v2 import PromptPlanV2
from src.providers.image.base import BaseImageProvider
from src.providers.image.routed_image import ImageGenerationContext

logger = logging.getLogger(__name__)


RUNAPI_GEMINI31_MODEL_ID = "gemini-3.1-flash-image-preview"


class RunApiGemini31ImageProvider(BaseImageProvider):
    """通过 RunAPI 调用 Gemini 3.1 图片生成接口。

    设计说明：
    - 这个 provider 是 v2 直出图内文案的主入口，因此同时承担
      `PromptPlanV2 -> HTTP 请求 -> 图片落盘` 三段职责。
    - 旧链路仍然可能通过 router 把它当作兼容层 provider 使用，
      所以保留了 `generate_images()`，避免强迫旧节点一次性改完。
    - 对外统一返回 `GenerationResult`，这样 render/QC/finalize 不需要
      再感知 Gemini 3.1 的原始响应格式。
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # 这个 provider 既可能作为主 image provider 使用，也可能作为
        # DashScope 路由下的 image_edit provider 使用，因此不能直接复用
        # 全局 image_model 默认值，否则会把 Wanx 默认模型误带进来。
        if settings.resolve_image_provider_route().alias == "runapi_gemini31":
            self.model_id = settings.resolve_image_model_selection().model_id
        elif settings.resolve_image_edit_provider_route().alias == "runapi_gemini31":
            self.model_id = settings.resolve_image_edit_model_selection().model_id
        else:
            self.model_id = RUNAPI_GEMINI31_MODEL_ID
        self.last_request_payloads: dict[str, dict[str, object]] = {}
        self.last_reference_asset_ids: list[str] = []

    def resolve_generation_context(self, *, reference_assets: list[Asset] | None = None) -> ImageGenerationContext:
        """返回当前图片 provider 的运行上下文，便于 render/QC 记录调试信息。"""
        prepared_assets = self._prepare_reference_assets(reference_assets)
        return ImageGenerationContext(
            generation_mode="t2i",
            provider_alias="runapi_gemini31",
            model_id=self.model_id,
            reference_asset_ids=[asset.asset_id for asset in prepared_assets],
            selected_reference_assets=prepared_assets,
        )

    def generate_images(
        self,
        plan: ImagePromptPlan,
        *,
        output_dir: Path,
        reference_assets: list[Asset] | None = None,
    ) -> GenerationResult:
        """兼容旧的 `ImagePromptPlan` 调用方式，按默认比例和尺寸发起请求。

        上下游关系：
        - 上游通常是 v1 的 `render_images`
        - 下游统一回到 `GenerationResult`
        - 这里不做旧链路 schema 改造，只做最小兼容
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        prepared_assets = self._prepare_reference_assets(reference_assets)
        self.last_reference_asset_ids = [asset.asset_id for asset in prepared_assets]
        images: list[GeneratedImage] = []
        for index, prompt in enumerate(plan.prompts, start=1):
            prompt_text = prompt.edit_instruction or prompt.prompt
            logger.info(
                "开始调用 Gemini 3.1 图片生成，mode=legacy-v1, shot_id=%s, reference_count=%s, output_name=%s",
                prompt.shot_id,
                len(prepared_assets),
                f"{index:02d}_{prompt.shot_id}.png",
            )
            image_bytes = self._generate_single(
                shot_id=prompt.shot_id,
                prompt_text=prompt_text,
                reference_assets=prepared_assets,
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
    ) -> GenerationResult:
        """按 v2 prompt plan 逐张生图并落盘。

        为什么逐张调用：
        - v2 需要对“单张图直出失败”做 overlay fallback
        - 如果整套图一次请求，失败时很难只重做某一张
        - 逐张执行虽然更慢，但更符合当前 PR 的可追踪和可回退目标
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        prepared_assets = self._prepare_reference_assets(reference_assets)
        self.last_reference_asset_ids = [asset.asset_id for asset in prepared_assets]
        images: list[GeneratedImage] = []
        for index, shot in enumerate(prompt_plan.shots, start=1):
            request_mode = "multimodal_t2i_with_refs" if prepared_assets else "t2i_text_only"
            logger.info(
                "开始调用 Gemini 3.1 图片生成，mode=v2, request_mode=%s, shot_id=%s, reference_count=%s, output_name=%s",
                request_mode,
                shot.shot_id,
                len(prepared_assets),
                f"{index:02d}_{shot.shot_id}.png",
            )
            prompt_text = self._compose_v2_prompt_text(shot)
            image_bytes = self._generate_single(
                shot_id=shot.shot_id,
                prompt_text=prompt_text,
                reference_assets=prepared_assets,
                aspect_ratio=shot.aspect_ratio,
                image_size=shot.image_size,
            )
            images.append(self._write_generated_image(index=index, shot_id=shot.shot_id, image_bytes=image_bytes, output_dir=output_dir))
        return GenerationResult(images=images)

    def _compose_v2_prompt_text(self, shot) -> str:
        """把 v2 shot 结构压成实际发给图片模型的文本描述。

        这里故意不只传 `render_prompt`，而是把标题、副标题、版式提示一起
        下发给图片模型。这样 v2 才能真正尝试“图内直接带字”。
        """
        lines = [shot.render_prompt]
        if shot.title_copy:
            lines.append(f"主标题：{shot.title_copy}")
        if shot.subtitle_copy:
            lines.append(f"副标题：{shot.subtitle_copy}")
        if shot.layout_hint:
            lines.append(f"版式提示：{shot.layout_hint}")
        return "\n".join(lines).strip()

    def _generate_single(
        self,
        *,
        shot_id: str,
        prompt_text: str,
        reference_assets: list[Asset],
        aspect_ratio: str,
        image_size: str,
    ) -> bytes:
        """执行单次图片生成请求，并从响应中提取图片字节。

        失败边界：
        - 请求失败：抛 RuntimeError，让 `render_images` 决定是否进入 fallback
        - 响应不是 JSON：直接报错，不做静默吞掉
        - 响应没有图片：直接报错，避免写出空文件污染任务目录
        """
        if self.settings.image_provider_mode == "mock":
            raise RuntimeError("RunApiGemini31ImageProvider cannot run in mock mode.")
        if not self.settings.runapi_api_key:
            raise RuntimeError("ECOM_IMAGE_AGENT_RUNAPI_API_KEY is required when using runapi_gemini31.")

        payload = self._build_request_payload(
            prompt_text=prompt_text,
            reference_assets=reference_assets,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
        self.last_request_payloads[shot_id] = payload
        url = f"{self.settings.runapi_image_base_url.rstrip('/')}/v1/models/{self.model_id}:generateContent"
        logger.info(
            "发送 Gemini 3.1 图片请求，shot_id=%s, url=%s, aspect_ratio=%s, image_size=%s, reference_count=%s, proxy=%s",
            shot_id,
            url,
            aspect_ratio,
            image_size,
            len(reference_assets),
            describe_proxy_status(),
        )
        started_at = perf_counter()
        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.settings.runapi_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.settings.provider_timeout_seconds,
            )
        except requests.RequestException as exc:
            logger.exception("Gemini 3.1 图片请求失败，shot_id=%s, error=%s", shot_id, exc)
            raise RuntimeError(f"RunAPI Gemini 3.1 request failed for {shot_id}: {exc}") from exc

        if response.status_code >= 400:
            logger.error(
                "Gemini 3.1 图片请求失败，shot_id=%s, status_code=%s, response=%s",
                shot_id,
                response.status_code,
                summarize_text(response.text, limit=240),
            )
            raise RuntimeError(f"RunAPI Gemini 3.1 request failed: {response.status_code} {response.text[:1200]}")

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f"RunAPI Gemini 3.1 response is not valid JSON: {response.text[:1200]}") from exc

        logger.info(
            "Gemini 3.1 图片请求成功，shot_id=%s, elapsed_ms=%s",
            shot_id,
            int((perf_counter() - started_at) * 1000),
        )
        return self._extract_image_bytes(data)

    def _build_request_payload(
        self,
        *,
        prompt_text: str,
        reference_assets: list[Asset],
        aspect_ratio: str,
        image_size: str,
    ) -> dict[str, object]:
        """构造符合 Gemini 3.1 generateContent 的请求体。

        结构约定：
        - 第一段 `text` 一定放完整执行 prompt
        - 后续 `inlineData` 只放经过筛选的 1~2 张参考图
        - `aspectRatio / imageSize` 由 v2 prompt plan 显式传入，避免 provider
          自己猜尺寸
        """
        parts: list[dict[str, object]] = [{"text": prompt_text}]
        for asset in reference_assets:
            asset_path = Path(asset.local_path)
            if not asset.local_path or not asset_path.exists():
                continue
            # 参考图在当前阶段只允许做“弱指导”，不在这里额外叠加业务逻辑，
            # 避免 provider 层变成隐式 prompt builder。
            parts.append(
                {
                    "inlineData": {
                        "mimeType": asset.mime_type or self._guess_mime_type(asset_path),
                        "data": base64.b64encode(asset_path.read_bytes()).decode("utf-8"),
                    }
                }
            )
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

    def _extract_image_bytes(self, response_json: dict[str, object]) -> bytes:
        """从 Gemini 3.1 响应里提取 inlineData 图片。

        这里显式只认图片字节，不接受 provider 返回“半成功”状态。
        这样可以保证任务目录里只落真实可用图片。
        """
        for candidate in response_json.get("candidates", []):
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return base64.b64decode(inline["data"])
        raise RuntimeError(f"RunAPI Gemini 3.1 response did not contain inline image data: {response_json}")

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
        """统一裁剪到最多两张参考图，并过滤掉无本地路径资产。

        为什么限制 2 张：
        - 当前业务固定是包装白底图 + 内部细节图
        - 超过 2 张会明显增加请求体体积和不确定性
        - 现阶段优先保证稳定性，不做更复杂的多图混合策略
        """
        prepared: list[Asset] = []
        for asset in reference_assets or []:
            if not asset.local_path:
                continue
            prepared.append(asset)
            if len(prepared) >= 2:
                break
        return prepared

    def _guess_mime_type(self, path: Path) -> str:
        """根据文件后缀推断最小可用 mime type。"""
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"
