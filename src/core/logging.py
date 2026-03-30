"""统一日志初始化与任务级文件日志能力。

文件位置：
- `src/core/logging.py`

核心职责：
- 初始化控制台日志
- 注入 `task_id` / `node_name` 上下文
- 为单个任务挂载 `workflow.log`
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import contextmanager
from contextvars import ContextVar, Token
from pathlib import Path
from threading import RLock
from typing import Iterator

from src.core.config import Settings, get_settings

_DEFAULT_TASK_ID = "-"
_DEFAULT_NODE_NAME = "-"
_TASK_CONTEXT: ContextVar[str] = ContextVar("ecom_task_id", default=_DEFAULT_TASK_ID)
_NODE_CONTEXT: ContextVar[str] = ContextVar("ecom_node_name", default=_DEFAULT_NODE_NAME)
_INIT_LOCK = RLock()
_TASK_FILE_HANDLERS: dict[str, logging.Handler] = {}
_STARTUP_LOGGED = False


class _ContextDefaultsFilter(logging.Filter):
    """为日志记录补齐 task_id 与 node_name。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.task_id = getattr(record, "task_id", None) or _TASK_CONTEXT.get()
        record.node_name = getattr(record, "node_name", None) or _NODE_CONTEXT.get()
        return True


def _build_formatter() -> logging.Formatter:
    """构造统一日志格式。"""

    return logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | task_id=%(task_id)s | node=%(node_name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _resolve_log_level(level_name: str) -> int:
    """把字符串日志级别转换为 logging 常量。"""

    normalized = str(level_name or "INFO").upper()
    return getattr(logging, normalized, logging.INFO)


def initialize_logging(settings: Settings | None = None) -> None:
    """初始化控制台日志，重复调用时保持幂等。"""

    settings = settings or get_settings()
    level = _resolve_log_level(settings.log_level)
    formatter = _build_formatter()

    with _INIT_LOCK:
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        console_handler = next(
            (handler for handler in root_logger.handlers if getattr(handler, "_ecom_console_handler", False)),
            None,
        )
        if console_handler is None:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler._ecom_console_handler = True  # type: ignore[attr-defined]
            console_handler.addFilter(_ContextDefaultsFilter())
            root_logger.addHandler(console_handler)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)


def get_task_log_path(task_dir: str | Path) -> Path:
    """返回任务级日志文件路径。"""

    return Path(task_dir) / "workflow.log"


def attach_task_file_handler(
    task_id: str,
    task_dir: str | Path,
    *,
    settings: Settings | None = None,
) -> Path | None:
    """为指定任务挂载 UTF-8 文件日志处理器。"""

    settings = settings or get_settings()
    if not settings.enable_file_log:
        return None

    initialize_logging(settings)
    log_path = get_task_log_path(task_dir)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with _INIT_LOCK:
        if task_id in _TASK_FILE_HANDLERS:
            return log_path
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setLevel(_resolve_log_level(settings.log_level))
        handler.setFormatter(_build_formatter())
        handler.addFilter(_ContextDefaultsFilter())
        logging.getLogger().addHandler(handler)
        _TASK_FILE_HANDLERS[task_id] = handler
    return log_path


def detach_task_file_handler(task_id: str) -> None:
    """移除并关闭任务级文件日志处理器。"""

    with _INIT_LOCK:
        handler = _TASK_FILE_HANDLERS.pop(task_id, None)
        if handler is None:
            return
        logging.getLogger().removeHandler(handler)
        handler.close()


@contextmanager
def log_context(*, task_id: str | None = None, node_name: str | None = None) -> Iterator[None]:
    """在当前上下文中注入 task_id 与 node_name。"""

    task_token: Token[str] | None = None
    node_token: Token[str] | None = None
    try:
        if task_id is not None:
            task_token = _TASK_CONTEXT.set(task_id)
        if node_name is not None:
            node_token = _NODE_CONTEXT.set(node_name)
        yield
    finally:
        if node_token is not None:
            _NODE_CONTEXT.reset(node_token)
        if task_token is not None:
            _TASK_CONTEXT.reset(task_token)


def summarize_text(text: str, limit: int = 160) -> str:
    """返回截断后的文本摘要。"""

    if len(text) <= limit:
        return text
    return f"{text[:limit]}...(截断，总长 {len(text)})"


def get_proxy_env_names() -> list[str]:
    """返回当前进程中已启用的代理环境变量名。"""

    proxy_names = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
    return [name for name in proxy_names if os.getenv(name)]


def describe_proxy_status() -> str:
    """返回代理状态描述。"""

    proxy_names = get_proxy_env_names()
    if not proxy_names:
        return "未启用"
    return f"已启用（{', '.join(proxy_names)}）"


def log_application_startup(settings: Settings | None = None) -> None:
    """输出应用启动阶段的关键日志。"""

    global _STARTUP_LOGGED

    settings = settings or get_settings()
    initialize_logging(settings)

    with _INIT_LOCK:
        if _STARTUP_LOGGED:
            return
        _STARTUP_LOGGED = True

    logger = logging.getLogger(__name__)
    debug_summary = settings.build_debug_summary()
    logger.info("应用启动成功，Python=%s，env=%s", sys.version.split()[0], settings.env)
    logger.info(
        "当前路由：text=%s(%s)，image=%s(%s)，overlay_fallback=%s",
        debug_summary["text_provider"],
        debug_summary["text_model"],
        debug_summary["image_provider"],
        debug_summary["image_model"],
        debug_summary["overlay_fallback"],
    )
    logger.info(
        "默认业务参数：platform=%s，shot_count=%s，aspect_ratio=%s，image_size=%s",
        debug_summary["platform"],
        debug_summary["shot_count"],
        debug_summary["aspect_ratio"],
        debug_summary["image_size"],
    )
    logger.info("输出目录：tasks=%s", settings.tasks_dir)
    logger.info("代理状态：%s", describe_proxy_status())
