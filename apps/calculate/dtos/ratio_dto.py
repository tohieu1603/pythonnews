from typing import Optional
from pydantic import BaseModel


class SymbolOut(BaseModel):
    """Symbol information output schema"""
    id: int
    name: str
    exchange: Optional[str] = None


class RatioOut(BaseModel):
    """Financial ratio output schema"""
    
    # Period information
    year: int
    quarter: int
    symbol: SymbolOut
    
    # Leverage ratios
    st_lt_borrowings_equity: Optional[float] = None
    debt_equity: Optional[float] = None
    fixed_asset_to_equity: Optional[float] = None
    owners_equity_charter_capital: Optional[float] = None
    
    # Activity ratios
    asset_turnover: Optional[float] = None
    fixed_asset_turnover: Optional[float] = None
    days_sales_outstanding: Optional[float] = None
    days_inventory_outstanding: Optional[float] = None
    days_payable_outstanding: Optional[float] = None
    cash_cycle: Optional[float] = None
    inventory_turnover: Optional[float] = None
    
    # Profitability ratios
    ebit_margin_percent: Optional[float] = None
    gross_profit_margin_percent: Optional[float] = None
    net_profit_margin_percent: Optional[float] = None
    roe_percent: Optional[float] = None
    roic_percent: Optional[float] = None
    roa_percent: Optional[float] = None
    
    # EBITDA and EBIT
    ebitda_bn_vnd: Optional[float] = None
    ebit_bn_vnd: Optional[float] = None
    dividend_yield_percent: Optional[float] = None
    
    # Liquidity ratios
    current_ratio: Optional[float] = None
    cash_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None
    interest_coverage: Optional[float] = None
    financial_leverage: Optional[float] = None
    
    # Market ratios
    market_capital_bn_vnd: Optional[float] = None
    outstanding_share_mil_shares: Optional[float] = None
    p_e: Optional[float] = None
    p_b: Optional[float] = None
    p_s: Optional[float] = None
    p_cash_flow: Optional[float] = None
    eps_vnd: Optional[float] = None
    bvps_vnd: Optional[float] = None
    ev_ebitda: Optional[float] = None

    class Config:
        from_attributes = True