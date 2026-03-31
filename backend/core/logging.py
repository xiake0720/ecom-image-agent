"""FastAPI 日志初始化。

设计意图：为请求日志、任务日志、异常日志提供统一格式，便于排查链路问题。
"""

from __future__ import annotations

import logging


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging() -> None:
    """初始化全局 logging。

    输入：无。
    输出：标准库 logging 全局配置副作用。
    """

    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
