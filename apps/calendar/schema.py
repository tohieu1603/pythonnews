"""Schemas for Calendar API"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, List
from ninja import Schema
from pydantic import Field, model_validator


class CalendarFilters(Schema):
    """Query parameters for filtering calendar events"""
    date_from: Optional[date] = Field(
        None,
        description="Start date (YYYY-MM-DD)",
        example="2025-10-14",
    )
    date_to: Optional[date] = Field(
        None,
        description="End date (YYYY-MM-DD)",
        example="2025-10-21",
    )

    @model_validator(mode='after')
    def validate_date_range(self):
        if self.date_from and self.date_to:
            if self.date_to < self.date_from:
                raise ValueError('date_to must be greater than or equal to date_from')
            
            # Giới hạn range tối đa 365 ngày để tránh performance issues
            max_days = 365
            if (self.date_to - self.date_from).days > max_days:
                raise ValueError(f'Date range too large. Maximum allowed: {max_days} days')
        
        return self


class EconomicEventSchema(Schema):
    """Economic event from Investing.com calendar"""
    date: str = Field(..., description="Event date (YYYY-MM-DD)")
    time: Optional[str] = Field(None, description="Event time (HH:MM)")
    all_day: bool = Field(..., description="Whether event is all day")
    country: Optional[str] = Field(None, description="Country name")
    country_code: Optional[str] = Field(None, description="Country code")
    currency: Optional[str] = Field(None, description="Currency code")
    importance: Optional[int] = Field(None, description="Event importance (1-3)")
    title: str = Field(..., description="Event title")
    actual: Optional[str] = Field(None, description="Actual value")
    forecast: Optional[str] = Field(None, description="Forecast value")
    previous: Optional[str] = Field(None, description="Previous value")
    source_url: Optional[str] = Field(None, description="Source URL on Investing.com")
    event_id: Optional[str] = Field(None, description="Event ID")
    event_datetime: Optional[str] = Field(None, description="Event datetime string")
    category: str = Field(..., description="Event category (event/holiday)")


class CalendarResponse(Schema):
    """Response schema for calendar endpoint"""
    events: List[EconomicEventSchema] = Field(..., description="List of economic events")
    total_count: int = Field(..., description="Total number of events returned")
    date_from: str = Field(..., description="Actual start date used")
    date_to: str = Field(..., description="Actual end date used")


class ErrorResponse(Schema):
    """Error response schema"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    code: Optional[str] = Field(None, description="Error code")


class CacheStatsResponse(Schema):
    """Cache statistics response schema"""
    status: str = Field(..., description="Response status")
    cache_stats: dict = Field(..., description="Cache configuration and statistics")
    message: str = Field(..., description="Status message")


class CacheClearResponse(Schema):
    """Cache clear response schema"""
    status: str = Field(..., description="Response status")
    cleared_entries: int = Field(..., description="Number of cache entries cleared")
    message: str = Field(..., description="Status message")
