"""Lightweight in-memory rate limiting for first-release API protection."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
import time

from fastapi import Request

from backend.core.config import Settings, get_settings
from backend.core.exceptions import AppException
from backend.core.metrics import metrics_registry


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    name: str
    max_requests: int
    window_seconds: int


class InMemoryRateLimiter:
    """Fixed-window-ish limiter backed by timestamp deques.

    This is intentionally per-process.  It protects the MVP from accidental or
    low-effort abuse without adding Redis coupling to every request path.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._buckets: defaultdict[tuple[str, str], deque[float]] = defaultdict(deque)

    def hit(self, *, rule: RateLimitRule, key: str, now: float | None = None) -> tuple[bool, int]:
        now = time.monotonic() if now is None else now
        cutoff = now - rule.window_seconds
        bucket_key = (rule.name, key)

        with self._lock:
            bucket = self._buckets[bucket_key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= rule.max_requests:
                retry_after = max(1, int(rule.window_seconds - (now - bucket[0])))
                return False, retry_after
            bucket.append(now)
            return True, 0


limiter = InMemoryRateLimiter()


def rate_limit(rule_name: str) -> Callable[[Request], None]:
    """Build a FastAPI dependency for a named rule."""

    async def dependency(request: Request) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return

        rule = _resolve_rule(settings, rule_name)
        if rule.max_requests <= 0 or rule.window_seconds <= 0:
            return

        key = _client_key(request)
        allowed, retry_after = limiter.hit(rule=rule, key=key)
        if allowed:
            return

        metrics_registry.record_rate_limited(rule_name=rule.name)
        raise AppException(
            "Too many requests. Please retry later.",
            code=4290,
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )

    return dependency


def _resolve_rule(settings: Settings, rule_name: str) -> RateLimitRule:
    if rule_name == "auth_login":
        return RateLimitRule(
            name=rule_name,
            max_requests=settings.rate_limit_login_requests,
            window_seconds=settings.rate_limit_login_window_seconds,
        )
    if rule_name == "task_create":
        return RateLimitRule(
            name=rule_name,
            max_requests=settings.rate_limit_task_create_requests,
            window_seconds=settings.rate_limit_task_create_window_seconds,
        )
    if rule_name == "upload_presign":
        return RateLimitRule(
            name=rule_name,
            max_requests=settings.rate_limit_upload_presign_requests,
            window_seconds=settings.rate_limit_upload_presign_window_seconds,
        )
    raise RuntimeError(f"unknown rate limit rule: {rule_name}")


def _client_key(request: Request) -> str:
    ip = _client_ip(request)
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    return f"{ip}:{request.method.upper()}:{path}"


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client is not None:
        return request.client.host
    return "unknown"
