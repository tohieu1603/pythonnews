from typing import Optional, Dict
from ninja import Schema

class SymbolOut(Schema):
    id: int
    name: str
    exchange: Optional[str] = None

class InComeOut(Schema):
    year: int
    quarter: int
    symbol: SymbolOut

    revenue: Optional[int]
    revenue_yoy: Optional[float]
    attribute_to_parent_company: Optional[int]
    attribute_to_parent_company_yoy: Optional[float]
    interest_and_similar_income: Optional[int]
    interest_and_similar_expenses: Optional[int]
    net_interest_income: Optional[int]
    fees_and_comission_income: Optional[int]
    fees_and_comission_expenses: Optional[int]
    net_fee_and_commission_income: Optional[int]
    net_gain_foreign_currency_and_gold_dealings: Optional[int]
    net_gain_trading_of_trading_securities: Optional[int]
    net_gain_disposal_of_investment_securities: Optional[int]
    net_other_income: Optional[int]
    other_expenses: Optional[int]
    net_other_income_expenses: Optional[int]
    dividends_received: Optional[int]
    total_operating_revenue: Optional[int]
    general_admin_expenses: Optional[int]
    operating_profit_before_provision: Optional[int]
    provision_for_credit_losses: Optional[int]
    profit_before_tax: Optional[int]
    tax_for_the_year: Optional[int]
    business_income_tax_current: Optional[int]
    business_income_tax_deferred: Optional[int]
    minority_interest: Optional[int]
    net_profit_for_the_year: Optional[int]
    attributable_to_parent_company: Optional[int]
    eps_basis: Optional[int]
