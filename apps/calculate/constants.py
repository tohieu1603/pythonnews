# apps/calculate/constants.py
"""
Mapping English field names từ vnstock API data sang DB column names
"""

CASH_FLOW_MAPPING = {
    # Basic fields
    "ticker": "ticker",
    "yearReport": "year_report", 
    "lengthReport": "length_report",
    
    # Cash Flow fields
    "Net Profit/Loss before tax": "net_profit_loss_before_tax",
    "Depreciation and Amortisation": "depreciation_and_amortisation",
    "Provision for credit losses": "provision_for_credit_losses",
    "Unrealized foreign exchange gain/loss": "unrealized_foreign_exchange_gain_loss",
    "Profit/Loss from investing activities": "profit_loss_from_investing_activities",
    "Interest Expense": "interest_expense",
    "Operating profit before changes in working capital": "operating_profit_before_changes_in_working_capital",
    "Increase/Decrease in receivables": "increase_decrease_in_receivables",
    "Increase/Decrease in inventories": "increase_decrease_in_inventories",
    "Increase/Decrease in payables": "increase_decrease_in_payables",
    "Increase/Decrease in prepaid expenses": "increase_decrease_in_prepaid_expenses",
    "Interest paid": "interest_paid",
    "Business Income Tax paid": "business_income_tax_paid",
    "Net cash inflows/outflows from operating activities": "net_cash_inflows_outflows_from_operating_activities",
    "Purchase of fixed assets": "purchase_of_fixed_assets",
    "Proceeds from disposal of fixed assets": "proceeds_from_disposal_of_fixed_assets",
    "Loans granted, purchases of debt instruments (Bn. VND)": "loans_granted_purchases_of_debt_instruments_bn_vnd",
    "Collection of loans, proceeds from sales of debts instruments (Bn. VND)": "collection_of_loans_proceeds_from_sales_of_debts_instruments_bn_vnd",
    "Investment in other entities": "investment_in_other_entities",
    "Proceeds from divestment in other entities": "proceeds_from_divestment_in_other_entities",
    "Gain on Dividend": "gain_on_dividend",
    "Net Cash Flows from Investing Activities": "net_cash_flows_from_investing_activities",
    "Increase in charter captial": "increase_in_charter_captial",
    "Payments for share repurchases": "payments_for_share_repurchases",
    "Proceeds from borrowings": "proceeds_from_borrowings",
    "Repayment of borrowings": "repayment_of_borrowings",
    "Finance lease principal payments": "finance_lease_principal_payments",
    "Dividends paid": "dividends_paid",
    "Cash flows from financial activities": "cash_flows_from_financial_activities",
    "Net increase/decrease in cash and cash equivalents": "net_increase_decrease_in_cash_and_cash_equivalents",
    "Cash and cash equivalents": "cash_and_cash_equivalents",
    "Foreign exchange differences Adjustment": "foreign_exchange_differences_adjustment",
    "Cash and Cash Equivalents at the end of period": "cash_and_cash_equivalents_at_the_end_of_period",
}

INCOME_STATEMENT_MAPPING = {
    # Basic fields
    "ticker": "ticker",
    "yearReport": "year_report",
    "lengthReport": "length_report",
    
    # Income Statement fields
    "Revenue YoY (%)": "revenue_yo_y_percent",
    "Revenue (Bn. VND)": "revenue_bn_vnd",
    "Attribute to parent company (Bn. VND)": "attribute_to_parent_company_bn_vnd",
    "Attribute to parent company YoY (%)": "attribute_to_parent_company_yo_y_percent",
    "Financial Income": "financial_income",
    "Interest Expenses": "interest_expenses",
    "Sales": "sales",
    "Sales deductions": "sales_deductions",
    "Net Sales": "net_sales",
    "Cost of Sales": "cost_of_sales",
    "Gross Profit": "gross_profit",
    "Financial Expenses": "financial_expenses",
    "Gain/(loss) from joint ventures": "gain_loss_from_joint_ventures",
    "Selling Expenses": "selling_expenses",
    "General & Admin Expenses": "general_admin_expenses",
    "Operating Profit/Loss": "operating_profit_loss",
    "Other income": "other_income",
    "Other Income/Expenses": "other_income_expenses",
    "Net other income/expenses": "net_other_income_expenses",
    "Profit before tax": "profit_before_tax",
    "Business income tax - current": "business_income_tax_current",
    "Business income tax - deferred": "business_income_tax_deferred",
    "Net Profit For the Year": "net_profit_for_the_year",
    "Minority Interest": "minority_interest",
    "Attributable to parent company": "attributable_to_parent_company",
}

BALANCE_SHEET_MAPPING = {
    # Basic fields
    "ticker": "ticker",
    "yearReport": "year_report",
    "lengthReport": "length_report",
    
    # Balance Sheet fields
    "CURRENT ASSETS (Bn. VND)": "current_assets_bn_vnd",
    "Cash and cash equivalents (Bn. VND)": "cash_and_cash_equivalents_bn_vnd",
    "Short-term investments (Bn. VND)": "short_term_investments_bn_vnd",
    "Accounts receivable (Bn. VND)": "accounts_receivable_bn_vnd",
    "Net Inventories": "net_inventories",
    "Other current assets": "other_current_assets",
    "LONG-TERM ASSETS (Bn. VND)": "long_term_assets_bn_vnd",
    "Long-term loans receivables (Bn. VND)": "long_term_loans_receivables_bn_vnd",
    "Fixed assets (Bn. VND)": "fixed_assets_bn_vnd",
    "Long-term investments (Bn. VND)": "long_term_investments_bn_vnd",
    "Other non-current assets": "other_non_current_assets",
    "TOTAL ASSETS (Bn. VND)": "total_assets_bn_vnd",
    "LIABILITIES (Bn. VND)": "liabilities_bn_vnd",
    "Current liabilities (Bn. VND)": "current_liabilities_bn_vnd",
    "Long-term liabilities (Bn. VND)": "long_term_liabilities_bn_vnd",
    "OWNER'S EQUITY(Bn.VND)": "owners_equitybn_vnd",
    "Capital and reserves (Bn. VND)": "capital_and_reserves_bn_vnd",
    "Undistributed earnings (Bn. VND)": "undistributed_earnings_bn_vnd",
    "MINORITY INTERESTS": "minority_interests",
    "TOTAL RESOURCES (Bn. VND)": "total_resources_bn_vnd",
    "Prepayments to suppliers (Bn. VND)": "prepayments_to_suppliers_bn_vnd",
    "Short-term loans receivables (Bn. VND)": "short_term_loans_receivables_bn_vnd",
    "Inventories, Net (Bn. VND)": "inventories_net_bn_vnd",
    "Other current assets (Bn. VND)": "other_current_assets_bn_vnd",
    "Investment and development funds (Bn. VND)": "investment_and_development_funds_bn_vnd",
    "Common shares (Bn. VND)": "common_shares_bn_vnd",
    "Paid-in capital (Bn. VND)": "paid_in_capital_bn_vnd",
    "Long-term borrowings (Bn. VND)": "long_term_borrowings_bn_vnd",
    "Advances from customers (Bn. VND)": "advances_from_customers_bn_vnd",
    "Short-term borrowings (Bn. VND)": "short_term_borrowings_bn_vnd",
    "Good will (Bn. VND)": "good_will_bn_vnd",
    "Long-term prepayments (Bn. VND)": "long_term_prepayments_bn_vnd",
    "Other long-term assets (Bn. VND)": "other_long_term_assets_bn_vnd",
    "Other long-term receivables (Bn. VND)": "other_long_term_receivables_bn_vnd",
    "Long-term trade receivables (Bn. VND)": "long_term_trade_receivables_bn_vnd",
}

RATIO_MAPPING = {
    # Basic fields
    "ticker": "ticker",
    "yearReport": "year_report",
    "lengthReport": "length_report",
    
    # Ratio fields
    "(ST+LT borrowings)/Equity": "st_lt_borrowings_equity",
    "Debt/Equity": "debt_equity",
    "Fixed Asset-To-Equity": "fixed_asset_to_equity",
    "Owners' Equity/Charter Capital": "owners_equity_charter_capital",
    "Asset Turnover": "asset_turnover",
    "Fixed Asset Turnover": "fixed_asset_turnover",
    "Days Sales Outstanding": "days_sales_outstanding",
    "Days Inventory Outstanding": "days_inventory_outstanding",
    "Days Payable Outstanding": "days_payable_outstanding",
    "Cash Cycle": "cash_cycle",
    "Inventory Turnover": "inventory_turnover",
    "EBIT Margin (%)": "ebit_margin_percent",
    "Gross Profit Margin (%)": "gross_profit_margin_percent",
    "Net Profit Margin (%)": "net_profit_margin_percent",
    "ROE (%)": "roe_percent",
    "ROIC (%)": "roic_percent",
    "ROA (%)": "roa_percent",
    "EBITDA (Bn. VND)": "ebitda_bn_vnd",
    "EBIT (Bn. VND)": "ebit_bn_vnd",
    "Dividend yield (%)": "dividend_yield_percent",
    "Current Ratio": "current_ratio",
    "Cash Ratio": "cash_ratio",
    "Quick Ratio": "quick_ratio",
    "Interest Coverage": "interest_coverage",
    "Financial Leverage": "financial_leverage",
    "Market Capital (Bn. VND)": "market_capital_bn_vnd",
    "Outstanding Share (Mil. Shares)": "outstanding_share_mil_shares",
    "P/E": "p_e",
    "P/B": "p_b",
    "P/S": "p_s",
    "P/Cash Flow": "p_cash_flow",
    "EPS (VND)": "eps_vnd",
    "BVPS (VND)": "bvps_vnd",
    "EV/EBITDA": "ev_ebitda",
}

# Helper để map data từ vnstock API format
def map_cash_flow_data(api_data):
    """Map cash flow data từ vnstock API format sang DB format"""
    mapped_data = {}
    for api_field, db_field in CASH_FLOW_MAPPING.items():
        if api_field in api_data:
            mapped_data[db_field] = api_data[api_field]
    return mapped_data

def map_income_statement_data(api_data):
    """Map income statement data từ vnstock API format sang DB format"""
    mapped_data = {}
    for api_field, db_field in INCOME_STATEMENT_MAPPING.items():
        if api_field in api_data:
            mapped_data[db_field] = api_data[api_field]
    return mapped_data

def map_balance_sheet_data(api_data):
    """Map balance sheet data từ vnstock API format sang DB format"""
    mapped_data = {}
    for api_field, db_field in BALANCE_SHEET_MAPPING.items():
        if api_field in api_data:
            mapped_data[db_field] = api_data[api_field]
    return mapped_data

def map_ratio_data(api_data):
    """Map ratio data từ vnstock API format sang DB format"""
    mapped_data = {}
    for api_field, db_field in RATIO_MAPPING.items():
        if api_field in api_data:
            mapped_data[db_field] = api_data[api_field]
    return mapped_data

class VNStockFields:
    """Constants for vnstock API field names."""
    
    YEAR_REPORT = "yearReport"
    LENGTH_REPORT = "lengthReport"
    
    TOTAL_ASSETS = "TOTAL ASSETS (Bn. VND)"
    CASH_AND_CASH_EQUIVALENTS = "Cash and cash equivalents (Bn. VND)"
    FIXED_ASSETS = "Fixed assets (Bn. VND)"
    LONG_TERM_INVESTMENTS = "Long-term investments (Bn. VND)"
    OTHER_CURRENT_ASSETS = "Other current assets (Bn. VND)"
    OTHER_LONG_TERM_ASSETS = "Other long-term assets (Bn. VND)"
    SHORT_TERM_INVESTMENTS = "Short-term investments (Bn. VND)"
    
    LIABILITIES = "LIABILITIES (Bn. VND)"
    CURRENT_LIABILITIES = "Current liabilities (Bn. VND)"
    
    OWNERS_EQUITY = "OWNER'S EQUITY(Bn.VND)"
    CAPITAL_AND_RESERVES = "Capital and reserves (Bn. VND)"
    UNDISTRIBUTED_EARNINGS = "Undistributed earnings (Bn. VND)"
    PAID_IN_CAPITAL = "Paid-in capital (Bn. VND)"
    
    TOTAL_RESOURCES = "TOTAL RESOURCES (Bn. VND)"
    
    REVENUE = "revenue"
    NET_PROFIT = "net_profit"
    
    CASH_FLOW = "cash_flow"
    
    ROE = "roe"
    ROA = "roa"
    PE = "pe"
    PB = "pb"

class ConversionConstants:
    """Constants for data type conversions."""
    BILLION_TO_UNITS = 1_000_000_000