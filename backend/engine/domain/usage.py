"""模型调用 usage 领域模型与聚合工具。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

ProviderType = Literal["text", "image"]


class UsageSource(str, Enum):
    """标准化 usage 来源。"""

    PROVIDER_REPORTED = "provider_reported"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"


class ProviderUsageSnapshot(BaseModel):
    """单次 provider 调用的标准化 usage 快照。"""

    usage_source: UsageSource = UsageSource.UNAVAILABLE
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 1
    image_count: int = 0
    latency_ms: int = 0
    raw_usage: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def empty(cls) -> "ProviderUsageSnapshot":
        """返回一个全零快照。"""

        return cls(request_count=0)

    @classmethod
    def unavailable(
        cls,
        *,
        request_count: int = 1,
        image_count: int = 0,
        latency_ms: int = 0,
    ) -> "ProviderUsageSnapshot":
        """返回 provider 未提供 token 细节时的占位快照。"""

        return cls(
            usage_source=UsageSource.UNAVAILABLE,
            request_count=max(0, request_count),
            image_count=max(0, image_count),
            latency_ms=max(0, latency_ms),
        )

    def merged(self, other: "ProviderUsageSnapshot") -> "ProviderUsageSnapshot":
        """合并两个 provider usage 快照。"""

        return ProviderUsageSnapshot(
            usage_source=_merge_usage_source(self.usage_source, other.usage_source),
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            request_count=self.request_count + other.request_count,
            image_count=self.image_count + other.image_count,
            latency_ms=self.latency_ms + other.latency_ms,
            raw_usage={},
        )


class UsageEvent(BaseModel):
    """落盘到任务目录中的单次模型调用事件。"""

    event_id: str = Field(default_factory=lambda: uuid4().hex)
    task_id: str
    task_type: str
    stage_name: str
    stage_label: str = ""
    provider_type: ProviderType
    provider_name: str
    model_id: str
    item_id: str = ""
    attempt: int = 1
    success: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    usage: ProviderUsageSnapshot = Field(default_factory=ProviderUsageSnapshot.empty)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UsageMetrics(BaseModel):
    """任务级 usage 聚合指标。"""

    total_event_count: int = 0
    successful_event_count: int = 0
    failed_event_count: int = 0
    provider_reported_event_count: int = 0
    estimated_event_count: int = 0
    unavailable_event_count: int = 0
    request_count: int = 0
    image_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0

    def merged(self, other: "UsageMetrics") -> "UsageMetrics":
        """合并两个 usage 聚合指标。"""

        return UsageMetrics(
            total_event_count=self.total_event_count + other.total_event_count,
            successful_event_count=self.successful_event_count + other.successful_event_count,
            failed_event_count=self.failed_event_count + other.failed_event_count,
            provider_reported_event_count=self.provider_reported_event_count + other.provider_reported_event_count,
            estimated_event_count=self.estimated_event_count + other.estimated_event_count,
            unavailable_event_count=self.unavailable_event_count + other.unavailable_event_count,
            request_count=self.request_count + other.request_count,
            image_count=self.image_count + other.image_count,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            latency_ms=self.latency_ms + other.latency_ms,
        )


class UsageBreakdownItem(BaseModel):
    """按阶段或 provider 聚合后的 usage 条目。"""

    key: str
    label: str
    metrics: UsageMetrics = Field(default_factory=UsageMetrics)


class UsageSummary(BaseModel):
    """任务 usage 汇总。"""

    total: UsageMetrics = Field(default_factory=UsageMetrics)
    by_stage: list[UsageBreakdownItem] = Field(default_factory=list)
    by_provider: list[UsageBreakdownItem] = Field(default_factory=list)


class RuntimeUsageSummary(BaseModel):
    """runtime 接口使用的 usage 汇总容器。"""

    self_summary: UsageSummary = Field(default_factory=UsageSummary)
    upstream_summary: UsageSummary = Field(default_factory=UsageSummary)
    end_to_end_summary: UsageSummary = Field(default_factory=UsageSummary)


def normalize_usage_snapshot(
    raw_usage: object,
    *,
    latency_ms: int = 0,
    request_count: int = 1,
    image_count: int = 0,
) -> ProviderUsageSnapshot:
    """把 provider 原始 usage 负载标准化为统一快照。"""

    normalized = coerce_usage_payload(raw_usage)
    input_tokens = _first_int(
        normalized,
        "input_tokens",
        "prompt_tokens",
        "prompt_token_count",
        "input_token_count",
        "prompt_eval_count",
    )
    output_tokens = _first_int(
        normalized,
        "output_tokens",
        "completion_tokens",
        "completion_token_count",
        "candidates_token_count",
        "eval_count",
    )
    total_tokens = _first_int(
        normalized,
        "total_tokens",
        "total_token_count",
    )
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens
    usage_source = UsageSource.PROVIDER_REPORTED if normalized else UsageSource.UNAVAILABLE
    return ProviderUsageSnapshot(
        usage_source=usage_source,
        input_tokens=max(0, input_tokens),
        output_tokens=max(0, output_tokens),
        total_tokens=max(0, total_tokens),
        request_count=max(0, request_count),
        image_count=max(0, image_count),
        latency_ms=max(0, latency_ms),
        raw_usage=normalized,
    )


def coerce_usage_payload(raw_usage: object) -> dict[str, Any]:
    """尽量把 provider 的 usage 对象转换成普通字典。"""

    if raw_usage is None:
        return {}
    if isinstance(raw_usage, dict):
        return {str(key): value for key, value in raw_usage.items()}
    if hasattr(raw_usage, "model_dump"):
        payload = raw_usage.model_dump(mode="json")
        if isinstance(payload, dict):
            return {str(key): value for key, value in payload.items()}
    if hasattr(raw_usage, "to_dict"):
        payload = raw_usage.to_dict()
        if isinstance(payload, dict):
            return {str(key): value for key, value in payload.items()}
    payload: dict[str, Any] = {}
    for key in dir(raw_usage):
        if key.startswith("_"):
            continue
        try:
            value = getattr(raw_usage, key)
        except Exception:
            continue
        if callable(value):
            continue
        payload[key] = value
    return payload


def resolve_provider_usage_snapshot(
    provider: object,
    *,
    default_request_count: int = 1,
    default_image_count: int = 0,
) -> ProviderUsageSnapshot:
    """从 provider 实例中提取最近一次调用的 usage 快照。"""

    snapshot: object | None = None
    getter = getattr(provider, "get_last_usage", None)
    if callable(getter):
        snapshot = getter()
    elif hasattr(provider, "last_usage"):
        snapshot = getattr(provider, "last_usage")
    if isinstance(snapshot, ProviderUsageSnapshot):
        return snapshot.model_copy()
    if isinstance(snapshot, dict):
        return ProviderUsageSnapshot.model_validate(snapshot)
    return ProviderUsageSnapshot.unavailable(
        request_count=default_request_count,
        image_count=default_image_count,
    )


def summarize_usage_events(events: list[UsageEvent]) -> UsageSummary:
    """按阶段和 provider 聚合 usage 事件。"""

    total = UsageMetrics()
    by_stage: dict[str, UsageBreakdownItem] = {}
    by_provider: dict[str, UsageBreakdownItem] = {}
    for event in events:
        event_metrics = metrics_from_event(event)
        total = total.merged(event_metrics)
        stage_key = event.stage_name
        stage_item = by_stage.setdefault(
            stage_key,
            UsageBreakdownItem(
                key=stage_key,
                label=event.stage_label or event.stage_name,
            ),
        )
        stage_item.metrics = stage_item.metrics.merged(event_metrics)
        provider_key = f"{event.provider_type}:{event.provider_name}:{event.model_id}"
        provider_item = by_provider.setdefault(
            provider_key,
            UsageBreakdownItem(
                key=provider_key,
                label=f"{event.provider_type}/{event.provider_name}/{event.model_id or '-'}",
            ),
        )
        provider_item.metrics = provider_item.metrics.merged(event_metrics)
    return UsageSummary(
        total=total,
        by_stage=sorted(by_stage.values(), key=lambda item: item.key),
        by_provider=sorted(by_provider.values(), key=lambda item: item.key),
    )


def merge_usage_summaries(left: UsageSummary, right: UsageSummary) -> UsageSummary:
    """把两个 usage summary 合并为一个端到端 summary。"""

    by_stage: dict[str, UsageBreakdownItem] = {}
    by_provider: dict[str, UsageBreakdownItem] = {}
    for summary in [left, right]:
        for item in summary.by_stage:
            current = by_stage.get(item.key)
            if current is None:
                by_stage[item.key] = item.model_copy(deep=True)
                continue
            current.metrics = current.metrics.merged(item.metrics)
        for item in summary.by_provider:
            current = by_provider.get(item.key)
            if current is None:
                by_provider[item.key] = item.model_copy(deep=True)
                continue
            current.metrics = current.metrics.merged(item.metrics)
    return UsageSummary(
        total=left.total.merged(right.total),
        by_stage=sorted(by_stage.values(), key=lambda item: item.key),
        by_provider=sorted(by_provider.values(), key=lambda item: item.key),
    )


def metrics_from_event(event: UsageEvent) -> UsageMetrics:
    """把单个 usage event 转换成可聚合指标。"""

    usage = event.usage
    return UsageMetrics(
        total_event_count=1,
        successful_event_count=1 if event.success else 0,
        failed_event_count=0 if event.success else 1,
        provider_reported_event_count=1 if usage.usage_source == UsageSource.PROVIDER_REPORTED else 0,
        estimated_event_count=1 if usage.usage_source == UsageSource.ESTIMATED else 0,
        unavailable_event_count=1 if usage.usage_source == UsageSource.UNAVAILABLE else 0,
        request_count=max(0, usage.request_count),
        image_count=max(0, usage.image_count),
        input_tokens=max(0, usage.input_tokens),
        output_tokens=max(0, usage.output_tokens),
        total_tokens=max(0, usage.total_tokens),
        latency_ms=max(0, usage.latency_ms),
    )


def _merge_usage_source(left: UsageSource, right: UsageSource) -> UsageSource:
    """合并两个 usage 来源并保留更强的可信度。"""

    priority = {
        UsageSource.PROVIDER_REPORTED: 3,
        UsageSource.ESTIMATED: 2,
        UsageSource.UNAVAILABLE: 1,
    }
    return left if priority[left] >= priority[right] else right


def _first_int(payload: dict[str, Any], *keys: str) -> int:
    """按优先级读取 usage 字段中的整数值。"""

    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.isdigit():
                return int(stripped)
    return 0
