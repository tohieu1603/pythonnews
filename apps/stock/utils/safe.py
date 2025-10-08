# apps/stock/utils/safe.py
import math
from datetime import datetime, date, time as dtime
from typing import Any, Optional
from django.utils import timezone
import pytz

def _is_nan(v: Any) -> bool:
    return isinstance(v, float) and math.isnan(v)

def safe_decimal(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
    try:
        if value is None or _is_nan(value):
            return default
        return float(value)
    except Exception:
        return default

def safe_int(value: Any, default: Optional[int] = 0) -> Optional[int]:
    try:
        if value is None or _is_nan(value):
            return default
        return int(value)
    except Exception:
        return default

def safe_str(value: Any, default: str = "") -> str:
    try:
        if value is None or _is_nan(value):
            return default
        return str(value)
    except Exception:
        return default

def safe_date_passthrough(value: Any):
    try:
        if value is None or _is_nan(value):
            return None
        
        # Nếu là string, thử convert thành date
        if isinstance(value, str):
            # Thử parse date format YYYY-MM-DD
            try:
                return datetime.strptime(value.strip(), "%Y-%m-%d").date()
            except ValueError:
                # Nếu không parse được, trả về None
                return None
                
        # Nếu đã là date object, trả về nguyên vẹn
        if isinstance(value, date):
            return value
            
        # Nếu là datetime, convert thành date
        if isinstance(value, datetime):
            return value.date()
            
        return value
    except Exception:
        return None

def to_epoch_seconds(value: Any) -> Optional[int]:
    try:
        if value is None or _is_nan(value):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, datetime):
            return int(value.timestamp())
        if isinstance(value, date):
            return int(datetime.combine(value, dtime.min).timestamp())
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return int(dt.timestamp())
            except Exception:
                try:
                    return int(float(value))
                except Exception:
                    return None
    except Exception:
        return None
    return None

def to_datetime(value: Any) -> Optional[datetime]:
    """Convert value to timezone-aware datetime"""
    try:
        if value is None or _is_nan(value):
            return None

        # If already datetime, make it timezone-aware
        if isinstance(value, datetime):
            if timezone.is_naive(value):
                return timezone.make_aware(value, pytz.UTC)
            return value

        # Convert from timestamp
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(float(value), tz=pytz.UTC)
            return dt

        # Convert from date
        if isinstance(value, date):
            dt = datetime.combine(value, dtime.min)
            return timezone.make_aware(dt, pytz.UTC)

        # Parse from string
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if timezone.is_naive(dt):
                    return timezone.make_aware(dt, pytz.UTC)
                return dt
            except Exception:
                try:
                    # Try parsing as YYYY-MM-DD
                    dt = datetime.strptime(value.strip(), "%Y-%m-%d")
                    return timezone.make_aware(dt, pytz.UTC)
                except Exception:
                    try:
                        dt = datetime.fromtimestamp(float(value), tz=pytz.UTC)
                        return dt
                    except Exception:
                        return None
    except Exception:
        return None
    return None

def iso_str_or_none(value: Any) -> Optional[str]:
    """Trả về ISO string (dùng cho SymbolOut.update_time)."""
    dt = to_datetime(value)
    return dt.isoformat() if dt else None
