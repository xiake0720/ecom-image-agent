from __future__ import annotations

import logging
from pathlib import Path

from src.core.config import Settings
from src.core.logging import (
    attach_task_file_handler,
    detach_task_file_handler,
    get_task_log_path,
    initialize_logging,
    log_context,
)


def test_task_file_log_handler_writes_utf8_log(tmp_path: Path) -> None:
    settings = Settings(log_level="INFO", enable_file_log=True)
    initialize_logging(settings)
    logger = logging.getLogger("tests.unit.logging")

    log_path = attach_task_file_handler("task-log-001", tmp_path, settings=settings)
    assert log_path == get_task_log_path(tmp_path)

    with log_context(task_id="task-log-001", node_name="test_node"):
        logger.info("写入中文日志测试")

    detach_task_file_handler("task-log-001")

    content = log_path.read_text(encoding="utf-8")
    assert "写入中文日志测试" in content
    assert "task_id=task-log-001" in content
    assert "node=test_node" in content
