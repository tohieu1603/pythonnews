"""Tool để lấy lịch kinh tế từ Investing.com (giao diện tiếng Việt)."""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional, Tuple
from types import SimpleNamespace
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://vn.investing.com"
SERVICE_URL = f"{BASE_URL}/economic-calendar/Service/getCalendarFilteredData"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


@dataclass
class EconomicEvent:
    date: str
    time: Optional[str]
    all_day: bool
    country: Optional[str]
    country_code: Optional[str]
    currency: Optional[str]
    importance: Optional[int]
    title: str
    actual: Optional[str]
    forecast: Optional[str]
    previous: Optional[str]
    source_url: Optional[str]
    event_id: Optional[str]
    event_datetime: Optional[str]
    category: str




@dataclass
class CalendarFetchOptions:
    date_from: date
    date_to: date
    time_zone: str = "110"
    time_filter: str = "timeRemain"
    importance: Optional[List[int]] = None
    countries: Optional[List[str]] = None
    skip_holidays: bool = False

def ensure_utf8_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    today = date.today().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(
        description=(
            "Tải lịch kinh tế từ Investing.com (phiên bản tiếng Việt) và xuất ra JSON hoặc CSV."
        )
    )
    parser.add_argument("--date-from", default=today, help="Ngày bắt đầu (YYYY-MM-DD), mặc định hôm nay")
    parser.add_argument("--date-to", default=today, help="Ngày kết thúc (YYYY-MM-DD), mặc định cùng ngày")
    parser.add_argument(
        "--time-zone",
        default="110",
        help=(
            "Mã múi giờ theo Investing (mặc định 110 - Asia/Ho_Chi_Minh)."
            " Xem mã khác trực tiếp trên trang nếu cần."
        ),
    )
    parser.add_argument(
        "--time-filter",
        default="timeRemain",
        choices=["timeRemain", "timeOnly", "excludePassed"],
        help="Bộ lọc thời gian Investing (mặc định: timeRemain).",
    )
    parser.add_argument(
        "--importance",
        nargs="*",
        type=int,
        choices=[2, 3],
        help="Lọc theo độ quan trọng (số đầu bò: 1-3). Bỏ trống để lấy tất cả.",
    )
    parser.add_argument(
        "--countries",
        nargs="*",
        help=(
            "Danh sách ID quốc gia theo Investing. Ví dụ: 25 (Mỹ), 6 (Anh)."
            " Bỏ trống để lấy tất cả."
        ),
    )
    parser.add_argument(
        "--format",
        default="json",
        choices=["json", "csv"],
        help="Định dạng xuất: json (mặc định) hoặc csv.",
    )
    parser.add_argument(
        "--skip-holidays",
        action="store_true",
        help="Bỏ qua các mục ngày nghỉ lễ.",
    )
    parser.add_argument(
        "--output",
        help="???ng d?n file ?? l?u k?t qu? (m?c ??nh in ra stdout).",
    )
    return parser.parse_args(argv)


def validate_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise SystemExit(f"Ngày không hợp lệ: {value}. Định dạng đúng: YYYY-MM-DD") from exc


def build_payload(args: argparse.Namespace, date_from: str, date_to: str) -> List[tuple[str, str]]:
    payload: List[tuple[str, str]] = [
        ("timeZone", str(args.time_zone)),
        ("timeFilter", args.time_filter),
        ("dateFrom", date_from),
        ("dateTo", date_to),
    ]
    if args.importance:
        for level in args.importance:
            payload.append(("importance[]", str(level)))
    if args.countries:
        for country_id in args.countries:
            payload.append(("country[]", str(country_id)))
    return payload


def clean_text(cell: Optional[BeautifulSoup]) -> Optional[str]:
    if cell is None:
        return None
    text = cell.get_text(" ", strip=True)
    return text or None


def parse_importance(cell: Optional[BeautifulSoup]) -> Optional[int]:
    if cell is None:
        return None
    icons = cell.find_all("i")
    if not icons:
        return None
    score = 0
    for icon in icons:
        classes = " ".join(icon.get("class", []))
        if "FullBullish" in classes:
            score += 1
    return score or None


def parse_country_currency(cell: Optional[BeautifulSoup]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    if cell is None:
        return (None, None, None)
    span = cell.find("span")
    country_name = span.get("title") if span else None
    country_code = span.get("data-img_key") if span else None
    texts = list(cell.stripped_strings)
    currency = None
    if texts:
        last_token = texts[-1]
        if not country_name or last_token != country_name:
            currency = last_token
    return country_name, country_code, currency


def parse_event_row(row: BeautifulSoup, current_date: datetime) -> EconomicEvent:
    cells = row.find_all("td")
    time_cell, country_cell, importance_cell, event_cell = cells[:4]
    actual_cell = cells[4] if len(cells) > 4 else None
    forecast_cell = cells[5] if len(cells) > 5 else None
    previous_cell = cells[6] if len(cells) > 6 else None

    time_text = clean_text(time_cell)
    all_day = time_text == "Tất cả các Ngày"
    if all_day:
        time_text = None

    country_name, country_code, currency = parse_country_currency(country_cell)
    importance = parse_importance(importance_cell)

    title_link = event_cell.find("a")
    title_text = clean_text(event_cell) or ""
    source_url = urljoin(BASE_URL, title_link.get("href")) if title_link else None

    event_datetime = row.get("data-event-datetime")

    return EconomicEvent(
        date=current_date.strftime("%Y-%m-%d"),
        time=time_text,
        all_day=all_day,
        country=country_name,
        country_code=country_code,
        currency=currency,
        importance=importance,
        title=title_text,
        actual=clean_text(actual_cell),
        forecast=clean_text(forecast_cell),
        previous=clean_text(previous_cell),
        source_url=source_url,
        event_id=row.get("event_attr_id") or row.get("id"),
        event_datetime=event_datetime,
        category="event",
    )


def parse_holiday_row(row: BeautifulSoup, current_date: datetime) -> EconomicEvent:
    cells = row.find_all("td")
    time_cell = cells[0] if cells else None
    country_cell = cells[1] if len(cells) > 1 else None
    category_cell = cells[2] if len(cells) > 2 else None
    description_cell = cells[3] if len(cells) > 3 else None

    country_name, country_code, currency = parse_country_currency(country_cell)
    category_text = clean_text(category_cell) or "Holiday"
    title_text = clean_text(description_cell) or category_text
    normalized = category_text.strip().lower()
    normalized_ascii = unicodedata.normalize('NFD', normalized)
    normalized_ascii = ''.join(ch for ch in normalized_ascii if unicodedata.category(ch) != 'Mn')
    normalized_ascii = normalized_ascii.encode('ascii', 'ignore').decode()
    if 'holiday' in normalized_ascii or 'ngay nghi' in normalized_ascii:
        category_slug = 'holiday'
    else:
        category_slug = normalized.replace(' ', '_')

    return EconomicEvent(
        date=current_date.strftime("%Y-%m-%d"),
        time=None,
        all_day=True,
        country=country_name,
        country_code=country_code,
        currency=currency,
        importance=2,
        title=title_text,
        actual=None,
        forecast=None,
        previous=None,
        source_url=None,
        event_id=row.get("id"),
        event_datetime=None,
        category=category_slug,
    )


def parse_calendar_html(html: str) -> List[EconomicEvent]:
    soup = BeautifulSoup(html, "html.parser")
    no_result = soup.find("td", class_="noResults")
    if no_result:
        return []

    events: List[EconomicEvent] = []
    current_date: Optional[datetime] = None

    for row in soup.find_all("tr"):
        date_cell = row.find("td", class_="theDay")
        if date_cell is not None:
            raw_date = clean_text(date_cell)
            if not raw_date:
                continue
            try:
                current_date = datetime.strptime(raw_date, "%d/%m/%Y")
            except ValueError:
                continue
            continue

        if current_date is None:
            continue

        row_id = row.get("id", "")
        classes = row.get("class", [])
        if "js-event-item" in classes:
            events.append(parse_event_row(row, current_date))
        elif row_id.startswith("eventRowId"):
            events.append(parse_holiday_row(row, current_date))

    return events


def _expected_dates(start_date: date, end_date: date) -> set[date]:
    span = (end_date - start_date).days
    return {start_date + timedelta(days=offset) for offset in range(span + 1)}


def _extract_event_dates(events: List[EconomicEvent]) -> set[date]:
    dates: set[date] = set()
    for event in events:
        if not event.date:
            continue
        try:
            parsed = datetime.strptime(event.date, "%Y-%m-%d").date()
        except ValueError:
            continue
        dates.add(parsed)
    return dates


def _group_missing_ranges(missing_dates: List[date]) -> List[Tuple[date, date]]:
    if not missing_dates:
        return []
    ranges: List[Tuple[date, date]] = []
    start = prev = missing_dates[0]
    for current in missing_dates[1:]:
        if current == prev + timedelta(days=1):
            prev = current
            continue
        ranges.append((start, prev))
        start = prev = current
    ranges.append((start, prev))
    return ranges


def _request_calendar_span(args: argparse.Namespace, start_date: date, end_date: date) -> List[EconomicEvent]:
    payload = build_payload(
        args,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
    )
    headers = {
        "User-Agent": USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE_URL}/economic-calendar/",
    }
    response = requests.post(SERVICE_URL, data=payload, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    html = data.get("data", "")
    return parse_calendar_html(html)


def _fetch_calendar_span(args: argparse.Namespace, start_date: date, end_date: date) -> List[EconomicEvent]:
    events = _request_calendar_span(args, start_date, end_date)
    if start_date == end_date:
        return events
    expected = _expected_dates(start_date, end_date)
    observed = _extract_event_dates(events)
    missing = sorted(expected - observed)
    if not missing:
        return events
    for missing_start, missing_end in _group_missing_ranges(missing):
        events.extend(_fetch_calendar_span(args, missing_start, missing_end))
    return events


def _deduplicate_events(events: List[EconomicEvent]) -> List[EconomicEvent]:
    seen = set()
    deduped: List[EconomicEvent] = []
    for event in events:
        key = (
            event.date,
            event.time,
            event.title,
            event.country_code,
            event.event_id,
            event.category,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)
    deduped.sort(key=_event_sort_key)
    return deduped


def _event_sort_key(event: EconomicEvent) -> tuple[str, tuple[int, int, int], str]:
    date_key = event.date or ""
    if event.time:
        try:
            hour_str, minute_str = event.time.split(":", 1)
            hour = int(hour_str)
            minute = int(minute_str)
        except (ValueError, AttributeError):
            time_key = (1, 99, 99)
        else:
            time_key = (1, hour, minute)
    else:
        time_key = (0, 0, 0)
    return (date_key, time_key, event.title or "")


def fetch_calendar(args: argparse.Namespace, start_date: date, end_date: date) -> List[EconomicEvent]:
    events = _fetch_calendar_span(args, start_date, end_date)
    events = _deduplicate_events(events)
    if args.skip_holidays:
        events = [event for event in events if event.category != "holiday"]
    return events



def fetch_events(options: CalendarFetchOptions) -> List[EconomicEvent]:
    namespace = SimpleNamespace(
        time_zone=options.time_zone,
        time_filter=options.time_filter,
        importance=options.importance,
        countries=options.countries,
        skip_holidays=options.skip_holidays,
    )
    return fetch_calendar(namespace, options.date_from, options.date_to)


def output_json(events: List[EconomicEvent], output_path: Optional[str] = None) -> None:
    payload = [asdict(event) for event in events]
    if output_path:
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    else:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")


def output_csv(events: List[EconomicEvent], output_path: Optional[str] = None) -> None:
    import csv

    fieldnames = list(asdict(events[0]).keys()) if events else [
        "date",
        "time",
        "all_day",
        "country",
        "country_code",
        "currency",
        "importance",
        "title",
        "actual",
        "forecast",
        "previous",
        "source_url",
        "event_id",
        "event_datetime",
        "category",
    ]
    handle = sys.stdout
    close_handle = False
    if output_path:
        handle = open(output_path, "w", encoding="utf-8", newline="")
        close_handle = True
    try:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for event in events:
            writer.writerow(asdict(event))
    finally:
        if close_handle:
            handle.close()


def main(argv: Optional[Iterable[str]] = None) -> None:
    ensure_utf8_stdout()
    args = parse_args(argv)
    start = validate_date(args.date_from)
    end = validate_date(args.date_to)
    if end < start:
        raise SystemExit("date-to phải lớn hơn hoặc bằng date-from")

    events = fetch_calendar(args, start.date(), end.date())
    if args.format == "json":
        output_json(events, args.output)
    else:
        output_csv(events, args.output)


if __name__ == "__main__":
    main()
