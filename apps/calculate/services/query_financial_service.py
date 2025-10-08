from typing import List
from ninja.errors import HttpError
from apps.calculate.repositories import qs_cash_flow, qs_income_statement, qs_balance_sheet
from apps.calculate.dtos.cash_flow_dto import CashFlowOut, SymbolOut as CashFlowSymbolOut
from apps.calculate.dtos.income_statement_dto import InComeOut, SymbolOut
from apps.calculate.dtos.blance_sheet_dto import BalanceSheetOut
from apps.calculate.dtos.ratio_dto import RatioOut, SymbolOut as RatioSymbolOut


class QueryFinancialService:
    """Service to handle financial data queries and formatting"""
    
    @staticmethod
    def format_vnd(value) -> str:
        """Format number to VND currency standard"""
        if value is None:
            return "N/A"
        
        try:
            value = float(value)
            if value == 0:
                return "0 VND"
            
            # Convert to billion VND
            if abs(value) >= 1000:
                return f"{value:,.1f} tỷ VND"
            elif abs(value) >= 1:
                return f"{value:,.2f} tỷ VND"
            else:
                # Convert to million VND
                millions = value * 1000
                return f"{millions:,.0f} triệu VND"
        except (ValueError, TypeError):
            return "N/A"
    
    @staticmethod
    def format_percent(value) -> str:
        """Format percentage with proper sign and precision"""
        if value is None:
            return "N/A"
            
        try:
            value = float(value)
            if value == 0:
                return "0%"
            
            return f"{value:+.2f}%"
        except (ValueError, TypeError):
            return "N/A"
    
    @staticmethod
    def format_number(value) -> str:
        """Format regular numbers with thousand separators"""
        if value is None:
            return "N/A"
            
        try:
            value = float(value)
            if value == 0:
                return "0"
            
            return f"{value:,.2f}"
        except (ValueError, TypeError):
            return "N/A"
    
    def get_cash_flow_statements(self, symbol_id: int, limit: int = 10) -> List[CashFlowOut]:
        """Get cash flow statements for a symbol"""
        try:
            qs = qs_cash_flow(symbol_id, limit)
            if not qs.exists():
                raise HttpError(404, f"No cash flow statements found for symbol_id={symbol_id}")
            
            return [
                CashFlowOut(
                    year=cf.year_report,
                    quarter=cf.length_report,
                    symbol=CashFlowSymbolOut(
                        id=cf.symbol.id,
                        name=cf.symbol.name,
                        exchange=getattr(cf.symbol, "exchange", None),
                    ),
                    net_profit_loss_before_tax=cf.net_profit_loss_before_tax,
                    depreciation_and_amortisation=cf.depreciation_and_amortisation,
                    provision_for_credit_losses=cf.provision_for_credit_losses,
                    unrealized_foreign_exchange_gain_loss=cf.unrealized_foreign_exchange_gain_loss,
                    profit_loss_from_investing_activities=cf.profit_loss_from_investing_activities,
                    interest_expense=cf.interest_expense,
                    operating_profit_before_changes_in_working_capital=cf.operating_profit_before_changes_in_working_capital,
                    increase_decrease_in_receivables=cf.increase_decrease_in_receivables,
                    increase_decrease_in_inventories=cf.increase_decrease_in_inventories,
                    increase_decrease_in_payables=cf.increase_decrease_in_payables,
                    increase_decrease_in_prepaid_expenses=cf.increase_decrease_in_prepaid_expenses,
                    interest_paid=cf.interest_paid,
                    business_income_tax_paid=cf.business_income_tax_paid,
                    net_cash_inflows_outflows_from_operating_activities=cf.net_cash_inflows_outflows_from_operating_activities,
                    purchase_of_fixed_assets=cf.purchase_of_fixed_assets,
                    proceeds_from_disposal_of_fixed_assets=cf.proceeds_from_disposal_of_fixed_assets,
                    loans_granted_purchases_of_debt_instruments_bn_vnd=cf.loans_granted_purchases_of_debt_instruments_bn_vnd,
                    collection_of_loans_proceeds_sales_instruments_vnd=cf.collection_of_loans_proceeds_sales_instruments_vnd,
                    investment_in_other_entities=cf.investment_in_other_entities,
                    proceeds_from_divestment_in_other_entities=cf.proceeds_from_divestment_in_other_entities,
                    gain_on_dividend=cf.gain_on_dividend,
                    net_cash_flows_from_investing_activities=cf.net_cash_flows_from_investing_activities,
                    increase_in_charter_captial=cf.increase_in_charter_captial,
                    payments_for_share_repurchases=cf.payments_for_share_repurchases,
                    proceeds_from_borrowings=cf.proceeds_from_borrowings,
                    repayment_of_borrowings=cf.repayment_of_borrowings,
                    finance_lease_principal_payments=cf.finance_lease_principal_payments,
                    dividends_paid=cf.dividends_paid,
                    cash_flows_from_financial_activities=cf.cash_flows_from_financial_activities,
                    net_increase_decrease_in_cash_and_cash_equivalents=cf.net_increase_decrease_in_cash_and_cash_equivalents,
                    cash_and_cash_equivalents=cf.cash_and_cash_equivalents,
                    foreign_exchange_differences_adjustment=cf.foreign_exchange_differences_adjustment,
                    cash_and_cash_equivalents_at_the_end_of_period=cf.cash_and_cash_equivalents_at_the_end_of_period,
                )
                for cf in qs
            ]

        except Exception as e:
            import traceback
            print(f"Error in get_cash_flow_statements: {e}")
            print(traceback.format_exc())
            raise HttpError(500, "Lỗi hệ thống, vui lòng thử lại sau.")
    
    def get_income_statements(self, symbol_id: int) -> List[InComeOut]:
        """Get income statements for a symbol"""
        try:
            qs = qs_income_statement(symbol_id)
            if not qs.exists():
                raise HttpError(404, "No income statements found for this symbol")

            return [
                InComeOut(
                    year=inc.year_report,
                    quarter=inc.length_report,
                    symbol=SymbolOut(
                        id=inc.symbol.id,
                        name=inc.symbol.name,
                        exchange=getattr(inc.symbol, "exchange", None)
                    ),
                    revenue=inc.revenue_bn_vnd,
                    revenue_yoy=inc.revenue_yoy_percent,
                    attribute_to_parent_company=inc.attribute_to_parent_company_bn_vnd,
                    attribute_to_parent_company_yoy=inc.attribute_to_parent_company_yo_y_percent,
                    general_admin_expenses=inc.general_admin_expenses,
                    profit_before_tax=inc.profit_before_tax,
                    business_income_tax_current=inc.business_income_tax_current,
                    business_income_tax_deferred=inc.business_income_tax_deferred,
                    minority_interest=inc.minority_interest,
                    net_profit_for_the_year=inc.net_profit_for_the_year,
                    attributable_to_parent_company=inc.attributable_to_parent_company,
                    net_other_income=inc.net_other_income_expenses,
                    net_other_income_expenses=inc.net_other_income_expenses,
                    interest_and_similar_income=None,
                    interest_and_similar_expenses=None,
                    net_interest_income=None,
                    fees_and_comission_income=None,
                    fees_and_comission_expenses=None,
                    net_fee_and_commission_income=None,
                    net_gain_foreign_currency_and_gold_dealings=None,
                    net_gain_trading_of_trading_securities=None,
                    net_gain_disposal_of_investment_securities=None,
                    other_expenses=None,
                    dividends_received=None,
                    total_operating_revenue=None,
                    operating_profit_before_provision=None,
                    provision_for_credit_losses=None,
                    tax_for_the_year=None,
                    eps_basis=None,
                )
                for inc in qs
            ]

        except Exception as e:
            import traceback
            print(f"Error in get_income_statements: {e}")
            print(traceback.format_exc())
            raise HttpError(500, "Lỗi hệ thống, vui lòng thử lại sau.")
    
    def get_balance_sheets(self, symbol_id: int) -> List[BalanceSheetOut]:
        """Get balance sheets for a symbol"""
        try:
            qs = qs_balance_sheet(symbol_id)
            if not qs.exists():
                raise HttpError(404, f"No balance sheets found for symbol_id={symbol_id}")

            return [
                BalanceSheetOut(
                    year=bs.year_report,
                    quarter=bs.length_report,
                    symbol=SymbolOut(
                        id=bs.symbol.id,
                        name=bs.symbol.name,
                        exchange=getattr(bs.symbol, "exchange", None)
                    ),
                    current_assets=bs.current_assets_bn_vnd,
                    cash_and_cash_equivalents=bs.cash_and_cash_equivalents_bn_vnd,
                    short_term_investments=bs.short_term_investments_bn_vnd,
                    accounts_receivable=bs.accounts_receivable_bn_vnd,
                    net_inventories=bs.net_inventories,
                    prepayments_to_suppliers=bs.prepayments_to_suppliers_bn_vnd,
                    other_current_assets=bs.other_current_assets_bn_vnd,
                    long_term_assets=bs.long_term_assets_bn_vnd,
                    fixed_assets=bs.fixed_assets_bn_vnd,
                    long_term_investments=bs.long_term_investments_bn_vnd,
                    long_term_prepayments=bs.long_term_prepayments_bn_vnd,
                    other_long_term_assets=bs.other_long_term_assets_bn_vnd,
                    other_long_term_receivables=bs.other_long_term_receivables_bn_vnd,
                    long_term_trade_receivables=bs.long_term_trade_receivables_bn_vnd,
                    total_assets=bs.total_assets_bn_vnd,
                    liabilities=bs.liabilities_bn_vnd,
                    current_liabilities=bs.current_liabilities_bn_vnd,
                    short_term_borrowings=bs.short_term_borrowings_bn_vnd,
                    advances_from_customers=bs.advances_from_customers_bn_vnd,
                    long_term_liabilities=bs.long_term_liabilities_bn_vnd,
                    long_term_borrowings=bs.long_term_borrowings_bn_vnd,
                    owners_equity=bs.owners_equitybn_vnd, 
                    capital_and_reserves=bs.capital_and_reserves_bn_vnd,
                    common_shares=bs.common_shares_bn_vnd,
                    paid_in_capital=bs.paid_in_capital_bn_vnd,
                    undistributed_earnings=bs.undistributed_earnings_bn_vnd,
                    investment_and_development_funds=bs.investment_and_development_funds_bn_vnd,
                    total_resources=bs.total_resources_bn_vnd,
                )
                for bs in qs
            ]

        except Exception as e:
            import traceback
            print(f"Error in get_balance_sheets: {e}")
            print(traceback.format_exc())
            raise HttpError(500, "Lỗi hệ thống, vui lòng thử lại sau.")
        
    def get_ratios(self, symbol_id: int) -> List[RatioOut]:
        """Get all financial ratios for a symbol"""
        try:
            from apps.calculate.repositories import qs_ratio
            qs = qs_ratio(symbol_id)
            if not qs.exists():
                raise HttpError(404, f"No financial ratios found for symbol_id={symbol_id}")
            
            return [
                RatioOut(
                    year=ratio.year_report,
                    quarter=ratio.length_report,
                    symbol=RatioSymbolOut(
                        id=ratio.symbol.id,
                        name=ratio.symbol.name,
                        exchange=getattr(ratio.symbol, "exchange", None)
                    ),
                    st_lt_borrowings_equity=ratio.st_lt_borrowings_equity,
                    debt_equity=ratio.debt_equity,
                    fixed_asset_to_equity=ratio.fixed_asset_to_equity,
                    owners_equity_charter_capital=ratio.owners_equity_charter_capital,
                    asset_turnover=ratio.asset_turnover,
                    fixed_asset_turnover=ratio.fixed_asset_turnover,
                    days_sales_outstanding=ratio.days_sales_outstanding,
                    days_inventory_outstanding=ratio.days_inventory_outstanding,
                    days_payable_outstanding=ratio.days_payable_outstanding,
                    cash_cycle=ratio.cash_cycle,
                    inventory_turnover=ratio.inventory_turnover,
                    ebit_margin_percent=ratio.ebit_margin_percent,
                    gross_profit_margin_percent=ratio.gross_profit_margin_percent,
                    net_profit_margin_percent=ratio.net_profit_margin_percent,
                    roe_percent=ratio.roe_percent,
                    roic_percent=ratio.roic_percent,
                    roa_percent=ratio.roa_percent,
                    ebitda_bn_vnd=ratio.ebitda_bn_vnd,
                    ebit_bn_vnd=ratio.ebit_bn_vnd,
                    dividend_yield_percent=ratio.dividend_yield_percent,
                    current_ratio=ratio.current_ratio,
                    cash_ratio=ratio.cash_ratio,
                    quick_ratio=ratio.quick_ratio,
                    interest_coverage=ratio.interest_coverage,
                    financial_leverage=ratio.financial_leverage,
                    market_capital_bn_vnd=ratio.market_capital_bn_vnd,
                    outstanding_share_mil_shares=ratio.outstanding_share_mil_shares,
                    p_e=ratio.p_e,
                    p_b=ratio.p_b,
                    p_s=ratio.p_s,
                    p_cash_flow=ratio.p_cash_flow,
                    eps_vnd=ratio.eps_vnd,
                    bvps_vnd=ratio.bvps_vnd,
                    ev_ebitda=ratio.ev_ebitda,
                )
                for ratio in qs
            ]

        except Exception as e:
            import traceback
            print(f"Error in get_ratios: {e}")
            print(traceback.format_exc())
            raise HttpError(500, "Lỗi hệ thống, vui lòng thử lại sau.")

