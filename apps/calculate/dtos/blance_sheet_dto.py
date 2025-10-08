from typing import Optional, List
from ninja import Schema
from apps.stock.schemas import SymbolOut
from apps.calculate.models import BalanceSheet
from ninja.errors import HttpError

# Schema Out
class BalanceSheetOut(Schema):
    year: int
    quarter: int
    symbol: SymbolOut

    current_assets: Optional[int]
    cash_and_cash_equivalents: Optional[int]
    short_term_investments: Optional[int]
    accounts_receivable: Optional[int]
    net_inventories: Optional[int]
    prepayments_to_suppliers: Optional[int]
    other_current_assets: Optional[int]

    long_term_assets: Optional[int]
    fixed_assets: Optional[int]
    long_term_investments: Optional[int]
    long_term_prepayments: Optional[int]
    other_long_term_assets: Optional[int]
    other_long_term_receivables: Optional[int]
    long_term_trade_receivables: Optional[int]

    total_assets: Optional[int]

    liabilities: Optional[int]
    current_liabilities: Optional[int]
    short_term_borrowings: Optional[int]
    advances_from_customers: Optional[int]
    long_term_liabilities: Optional[int]
    long_term_borrowings: Optional[int]
    owners_equity: Optional[int]
    capital_and_reserves: Optional[int]
    common_shares: Optional[int]
    paid_in_capital: Optional[int]
    undistributed_earnings: Optional[int]
    investment_and_development_funds: Optional[int]

    total_resources: Optional[int]


