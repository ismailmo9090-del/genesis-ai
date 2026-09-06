"""Sliding-window rate limiter for API requests."""

from __future__ import annotations

import logging
import time
import threading
from functools import wraps

from flask import g

from .errors import error_response

logger = logging.getLogger(__name__)


class RateLimiter:
    """In-memory sliding-window rate limiter per API key prefix."""

    def __init__(self):
        self._windows: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _cleanup(self, key: str, window_seconds: int):
        """Remove timestamps older than the window."""
        now = time.time()
        cutoff = now - window_seconds
        timestamps = self._windows.get(key, [])
        self._windows[key] = [t for t in timestamps if t > cutoff]

    def is_rate_limited(self, key: str, rpm: int, rph: int) -> tuple[bool, dict | None]:
        """Check if a key is rate limited.

        Returns:
            (is_limited, retry_after_info)
        """
        with self._lock:
            now = time.time()

            # Check requests per minute
            minute_key = f"{key}:rpm"
            self._cleanup(minute_key, 60)
            minute_timestamps = self._windows.get(minute_key, [])
            if len(minute_timestamps) >= rpm:
                oldest = min(minute_timestamps)
                retry_after = int(60 - (now - oldest)) + 1
                return True, {
                    "limit": rpm,
                    "window": "minute",
                    "retry_after": retry_after,
                }

            # Check requests per hour
            hour_key = f"{key}:rph"
            self._cleanup(hour_key, 3600)
            hour_timestamps = self._windows.get(hour_key, [])
            if len(hour_timestamps) >= rph:
                oldest = min(hour_timestamps)
                retry_after = int(3600 - (now - oldest)) + 1
                return True, {
                    "limit": rph,
                    "window": "hour",
                    "retry_after": retry_after,
                }

            # Record this request
            self._windows.setdefault(minute_key, []).append(now)
            self._windows.setdefault(hour_key, []).append(now)

            return False, None


_limiter = RateLimiter()


def check_rate_limit():
    """Check rate limit for the current request. Call after auth.

    Returns:
        None if OK, or error_response tuple if limited.
    """
    if not hasattr(g, "api_key"):
        return None

    key_info = g.api_key
    is_limited, info = _limiter.is_rate_limited(
        key_info["key_prefix"],
        key_info["requests_per_minute"],
        key_info["requests_per_hour"],
    )

    if is_limited:
        logger.warning(
            "Rate limited: key=%s window=%s retry_after=%s",
            key_info["key_prefix"], info["window"], info["retry_after"],
        )
        return error_response(
            "RATE_LIMITED",
            f"Rate limit exceeded ({info['limit']} requests per {info['window']}). Retry after {info['retry_after']}s.",
            429,
        )
    return None


def rate_limit_required(f):
    """Decorator: check rate limit after auth."""
    @wraps(f)
    def decorated(*args, **kwargs):
        result = check_rate_limit()
        if result:
            response, status_code = result
            return response, status_code
        return f(*args, **kwargs)
    return decorated
