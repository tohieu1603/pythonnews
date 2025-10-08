import logging
from typing import Any, Dict, Optional

from django.conf import settings


def log_event(
    message: str,
    *,
    level: int = logging.INFO,
    channel: str = "app",
    context: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Convenient helper for writing structured events to the logs table."""

    logger = logging.getLogger(channel)
    logger.log(
        level,
        message,
        extra={
            "context": context or {},
            "extra_data": extra or {},
            "channel": channel,
            "environment": getattr(settings, "APP_ENV", "local"),
        },
    )
