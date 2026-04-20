"""Minimal in-process Prometheus metrics.

The project does not require prometheus_client at runtime.  This module keeps a
small, thread-safe registry that is enough for first-release operations.
"""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
import time


class MetricsRegistry:
    """Store low-cardinality HTTP and rate-limit counters."""

    def __init__(self) -> None:
        self.started_at = time.time()
        self._lock = Lock()
        self._http_requests: defaultdict[tuple[str, str, int], int] = defaultdict(int)
        self._http_duration_sum: defaultdict[tuple[str, str], float] = defaultdict(float)
        self._http_duration_count: defaultdict[tuple[str, str], int] = defaultdict(int)
        self._rate_limited: defaultdict[str, int] = defaultdict(int)

    def record_http_request(self, *, method: str, path: str, status_code: int, duration_seconds: float) -> None:
        """Record one HTTP request using route templates to avoid cardinality spikes."""

        key = (method.upper(), path, status_code)
        duration_key = (method.upper(), path)
        with self._lock:
            self._http_requests[key] += 1
            self._http_duration_sum[duration_key] += duration_seconds
            self._http_duration_count[duration_key] += 1

    def record_rate_limited(self, *, rule_name: str) -> None:
        """Record one blocked request for a named limit rule."""

        with self._lock:
            self._rate_limited[rule_name] += 1

    def render_prometheus(self) -> str:
        """Render metrics in Prometheus text exposition format."""

        lines = [
            "# HELP ecom_process_uptime_seconds Process uptime in seconds.",
            "# TYPE ecom_process_uptime_seconds gauge",
            f"ecom_process_uptime_seconds {time.time() - self.started_at:.6f}",
            "# HELP ecom_http_requests_total Total HTTP requests.",
            "# TYPE ecom_http_requests_total counter",
        ]

        with self._lock:
            http_requests = dict(self._http_requests)
            duration_sum = dict(self._http_duration_sum)
            duration_count = dict(self._http_duration_count)
            rate_limited = dict(self._rate_limited)

        for (method, path, status_code), value in sorted(http_requests.items()):
            lines.append(
                "ecom_http_requests_total"
                f'{{method="{_escape(method)}",path="{_escape(path)}",status="{status_code}"}} {value}'
            )

        lines.extend(
            [
                "# HELP ecom_http_request_duration_seconds HTTP request duration in seconds.",
                "# TYPE ecom_http_request_duration_seconds summary",
            ]
        )
        for (method, path), value in sorted(duration_sum.items()):
            lines.append(
                "ecom_http_request_duration_seconds_sum"
                f'{{method="{_escape(method)}",path="{_escape(path)}"}} {value:.6f}'
            )
            lines.append(
                "ecom_http_request_duration_seconds_count"
                f'{{method="{_escape(method)}",path="{_escape(path)}"}} {duration_count[(method, path)]}'
            )

        lines.extend(
            [
                "# HELP ecom_rate_limit_blocked_total Total requests blocked by in-process rate limiting.",
                "# TYPE ecom_rate_limit_blocked_total counter",
            ]
        )
        for rule_name, value in sorted(rate_limited.items()):
            lines.append(f'ecom_rate_limit_blocked_total{{rule="{_escape(rule_name)}"}} {value}')

        return "\n".join(lines) + "\n"


metrics_registry = MetricsRegistry()


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
