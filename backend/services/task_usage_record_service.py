"""任务用量记录写入服务。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import uuid

from backend.db.models.task import TaskUsageRecord
from backend.db.session import get_async_session_factory
from backend.repositories.db.task_usage_record_repository import TaskUsageRecordRepository


@dataclass(frozen=True, slots=True)
class TaskUsageRecordCreate:
    """写入 `task_usage_records` 的最小载荷。"""

    task_id: str
    user_id: str
    provider_type: str
    provider_name: str
    action_name: str
    model_name: str | None = None
    request_units: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    image_count: int | None = None
    latency_ms: int | None = None
    cost_amount: Decimal | None = None
    cost_currency: str = "CNY"
    success: bool = True
    error_code: str | None = None
    metadata: dict[str, object] | None = None


class TaskUsageRecordService:
    """为后续 provider 接入预留数据库写入入口。"""

    def __init__(self) -> None:
        self.session_factory = get_async_session_factory()

    async def record(self, payload: TaskUsageRecordCreate) -> TaskUsageRecord:
        """写入一条任务资源消耗记录。"""

        async with self.session_factory() as session:
            repository = TaskUsageRecordRepository(session)
            usage_record = TaskUsageRecord(
                id=uuid.uuid4(),
                task_id=uuid.UUID(payload.task_id),
                user_id=uuid.UUID(payload.user_id),
                provider_type=payload.provider_type,
                provider_name=payload.provider_name,
                model_name=payload.model_name,
                action_name=payload.action_name,
                request_units=payload.request_units,
                prompt_tokens=payload.prompt_tokens,
                completion_tokens=payload.completion_tokens,
                image_count=payload.image_count,
                latency_ms=payload.latency_ms,
                cost_amount=payload.cost_amount,
                cost_currency=payload.cost_currency,
                success=payload.success,
                error_code=payload.error_code,
                metadata_json=payload.metadata,
            )
            repository.add(usage_record)
            await session.commit()
            return usage_record
