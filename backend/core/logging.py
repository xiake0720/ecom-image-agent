"""FastAPI backend logging initialization."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from backend.core.config import PROJECT_ROOT, get_settings


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DEFAULT_LOG_LEVEL = "INFO"
LOG_FILE_MAX_BYTES = 10 * 1024 * 1024
LOG_FILE_BACKUP_COUNT = 5

_STANDARD_LOG_RECORD_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


class JsonLogFormatter(logging.Formatter):
    """Format log records as compact JSON for container log collectors."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_RECORD_ATTRS or key.startswith("_"):
                continue
            payload[key] = _json_safe(value)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging() -> None:
    """Initialize global logging for API, worker, access, and SQLAlchemy logs."""

    settings = get_settings()
    level = _parse_log_level(settings.log_level)
    formatter: logging.Formatter
    if settings.log_json:
        formatter = JsonLogFormatter()
    else:
        formatter = logging.Formatter(LOG_FORMAT)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    _remove_ecom_handlers(root_logger)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    console_handler._ecom_backend_handler = True  # type: ignore[attr-defined]
    root_logger.addHandler(console_handler)

    if settings.log_file_enabled:
        log_file_path = _resolve_log_file_path(settings.log_file_path)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=LOG_FILE_MAX_BYTES,
            backupCount=LOG_FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        file_handler._ecom_backend_handler = True  # type: ignore[attr-defined]
        root_logger.addHandler(file_handler)

    _configure_named_loggers(level=level, http_access=settings.log_http_access, sqlalchemy=settings.log_sqlalchemy)


def format_log_event(event: str, **fields: Any) -> str:
    """Build a text log message that keeps structured fields visible outside JSON mode."""

    if not fields:
        return event
    parts = [event]
    for key, value in fields.items():
        parts.append(f"{key}={_text_safe(value)}")
    return " ".join(parts)


def _configure_named_loggers(*, level: int, http_access: bool, sqlalchemy: bool) -> None:
    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("uvicorn").propagate = True

    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("uvicorn.error").propagate = True

    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.setLevel(logging.INFO if http_access else logging.WARNING)
    uvicorn_access_logger.propagate = False
    uvicorn_access_logger.handlers.clear()

    celery_logger = logging.getLogger("celery")
    celery_logger.setLevel(level)
    celery_logger.propagate = True

    sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
    sqlalchemy_logger.setLevel(logging.INFO if sqlalchemy else logging.WARNING)
    sqlalchemy_logger.propagate = True


def _remove_ecom_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        if getattr(handler, "_ecom_backend_handler", False):
            logger.removeHandler(handler)
            handler.close()


def _parse_log_level(value: str) -> int:
    normalized = (value or DEFAULT_LOG_LEVEL).strip().upper()
    return getattr(logging, normalized, logging.INFO)


def _resolve_log_file_path(path: Path) -> Path:
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _text_safe(value: Any) -> str:
    if value is None:
        return "-"
    text = str(value)
    if not text:
        return "-"
    if any(char.isspace() for char in text):
        return json.dumps(text, ensure_ascii=False)
    return text
