"""中文字体解析与加载工具。

文件位置：
- `src/services/rendering/font_utils.py`

核心职责：
- 优先加载项目内中文字体文件。
- 在配置字体缺失时，按平台尝试更适合中文的系统字体。
- 返回结构化字体来源信息，避免静默退回到不适合中文的默认字体。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging
import os
from pathlib import Path
import sys

from PIL import ImageFont

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadedFont:
    """描述一次真实可追踪的字体加载结果。"""

    font: ImageFont.FreeTypeFont
    requested_font_path: str
    resolved_font_path: str
    font_source: str
    font_loaded: bool
    fallback_used: bool
    fallback_target: str | None


def load_font(
    font_path: Path,
    font_size: int,
    *,
    project_font_candidates: tuple[Path, ...] = (),
    system_font_candidates: tuple[Path, ...] = (),
) -> LoadedFont:
    """按“项目字体优先、系统中文字体次之”的顺序加载字体。

    说明：
    - 不再静默回退到 `DejaVuSans.ttf` 或 `ImageFont.load_default()`。
    - 如果连合适的系统中文字体都找不到，会直接抛错，让问题在测试和日志里显式暴露。
    """
    requested_font_path = Path(font_path)
    resolved_font_path, font_source, fallback_used, fallback_target = _resolve_font_candidate(
        str(requested_font_path),
        tuple(str(path) for path in project_font_candidates),
        tuple(str(path) for path in system_font_candidates),
    )
    font = _load_truetype_font(resolved_font_path, font_size)
    return LoadedFont(
        font=font,
        requested_font_path=str(requested_font_path),
        resolved_font_path=resolved_font_path,
        font_source=font_source,
        font_loaded=True,
        fallback_used=fallback_used,
        fallback_target=fallback_target,
    )


def _build_candidate_records(
    *,
    requested_font_path: Path,
    project_font_candidates: tuple[Path, ...],
    system_font_candidates: tuple[Path, ...],
) -> list[tuple[Path, str]]:
    """为字体加载生成有序候选列表，并保留来源标签。"""
    records: list[tuple[Path, str]] = []
    seen: set[str] = set()

    def add_candidate(candidate_path: Path, source: str) -> None:
        normalized = _normalize_path_key(candidate_path)
        if normalized in seen:
            return
        seen.add(normalized)
        records.append((candidate_path, source))

    add_candidate(requested_font_path, "configured_font")
    for candidate_path in project_font_candidates:
        add_candidate(candidate_path, "project_font_fallback")

    system_source = _resolve_system_source_name()
    for candidate_path in system_font_candidates:
        add_candidate(candidate_path, system_source)
    return records


@lru_cache(maxsize=64)
def _resolve_font_candidate(
    requested_font_path: str,
    project_font_candidates: tuple[str, ...],
    system_font_candidates: tuple[str, ...],
) -> tuple[str, str, bool, str | None]:
    """解析并缓存当前应使用的字体文件路径与来源。"""
    requested_path = Path(requested_font_path)
    candidate_records = _build_candidate_records(
        requested_font_path=requested_path,
        project_font_candidates=tuple(Path(path) for path in project_font_candidates),
        system_font_candidates=tuple(Path(path) for path in system_font_candidates),
    )

    if not requested_path.exists():
        logger.warning("Configured Chinese font file is missing: %s", requested_path)

    load_errors: list[str] = []
    for candidate_path, source in candidate_records:
        if not candidate_path.exists():
            continue
        try:
            _load_truetype_font(str(candidate_path), 16)
        except OSError as exc:
            load_errors.append(f"{candidate_path}: {exc}")
            logger.warning("Failed to probe font candidate: path=%s, reason=%s", candidate_path, exc)
            continue

        fallback_used = not _same_path(candidate_path, requested_path)
        fallback_target = str(candidate_path) if fallback_used else None
        if fallback_used:
            logger.warning(
                "Chinese font fallback engaged: requested=%s, resolved=%s, source=%s",
                requested_path,
                candidate_path,
                source,
            )
        return str(candidate_path), source, fallback_used, fallback_target

    checked_candidates = [str(path) for path, _ in candidate_records]
    logger.error(
        "No suitable Chinese font could be loaded: requested=%s, checked_candidates=%s, load_errors=%s",
        requested_path,
        checked_candidates,
        load_errors or ["none"],
    )
    raise RuntimeError(
        "No suitable Chinese font available for text rendering. "
        f"requested={requested_path}, checked_candidates={checked_candidates}"
    )


@lru_cache(maxsize=256)
def _load_truetype_font(font_path: str, font_size: int) -> ImageFont.FreeTypeFont:
    """缓存 Pillow 字体对象，避免多 block 多次重复加载同一字号。"""
    return ImageFont.truetype(font_path, font_size)


def _resolve_system_source_name() -> str:
    """返回当前平台对应的系统字体来源标签。"""
    if os.name == "nt":
        return "windows_system_font"
    if sys.platform == "darwin":
        return "macos_system_font"
    return "linux_system_font"


def _same_path(left: Path, right: Path) -> bool:
    """尽量稳定地比较两个路径是否指向同一字体文件。"""
    return _normalize_path_key(left) == _normalize_path_key(right)


def _normalize_path_key(path: Path) -> str:
    """把路径归一化为缓存和去重可用的 key。"""
    try:
        return str(path.resolve()).lower()
    except OSError:
        return str(path).lower()
