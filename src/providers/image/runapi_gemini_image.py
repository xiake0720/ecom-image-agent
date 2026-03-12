"""RunAPI Gemini 图片 provider。

该模块位于 `src/providers/image/`，负责封装 RunAPI 提供的
Gemini Image Gen 调用，并把结果保存为当前任务目录中的真实图片文件。

当前模块只负责 provider 层的请求与响应处理：
- 不负责 workflow 节点编排
- 不负责 Pillow 中文后贴字
- 不负责 silent fallback
"""

from __future__ import annotations

import base64
import logging
from time import perf_counter
from pathlib import Path

import requests

from src.core.config import Settings
from src.core.logging import describe_proxy_status, summarize_text
from src.domain.asset import Asset
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.domain.image_prompt_plan import ImagePromptPlan
from src.providers.image.base import BaseImageProvider

logger = logging.getLogger(__name__)


class RunApiGeminiImageProvider(BaseImageProvider):
    """通过 RunAPI 调用 Gemini 图片生成接口。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate_images(
        self,
        plan: ImagePromptPlan,
        *,
        output_dir: Path,
        reference_assets: list[Asset] | None = None,
    ) -> GenerationResult:
        """生成图片并写入现有任务目录。

        Args:
            plan: 结构化图片提示词计划。
            output_dir: 当前任务的 `generated/` 目录。
            reference_assets: 用户上传的参考商品图。

        Returns:
            与现有 schema 兼容的 `GenerationResult`。

        Raises:
            RuntimeError: mock 模式误用、缺失 API key、缺失参考图、
                HTTP 失败或响应中没有图片数据时显式抛错。
        """
        logger.info(
            "开始调用图片模型，provider=RunAPI，mode=%s，model=%s，图片数量=%s，参考图数量=%s，输出目录=%s",
            self.settings.image_provider_mode,
            self.settings.runapi_image_model,
            len(plan.prompts),
            len(reference_assets or []),
            output_dir,
        )
        if self.settings.image_provider_mode == "mock":
            logger.error("调用图片模型失败：当前 provider 模式为 mock，不能使用 RunApiGeminiImageProvider")
            raise RuntimeError("RunApiGeminiImageProvider cannot run in mock mode.")
        if not self.settings.runapi_api_key:
            logger.error("调用图片模型失败：缺少 ECOM_IMAGE_AGENT_RUNAPI_API_KEY")
            raise RuntimeError(
                "ECOM_IMAGE_AGENT_RUNAPI_API_KEY is required when "
                "ECOM_IMAGE_AGENT_IMAGE_PROVIDER_MODE=real."
            )
        if not reference_assets:
            logger.error("调用图片模型失败：真实图片生成至少需要 1 张参考图")
            raise RuntimeError("At least one uploaded reference asset is required for real image generation.")

        output_dir.mkdir(parents=True, exist_ok=True)
        images: list[GeneratedImage] = []
        for index, prompt in enumerate(plan.prompts, start=1):
            width, height = [int(value) for value in prompt.output_size.split("x", maxsplit=1)]
            started_at = perf_counter()
            logger.info(
                "开始生成图片，provider=RunAPI，model=%s，shot_id=%s，尺寸=%s，prompt摘要=%s",
                self.settings.runapi_image_model,
                prompt.shot_id,
                prompt.output_size,
                summarize_text(prompt.prompt, limit=120),
            )
            image_bytes = self._generate_single(prompt.prompt, reference_assets)
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
                "图片生成成功，provider=RunAPI，model=%s，shot_id=%s，耗时=%sms，输出=%s",
                self.settings.runapi_image_model,
                prompt.shot_id,
                int((perf_counter() - started_at) * 1000),
                output_path,
            )
        logger.info("图片模型调用完成，provider=RunAPI，model=%s，成功生成=%s 张", self.settings.runapi_image_model, len(images))
        return GenerationResult(images=images)

    def _generate_single(self, prompt: str, reference_assets: list[Asset]) -> bytes:
        """执行单次图片请求，并从响应中提取二进制图片数据。"""
        parts = [{"text": prompt}]
        for asset in reference_assets:
            path = Path(asset.local_path)
            if not path.exists():
                continue
            mime_type = asset.mime_type or self._guess_mime_type(path)
            # 参考图作为内联多模态输入发送，保持当前“以商品图为参考”的实现边界。
            parts.append(
                {
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": base64.b64encode(path.read_bytes()).decode("utf-8"),
                    }
                }
            )

        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }
        url = (
            f"{self.settings.runapi_image_base_url.rstrip('/')}"
            f"/v1beta/models/{self.settings.runapi_image_model}:generateContent"
        )
        logger.info(
            "发送图片模型请求，provider=RunAPI，model=%s，url=%s，参考图数量=%s，代理状态=%s",
            self.settings.runapi_image_model,
            url,
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
            logger.exception(
                "图片模型调用失败：provider=RunAPI，model=%s，原因=网络请求异常，代理状态=%s，错误=%s",
                self.settings.runapi_image_model,
                describe_proxy_status(),
                exc,
            )
            raise
        if response.status_code >= 400:
            logger.error(
                "图片模型调用失败：provider=RunAPI，model=%s，状态码=%s，耗时=%sms，响应摘要=%s",
                self.settings.runapi_image_model,
                response.status_code,
                int((perf_counter() - started_at) * 1000),
                summarize_text(response.text, limit=240),
            )
            raise RuntimeError(
                f"RunAPI image request failed: {response.status_code} {response.text[:1200]}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            logger.exception(
                "图片模型调用失败：provider=RunAPI，model=%s，原因=响应不是合法 JSON，响应摘要=%s",
                self.settings.runapi_image_model,
                summarize_text(response.text, limit=240),
            )
            raise RuntimeError(f"RunAPI image response is not valid JSON: {response.text[:1200]}") from exc
        logger.info(
            "图片模型请求返回成功，provider=RunAPI，model=%s，耗时=%sms",
            self.settings.runapi_image_model,
            int((perf_counter() - started_at) * 1000),
        )
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return base64.b64decode(inline["data"])
        # 当前项目不允许在图片链路失败时偷偷回退到 mock 结果。
        logger.error(
            "图片模型调用失败：provider=RunAPI，model=%s，原因=响应中未找到图片数据，响应摘要=%s",
            self.settings.runapi_image_model,
            summarize_text(str(data), limit=240),
        )
        raise RuntimeError(f"RunAPI image response did not contain inline image data: {data}")

    def _guess_mime_type(self, path: Path) -> str:
        """根据文件后缀推断最小可用 mime type。"""
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"
