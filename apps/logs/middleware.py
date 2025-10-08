import logging
import re
import time
from typing import Any, Dict

import jwt
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("app")


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


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


class RequestLoggingMiddleware(MiddlewareMixin):
    """Capture incoming/outgoing HTTP requests for audit logging."""

    def process_request(self, request):
        request._log_start_ts = time.time()
        request._log_context: Dict[str, Any] = {
            "path": request.path,
            "method": request.method,
            "ip": _client_ip(request),
            "query_string": request.META.get("QUERY_STRING", ""),
            "user_id": _get_user_id_from_jwt(request),
        }

        # Check for stock search endpoints and generate custom message
        custom_message = _get_stock_search_message(request)
        log_message = custom_message if custom_message else f"Client request {request.path}"

        logger.info(
            log_message,
            extra={
                "context": request._log_context,
                "channel": "web",
                "environment": getattr(settings, "APP_ENV", "local"),
            },
        )

    def process_response(self, request, response):
        if hasattr(request, "_log_context"):
            duration_ms = None
            if hasattr(request, "_log_start_ts"):
                duration_ms = round((time.time() - request._log_start_ts) * 1000, 2)
            context = request._log_context.copy()
            context.update(
                {
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "content_type": response.get("Content-Type"),
                }
            )

            # Check for stock search endpoints and generate custom message
            custom_message = _get_stock_search_message(request)
            log_message = custom_message if custom_message else f"Client request {request.path}"

            logger.info(
                log_message,
                extra={
                    "context": context,
                    "channel": "web",
                    "environment": getattr(settings, "APP_ENV", "local"),
                },
            )
        return response

    def process_exception(self, request, exception):  
        context = getattr(request, "_log_context", {}).copy()
        context.update({"exception": repr(exception)})
        logger.error(
            "request_exception",
            extra={
                "context": context,
                "channel": "web",
                "environment": getattr(settings, "APP_ENV", "local"),
            },
        )
