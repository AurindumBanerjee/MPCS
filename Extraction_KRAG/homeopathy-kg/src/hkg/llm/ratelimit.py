from __future__ import annotations

import time
import threading


class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter for LLM API calls."""

    def __init__(self, requests_per_minute: int = 60):
        self.capacity = max(1, requests_per_minute)
        self.tokens = float(self.capacity)
        self.fill_rate = float(requests_per_minute) / 60.0  # tokens per second
        self.last_update = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self, tokens: int = 1) -> None:
        """Blocks until sufficient tokens are available."""
        while True:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(float(self.capacity), self.tokens + elapsed * self.fill_rate)

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
                # Calculate required sleep time
                deficit = tokens - self.tokens
                sleep_time = deficit / self.fill_rate

            time.sleep(max(0.01, sleep_time))
