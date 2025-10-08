"""Schemas for Calendar API"""
from __future__ import annotations

from datetime import date
from typing import Optional
from ninja import Schema
from pydantic import Field


class CalendarFilters(Schema):
    """Query parameters for filtering calendar events"""
    date_from: Optional[date] = Field(
        None,
        description="Start date (YYYY-MM-DD)",
        example="2025-09-22",
    )
    date_to: Optional[date] = Field(
        None,
        description="End date (YYYY-MM-DD)",
        example="2025-09-25",
    )


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
