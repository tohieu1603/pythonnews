from datetime import datetime
from typing import Optional

from apps.stock.models import Industry, Company, Symbol, ShareHolder, News, Events, Officers


def create_industry(name: str = "Technology") -> Industry:
    return Industry.objects.create(name=name)


def create_company(
    *,
    full_name: str = "Acme Corp",
    industry: Optional[Industry] = None,
    parent: Optional[Company] = None,
    company_profile: str | None = "Profile",
    history: str | None = "History",
    issue_share: int | None = 1_000_000,
    financial_ratio_issue_share: int | None = 100,
    charter_capital: int | None = 1_000_000_000,
) -> Company:
    if industry is None:
        industry = create_industry()
    return Company.objects.create(
        full_name=full_name,
        parent=parent,
        company_profile=company_profile,
        history=history,
        issue_share=issue_share,
        financial_ratio_issue_share=financial_ratio_issue_share,
        charter_capital=charter_capital,
        industry=industry,
    )


def create_symbol(
    *,
    name: str = "ACM",
    exchange: str = "HOSE",
    company: Optional[Company] = None,
    current_price: float = 10.5,
) -> Symbol:
    if company is None:
        company = create_company()
    return Symbol.objects.create(
        name=name,
        exchange=exchange,
        company=company,
        current_price=current_price,
    )


def create_company_bundle(symbol_name: str = "ACM") -> tuple[Company, Symbol]:
    company = create_company(full_name=f"{symbol_name} Holdings")
    symbol = create_symbol(name=symbol_name, company=company)

    ShareHolder.objects.create(
        share_holder="Founder",
        quantity=1000,
        share_own_percent=12.3456,
        company=company,
    )

    News.objects.create(
        title="Quarterly results",
        news_image_url="https://img.example/q.png",
        news_source_link="https://news.example/q",
        price_change_pct=1.23,
        public_date=int(datetime(2023, 1, 1).timestamp()),
        company=company,
    )

    Events.objects.create(
        event_title="AGM",
        source_url="https://events.example/agm",
        company=company,
    )

    Officers.objects.create(
        officer_name="Jane Doe",
        officer_position="CEO",
        position_short_name="CEO",
        officer_owner_percent=5.5,
        company=company,
    )

    return company, symbol
