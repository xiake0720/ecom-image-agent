from __future__ import annotations

from backend.core.rate_limit import InMemoryRateLimiter, RateLimitRule


def test_in_memory_rate_limiter_blocks_until_window_expires() -> None:
    limiter = InMemoryRateLimiter()
    rule = RateLimitRule(name="login", max_requests=2, window_seconds=10)

    assert limiter.hit(rule=rule, key="127.0.0.1", now=100.0) == (True, 0)
    assert limiter.hit(rule=rule, key="127.0.0.1", now=101.0) == (True, 0)

    allowed, retry_after = limiter.hit(rule=rule, key="127.0.0.1", now=102.0)
    assert allowed is False
    assert retry_after == 8

    assert limiter.hit(rule=rule, key="127.0.0.1", now=111.0) == (True, 0)
