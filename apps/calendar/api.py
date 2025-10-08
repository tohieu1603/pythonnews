"""Calendar API endpoints"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import List

from ninja import Query, Router
from ninja.errors import HttpError

from .schema import CalendarFilters, EconomicEventSchema
from .service import CalendarFetchOptions, fetch_events

router = Router(tags=["Economic Calendar"])


@router.get("", response=List[EconomicEventSchema])
def get_calendar(request, filters: Query[CalendarFilters]) -> List[EconomicEventSchema]:
    """
    Fetch economic calendar events from Investing.com
    """
    date_from = filters.date_from or date.today()
    date_to = filters.date_to or date_from

    if date_to < date_from:
        raise HttpError(400, "date_to must be greater than or equal to date_from")

    options = CalendarFetchOptions(
        date_from=date_from,
        date_to=date_to,
        skip_holidays=True,
        importance=[2, 3],
    )

    events = fetch_events(options)
    return [EconomicEventSchema(**asdict(event)) for event in events]
