"""
Rate limiter service để tránh gọi API VNStock quá nhiều
"""
import time
from typing import Dict, Optional
from threading import Lock
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class RateLimitInfo:
    last_call: float
    call_count: int
    window_start: float


class VNStockRateLimiter:
    """
    Rate limiter để control API calls tới VNStock
    """

    def __init__(self,
                 calls_per_minute: int = 30,  # Giảm xuống 30 calls/phút
                 calls_per_hour: int = 500,   # 500 calls/giờ
                 min_interval: float = 2.5):  # Tối thiểu 2.5 giây giữa các calls
        self.calls_per_minute = calls_per_minute
        self.calls_per_hour = calls_per_hour
        self.min_interval = min_interval

        # Track rate limits per endpoint/source
        self.rate_limits: Dict[str, RateLimitInfo] = {}
        self.lock = Lock()

        # Global tracking
        self.last_global_call = 0.0
        self.minute_calls = []
        self.hour_calls = []

    def _clean_old_calls(self, now: float):
        """Xóa các calls cũ khỏi tracking"""
        minute_ago = now - 60
        hour_ago = now - 3600

        self.minute_calls = [call_time for call_time in self.minute_calls if call_time > minute_ago]
        self.hour_calls = [call_time for call_time in self.hour_calls if call_time > hour_ago]

    def wait_if_needed(self, endpoint: str = "default") -> float:
        """
        Kiểm tra và wait nếu cần thiết để tránh rate limit
        Returns: thời gian đã wait (seconds)
        """
        with self.lock:
            now = time.time()

            # Clean old calls
            self._clean_old_calls(now)

            wait_time = 0.0

            # Check global minimum interval
            if self.last_global_call > 0:
                time_since_last = now - self.last_global_call
                if time_since_last < self.min_interval:
                    needed_wait = self.min_interval - time_since_last
                    wait_time = max(wait_time, needed_wait)

            # Check per-minute limit
            if len(self.minute_calls) >= self.calls_per_minute:
                oldest_call = min(self.minute_calls)
                time_to_wait = 60 - (now - oldest_call)
                if time_to_wait > 0:
                    wait_time = max(wait_time, time_to_wait)

            # Check per-hour limit
            if len(self.hour_calls) >= self.calls_per_hour:
                oldest_call = min(self.hour_calls)
                time_to_wait = 3600 - (now - oldest_call)
                if time_to_wait > 0:
                    wait_time = max(wait_time, time_to_wait)

            # Check endpoint-specific limits
            if endpoint in self.rate_limits:
                endpoint_info = self.rate_limits[endpoint]
                time_since_last = now - endpoint_info.last_call
                if time_since_last < self.min_interval:
                    needed_wait = self.min_interval - time_since_last
                    wait_time = max(wait_time, needed_wait)

            # Perform wait if needed
            if wait_time > 0:
                print(f"⏳ Rate limiter: waiting {wait_time:.1f}s for {endpoint}")
                time.sleep(wait_time)
                now = time.time()  # Update now after sleep

            # Record this call
            self.minute_calls.append(now)
            self.hour_calls.append(now)
            self.last_global_call = now

            # Update endpoint info
            if endpoint not in self.rate_limits:
                self.rate_limits[endpoint] = RateLimitInfo(now, 1, now)
            else:
                self.rate_limits[endpoint].last_call = now
                self.rate_limits[endpoint].call_count += 1

            return wait_time

    def get_stats(self) -> Dict:
        """Lấy thống kê rate limiting"""
        with self.lock:
            now = time.time()
            self._clean_old_calls(now)

            return {
                "calls_last_minute": len(self.minute_calls),
                "calls_last_hour": len(self.hour_calls),
                "limits": {
                    "per_minute": self.calls_per_minute,
                    "per_hour": self.calls_per_hour,
                    "min_interval": self.min_interval
                },
                "endpoint_stats": {
                    endpoint: {
                        "last_call": info.last_call,
                        "call_count": info.call_count,
                        "seconds_since_last": now - info.last_call
                    }
                    for endpoint, info in self.rate_limits.items()
                }
            }

    def reset_stats(self):
        """Reset tất cả statistics"""
        with self.lock:
            self.rate_limits.clear()
            self.minute_calls.clear()
            self.hour_calls.clear()
            self.last_global_call = 0.0


# Global rate limiter instance
_global_rate_limiter = None

def get_rate_limiter() -> VNStockRateLimiter:
    """Get global rate limiter instance"""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = VNStockRateLimiter()
    return _global_rate_limiter