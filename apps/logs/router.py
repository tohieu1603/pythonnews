import logging
import re
from typing import Any, Dict, Optional

import jwt
from django.conf import settings
from django.utils import timezone
from ninja import Router, Schema

router = Router(tags=["logs"])
logger = logging.getLogger("app")


class LogCreateRequest(Schema):
    level: str
    channel: str
    message: str
    context: Optional[Dict[str, Any]] = None
    extra_data: Optional[Dict[str, Any]] = None


class LogCreateResponse(Schema):
    success: bool
    message: str


def _get_user_id_from_jwt(request) -> int | None:
    """Extract user_id from JWT token in Authorization header or cookie."""
    auth_header = request.META.get("HTTP_AUTHORIZATION")
    token = None

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    else:
        token = request.COOKIES.get("access_token")

    if not token:
        return None

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("user_id") or payload.get("sub")
    except Exception:
        return None


def _get_stock_search_message(request) -> str | None:
    """Generate custom log message for stock search endpoints."""
    path = request.path

    # Pattern: /api/stocks/symbols/{id}
    symbol_by_id = re.match(r'^/api/stocks/symbols/(\d+)$', path)
    if symbol_by_id:
        symbol_id = symbol_by_id.group(1)
        try:
            from apps.stock.models import Symbol
            symbol = Symbol.objects.filter(id=symbol_id).first()
            if symbol:
                return f"Tìm kiếm {symbol.name}, xem chi tiết mã {symbol_id}"
        except Exception:
            pass
        return f"Tìm kiếm mã {symbol_id}"

    # Pattern: /api/stocks/symbols/by-name/{name}
    symbol_by_name = re.match(r'^/api/stocks/symbols/by-name/([^/]+)$', path)
    if symbol_by_name:
        symbol_name = symbol_by_name.group(1)
        return f"Tìm kiếm {symbol_name}"

    return None


@router.post("/logs", response=LogCreateResponse)
def create_log(request, payload: LogCreateRequest):
    """Create a log entry with user_id from JWT token."""
    try:
        from django.db import connection

        user_id = _get_user_id_from_jwt(request)

        context = payload.context or {}
        if user_id:
            context["user_id"] = user_id

        custom_message = _get_stock_search_message(request)
        log_message = custom_message if custom_message else payload.message

        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO logs (level, channel, message, context, extra, environment, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, [
                payload.level.lower(),
                payload.channel,
                log_message,
                __import__('json').dumps(context),
                __import__('json').dumps(payload.extra_data or {}),
                getattr(settings, "APP_ENV", "local"),
                timezone.now()
            ])

        return LogCreateResponse(success=True, message="Log created successfully")

    except Exception as e:
        logger.error(f"Failed to create log: {str(e)}")
        return LogCreateResponse(success=False, message=f"Failed to create log: {str(e)}")
