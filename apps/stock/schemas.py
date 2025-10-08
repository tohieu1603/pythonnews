from ninja import Schema
from typing import List, Optional
from datetime import datetime


class ShareHolderOut(Schema):
    id: int
    share_holder: Optional[str] = None
    quantity: Optional[int] = None
    share_own_percent: Optional[float] = None
    update_date: Optional[datetime] = None


class NewsOut(Schema):
    id: int
    title: Optional[str] = None
    news_image_url: Optional[str] = None   
    news_source_link: Optional[str] = None 
    price_change_pct: Optional[float] = None
    public_date: Optional[int] = None  


class EventsOut(Schema):
    id: int
    event_title: Optional[str] = None
    public_date: Optional[datetime] = None
    issue_date: Optional[datetime] = None
    source_url: Optional[str] = None


class OfficersOut(Schema):
    id: int
    officer_name: Optional[str] = None
    officer_position: Optional[str] = None
    position_short_name: Optional[str] = None
    officer_owner_percent: Optional[float] = None
    updated_at: Optional[datetime] = None


class SubCompanyOut(Schema):
    id: int
    company_name: Optional[str] = None
    sub_own_percent: Optional[float] = None


class CompanyOut(Schema):
    id: int
    company_name: str
    company_profile: Optional[str] = None
    history: Optional[str] = None
    issue_share: Optional[int] = None
    financial_ratio_issue_share: Optional[int] = None
    charter_capital: Optional[int] = None
    outstanding_share: Optional[float] = None
    foreign_percent: Optional[float] = None
    established_year: Optional[int] = None
    no_employees: Optional[int] = None
    stock_rating: Optional[float] = None
    website: Optional[str] = None
    updated_at: Optional[datetime] = None
    shareholders: List[ShareHolderOut] = []
    news: List[NewsOut] = []
    events: List[EventsOut] = []
    officers: List[OfficersOut] = []
    subsidiaries: List[SubCompanyOut] = []


class IndustryRefOut(Schema):
    id: int
    name: str
    updated_at: Optional[datetime] = None


class SymbolOut(Schema):
    id: int
    name: str
    exchange: Optional[str] = None
    updated_at: Optional[datetime] = None
    industries: List[IndustryRefOut] = []
    company: Optional[CompanyOut] = None
class SymbolOutBasic(Schema):
    id: int
    name: str
    exchange: Optional[str] = None
    
class SymbolList(Schema):
    id: int
    name: str
    exchange: str
    updated_at: datetime

class IndustryOut(Schema):
    id: int
    name: str
    updated_at: Optional[datetime] = None
    companies: List[CompanyOut] = []   
