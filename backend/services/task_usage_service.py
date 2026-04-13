"""任务 usage 事件记录与 runtime 聚合服务。"""

from __future__ import annotations

from backend.engine.domain.usage import (
    ProviderType,
    ProviderUsageSnapshot,
    RuntimeUsageSummary,
    UsageEvent,
    UsageSummary,
    merge_usage_summaries,
)
from backend.engine.services.storage.local_storage import LocalStorageService


class TaskUsageService:
    """统一处理 usage 事件落盘与 runtime 汇总。"""

    def __init__(self) -> None:
        self.storage = LocalStorageService()

    def record_usage(
        self,
        *,
        task_id: str,
        task_type: str,
        stage_name: str,
        stage_label: str,
        provider_type: ProviderType,
        provider_name: str,
        model_id: str,
        usage: ProviderUsageSnapshot,
        success: bool,
        attempt: int = 1,
        item_id: str = "",
        metadata: dict[str, object] | None = None,
    ) -> None:
        """记录一次标准化模型调用事件。"""

        event = UsageEvent(
            task_id=task_id,
            task_type=task_type,
            stage_name=stage_name,
            stage_label=stage_label,
            provider_type=provider_type,
            provider_name=provider_name,
            model_id=model_id,
            item_id=item_id,
            attempt=attempt,
            success=success,
            usage=usage,
            metadata=metadata or {},
        )
        self.storage.append_usage_event(task_id, event)

    def build_runtime_usage_summary(
        self,
        task_id: str,
        *,
        upstream_task_id: str = "",
    ) -> RuntimeUsageSummary:
        """构建 runtime 使用的 self/upstream/end-to-end usage 汇总。"""

        self_summary = self.storage.load_usage_summary(task_id) or UsageSummary()
        upstream_summary = self.storage.load_usage_summary(upstream_task_id) if upstream_task_id else None
        effective_upstream = upstream_summary or UsageSummary()
        return RuntimeUsageSummary(
            self_summary=self_summary,
            upstream_summary=effective_upstream,
            end_to_end_summary=merge_usage_summaries(self_summary, effective_upstream),
        )
