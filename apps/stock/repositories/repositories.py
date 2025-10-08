import math
from typing import Any, Dict, Iterable, Optional
from django.db.models import QuerySet, Prefetch
from apps.stock.models import Industry, ShareHolder, Symbol, Company, News, Officers, Events, SubCompany
from apps.stock.utils.safe import to_epoch_seconds


def _normalize_public_date(value: Any) -> Optional[int]:
    """Convert various epoch formats to seconds while tolerating NaN values."""
    if value is None:
        return None

    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        seconds = value / 1000 if value > 1e12 else value
        try:
            return int(seconds)
        except (TypeError, ValueError, OverflowError):
            return None

    # Attempt best-effort conversion for datetime/string inputs.
    try:
        fallback = to_epoch_seconds(value)
        if fallback is None:
            return None
        return int(fallback)
    except Exception:
        return None


def get_or_create_industry(name: Optional[str]) -> Industry:
    clean_name = (name or "").strip() or "Unknown Industry"
    obj, _ = Industry.objects.get_or_create(name=clean_name)
    return obj

def upsert_industry(defaults: Dict) -> Industry:
    ind_id = defaults.get("id") if isinstance(defaults, dict) else None
    name = defaults.get("name") if isinstance(defaults, dict) else None
    clean_name = (name or "").strip() or "Unknown Industry"

    if ind_id is not None:
        obj, _ = Industry.objects.update_or_create(
            id=int(ind_id),
            defaults={"name": clean_name, "level": defaults.get("level")},
        )
        return obj

    obj, _ = Industry.objects.get_or_create(
        name=clean_name, defaults={"level": defaults.get("level")}
    )
    return obj

def upsert_company(company_name: Optional[str], defaults: Dict) -> Company:
    clean_name = (company_name or "").strip() or "Unknown Company"
    company, _ = Company.objects.update_or_create(
        company_name=clean_name,
        defaults=defaults,
    )
    return company


def upsert_symbol(name: str, defaults: Dict) -> Symbol:
    clean_name = (name or "").strip().upper()
    symbol, _ = Symbol.objects.update_or_create(
        name=clean_name,
        defaults=defaults,
    )
    return symbol


def upsert_shareholders(company: Company, rows: Iterable[Dict]) -> None:
    for r in rows:
        ShareHolder.objects.update_or_create(
            share_holder=(r.get("share_holder") or "").strip(),
            company=company,
            defaults={
                "quantity": r.get("quantity"),
                "share_own_percent": r.get("share_own_percent"),
                "update_date": r.get("update_date"),
            }
        )


def upsert_news(company: Company, rows: Iterable[Dict]) -> None:
    for r in rows:
      
        public_date = _normalize_public_date(r.get("public_date"))
        price_change_pct = safe_decimal(r.get("price_change_pct"), None)

        News.objects.update_or_create(
            title=(r.get("title") or "").strip(),
            company=company,
            defaults={
                "news_image_url": r.get("news_image_url"),
                "news_source_link": r.get("news_source_link"),
                "public_date": public_date,
                "price_change_pct": price_change_pct,
            }
        )

def upsert_events(company: Company, rows: Iterable[Dict]) -> None:
    """
    Upsert events với public_date và issue_date từ nguồn vnstock
    """
    for r in rows:
        Events.objects.update_or_create(
            event_title=(r.get("event_title") or "").strip(),
            company=company,
            defaults={
                "source_url": r.get("source_url"),
                "public_date": r.get("public_date"),
                "issue_date": r.get("issue_date"),
            }
        )
def upsert_sub_company(rows: Optional[Iterable[Dict]], parent_company: Company) -> None:
    if not rows:  # None hoặc rỗng
        return
    for r in rows:
        SubCompany.objects.update_or_create(
            company_name=(r.get("company_name") or "").strip(),
            parent=parent_company,
            defaults={
                "sub_own_percent": r.get("sub_own_percent"),
            }
        )


def upsert_officers(company: Company, rows: Iterable[Dict]) -> None:
    for r in rows:
        Officers.objects.update_or_create(
            officer_name=(r.get("officer_name") or "").strip(),
            company=company,
            defaults={
                "officer_position": r.get("officer_position"),
                "position_short_name": r.get("position_short_name"),
                "officer_owner_percent": r.get("officer_owner_percent"),
            }
        )


def qs_companies_with_related() -> QuerySet[Company]:
    return (
        Company.objects
        .prefetch_related("industries", "shareholders", "news", "events", "officers", "symbols")
        .only("id", "company_name")
    )

def qs_symbol_by_name(symbol: int):
    
    return (
        Symbol.objects.filter(id=symbol)
        .select_related("company")
        .prefetch_related(
            "industries",
            Prefetch("company__shareholders"),
            Prefetch("company__events"),
            Prefetch("company__officers"),
            Prefetch("company__subsidiaries")
        )
    )
def qs_symbols(limit: Optional[int] = 10):
   return (
        Symbol.objects.all().order_by('id')[:limit])

def qs_industries_with_symbols() -> QuerySet[Industry]:
    return (
        Industry.objects
        .prefetch_related(
            Prefetch(
                "symbols",
                queryset=Symbol.objects.select_related("company"),
            ),
        )
    )
def qs_all_symbols() -> QuerySet[Symbol]:
    return Symbol.objects.all().only("id", "name")

def upsert_symbol_industry(symbol: Symbol, industry: Industry) -> None:
    """
    Tạo hoặc update quan hệ N-N giữa Symbol và Industry
    """
    if not symbol.industries.filter(id=industry.id).exists():
        symbol.industries.add(industry)

def qs_symbols_with_industries() -> QuerySet[Symbol]:
    return (
        Symbol.objects
        .select_related("company")
        .prefetch_related("industries")
        .only(
            "id", "name", "exchange", "updated_at",
            "company__id", "company__company_name", "company__updated_at"
        )
    )
def qs_symbol_name(symbol_name):
    return Symbol.objects.filter(name__iexact = symbol_name).only('id','name', 'exchange')

def qs_symbols_like(symbol_name: str):
    return Symbol.objects.filter(name__icontains=symbol_name)


def upsert_subsidiary_relation(parent_company: Company, sub_company: Company, own_percent: Optional[float]) -> None:
    """
    Tạo quan hệ parent ↔ subsidiary
    """
    sub_company.parent = parent_company
    if own_percent is not None:
        sub_company.sub_own_percent = own_percent
    sub_company.save()

def safe_int(val, default=0):
    if val is None:
        return default
    if isinstance(val, float) and math.isnan(val):
        return default
    try:
        return int(val)
    except (TypeError, ValueError, OverflowError):
        return default

def safe_decimal(val, default=0.0):
    if val is None:
        return default
    if isinstance(val, float) and math.isnan(val):
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

def safe_str(val, default=""):
    if val is None:
        return default
    if isinstance(val, float) and math.isnan(val):
        return default
    return str(val).strip()
