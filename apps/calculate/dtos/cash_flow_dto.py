

from datetime import date
from typing import Optional, List
from pydantic import BaseModel
from ninja import Schema
class SymbolOut(Schema):
    id: int
    name: str
    exchange: Optional[str]

class CashFlowOut(Schema):
    year: int
    quarter: int
    symbol: SymbolOut
    
    # Tất cả các field từ CashFlow model
    net_profit_loss_before_tax: Optional[int]
    depreciation_and_amortisation: Optional[int]
    provision_for_credit_losses: Optional[int]
    unrealized_foreign_exchange_gain_loss: Optional[int]
    profit_loss_from_investing_activities: Optional[int]
    interest_expense: Optional[int]
    operating_profit_before_changes_in_working_capital: Optional[int]
    increase_decrease_in_receivables: Optional[int]
    increase_decrease_in_inventories: Optional[int]
    increase_decrease_in_payables: Optional[int]
    increase_decrease_in_prepaid_expenses: Optional[int]
    interest_paid: Optional[int]
    business_income_tax_paid: Optional[int]
    net_cash_inflows_outflows_from_operating_activities: Optional[int]
    purchase_of_fixed_assets: Optional[int]
    proceeds_from_disposal_of_fixed_assets: Optional[int]
    loans_granted_purchases_of_debt_instruments_bn_vnd: Optional[int]
    collection_of_loans_proceeds_sales_instruments_vnd: Optional[int]
    investment_in_other_entities: Optional[int]
    proceeds_from_divestment_in_other_entities: Optional[int]
    gain_on_dividend: Optional[int]
    net_cash_flows_from_investing_activities: Optional[int]
    increase_in_charter_captial: Optional[int]
    payments_for_share_repurchases: Optional[int]
    proceeds_from_borrowings: Optional[int]
    repayment_of_borrowings: Optional[int]
    finance_lease_principal_payments: Optional[int]
    dividends_paid: Optional[int]
    cash_flows_from_financial_activities: Optional[int]
    net_increase_decrease_in_cash_and_cash_equivalents: Optional[int]
    cash_and_cash_equivalents: Optional[int]
    foreign_exchange_differences_adjustment: Optional[int]
    cash_and_cash_equivalents_at_the_end_of_period: Optional[int]