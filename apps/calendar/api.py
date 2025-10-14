"""Calendar API endpoints"""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date
from typing import List, Union, Dict, Any

from ninja import Query, Router
from ninja.errors import HttpError
from pydantic import ValidationError

from .schema import CalendarFilters, EconomicEventSchema, CalendarResponse, ErrorResponse, CacheStatsResponse, CacheClearResponse
from .service import CalendarFetchOptions, fetch_events
from .cache_service import SmartCacheService

logger = logging.getLogger(__name__)
router = Router(tags=["Economic Calendar"])


@router.get("", response={200: CalendarResponse, 400: ErrorResponse, 500: ErrorResponse})
def get_calendar(request, filters: Query[CalendarFilters]) -> Union[CalendarResponse, ErrorResponse]:
    """
    Fetch economic calendar events from Investing.com
    
    Returns economic events for the specified date range with proper error handling.
    """
    try:
        # Sử dụng default values đơn giản
        date_from = filters.date_from or date.today()
        date_to = filters.date_to or date_from
        
        # Sử dụng các giá trị mặc định cố định cho other parameters
        options = CalendarFetchOptions(
            date_from=date_from,
            date_to=date_to,
            time_zone="110",  # Asia/Ho_Chi_Minh timezone
            importance=[2, 3],  # Medium và High importance
            countries=None,  # Tất cả countries
            skip_holidays=True,  # Bỏ qua holidays
        )

        events = fetch_events(options)
        
        # Convert events sang schema format
        event_schemas = []
        for event in events:
            try:
                event_schemas.append(EconomicEventSchema(**asdict(event)))
            except Exception as e:
                logger.warning(f"Failed to convert event to schema: {e}")
                continue
        
        return CalendarResponse(
            events=event_schemas,
            total_count=len(event_schemas),
            date_from=date_from.strftime("%Y-%m-%d"),
            date_to=date_to.strftime("%Y-%m-%d")
        )
        
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HttpError(400, f"Invalid parameters: {str(e)}")
    
    except ValueError as e:
        logger.error(f"Value error: {e}")
        raise HttpError(400, str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error fetching calendar: {e}")
        raise HttpError(500, "Internal server error while fetching calendar data")


@router.get("/cache/stats", response={200: CacheStatsResponse})
def get_cache_stats(request) -> CacheStatsResponse:
    """
    Get calendar cache statistics
    """
    try:
        stats = SmartCacheService.get_cache_stats()
        return CacheStatsResponse(
            status="success",
            cache_stats=stats,
            message="Cache statistics retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HttpError(500, f"Failed to get cache stats: {str(e)}")


@router.post("/cache/clear", response={200: CacheClearResponse})
def clear_cache(request) -> CacheClearResponse:
    """
    Clear all calendar cache (admin endpoint)
    """
    try:
        cleared_count = SmartCacheService.clear_all_cache()
        return CacheClearResponse(
            status="success", 
            cleared_entries=cleared_count,
            message=f"Successfully cleared {cleared_count} cache entries"
        )
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HttpError(500, f"Failed to clear cache: {str(e)}")
