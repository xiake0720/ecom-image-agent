"""任务元数据仓储。

设计意图：当前阶段使用本地 JSON 持久化，接口层无需关心存储细节，后续可替换为 SQLite/数据库。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from backend.core.config import get_settings
from backend.schemas.task import TaskSummary


class TaskRepository:
    """管理任务索引与单任务元数据。"""

    def __init__(self) -> None:
        settings = get_settings()
        self.root = settings.storage_root / "tasks"
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"

    def list_tasks(self) -> list[TaskSummary]:
        """读取任务列表。

        输出按创建时间倒序，便于任务记录页展示最新任务。
        """

        rows = self._read_index()
        rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return [TaskSummary.model_validate(row) for row in rows]

    def get_task(self, task_id: str) -> TaskSummary | None:
        """根据 task_id 查询任务。"""

        for row in self._read_index():
            if row.get("task_id") == task_id:
                return TaskSummary.model_validate(row)
        return None

    def save_task(self, task: TaskSummary) -> None:
        """新增或更新任务索引。"""

        rows = self._read_index()
        exists = False
        for idx, row in enumerate(rows):
            if row.get("task_id") == task.task_id:
                rows[idx] = task.model_dump(mode="json")
                exists = True
                break
        if not exists:
            rows.append(task.model_dump(mode="json"))
        self.index_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def create_task_summary(
        self,
        *,
        task_id: str,
        task_type: str,
        status: str,
        title: str,
        platform: str,
        result_path: str,
    ) -> TaskSummary:
        """构造统一任务摘要对象。"""

        now = datetime.utcnow()
        return TaskSummary(
            task_id=task_id,
            task_type=task_type,
            status=status,
            created_at=now,
            updated_at=now,
            title=title,
            platform=platform,
            result_path=result_path,
        )

    def _read_index(self) -> list[dict[str, object]]:
        """读取索引文件，不存在时返回空列表。"""

        if not self.index_path.exists():
            return []
        return json.loads(self.index_path.read_text(encoding="utf-8"))
