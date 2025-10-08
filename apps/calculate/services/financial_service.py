from typing import Optional, Dict, List, Any
import os
import logging
import time
import pandas as pd

from django.db import transaction
from apps.calculate.repositories import (
    upsert_balance_sheet,
    upsert_income_statement,
    upsert_cash_flow,
    upsert_ratio,
)
from apps.calculate.vnstock import VNStock
from apps.calculate.models import BalanceSheet, IncomeStatement, CashFlow, Ratio
from apps.stock.models import Symbol
from apps.stock.utils.safe import safe_int, safe_decimal, safe_str


logger = logging.getLogger(__name__)


class CalculateService:
    """Service để import financial data từ vnstock theo mapping chính xác"""

    def __init__(self, vnstock_client: Optional[VNStock] = None, sleep_between_symbols: int = 1):
        self.vnstock_client = vnstock_client or VNStock()
        self.sleep_between_symbols = sleep_between_symbols

    def import_all_financials(self) -> Dict[str, Any]:
        """Import financial data for ALL symbols in database."""
        symbols = Symbol.objects.all().order_by('name')

        result = {
            "total_symbols": symbols.count(),
            "successful_symbols": 0,
            "failed_symbols": 0,
            "total_balance_sheets": 0,
            "total_income_statements": 0,
            "total_cash_flows": 0,
            "total_ratios": 0,
            "errors": [],
            "details": []
        }

        print(f"Starting import for {result['total_symbols']} symbols...")
        
        for symbol in symbols:
            print(f"Processing symbol: {symbol.name}")
            symbol_result = self._import_symbol_data(symbol)
            
            result["details"].append(symbol_result)
            
            if symbol_result.get("success", False):
                print(f"✓ Successfully imported {symbol.name}")
                result["successful_symbols"] += 1
                result["total_balance_sheets"] += symbol_result.get("balance_sheets", 0)
                result["total_income_statements"] += symbol_result.get("income_statements", 0)
                result["total_cash_flows"] += symbol_result.get("cash_flows", 0)
                result["total_ratios"] += symbol_result.get("ratios", 0)
            else:
                print(f"✗ Failed to import {symbol.name}")
                result["failed_symbols"] += 1
                result["errors"].extend(symbol_result.get("errors", []))
            
            if self.sleep_between_symbols > 0:
                time.sleep(self.sleep_between_symbols)

        print(f"Import completed: {result['successful_symbols']}/{result['total_symbols']} symbols successful")
        return result

    def import_income_statements_all(self) -> Dict[str, Any]:
        """Import ONLY income statements for all symbols in DB."""
        symbols = Symbol.objects.all().order_by('name')

        result = {
            "total_symbols": symbols.count(),
            "successful_symbols": 0,
            "failed_symbols": 0,
            "total_income_statements": 0,
            "errors": [],
            "details": []
        }

        for symbol in symbols:
            detail = {
                "symbol": symbol.name,
                "success": False,
                "income_statements": 0,
                "errors": []
            }
            try:
                ok, bundle = self.vnstock_client.get_full_financial_data(symbol.name)
                if not ok or not bundle:
                    detail["errors"].append("Failed to fetch data from vnstock")
                else:
                    with transaction.atomic():
                        cnt = self._import_income_statements(symbol, bundle)
                        detail["income_statements"] = cnt
                        detail["success"] = True
                        result["total_income_statements"] += cnt
                        result["successful_symbols"] += 1
            except Exception as e:
                detail["errors"].append(str(e))
                result["failed_symbols"] += 1
            finally:
                result["details"].append(detail)
                if self.sleep_between_symbols > 0:
                    time.sleep(self.sleep_between_symbols)

        return result

    def import_cash_flows_all(self) -> Dict[str, Any]:
        """Import ONLY cash flows for all symbols in DB."""
        symbols = Symbol.objects.all().order_by('name')

        result = {
            "total_symbols": symbols.count(),
            "successful_symbols": 0,
            "failed_symbols": 0,
            "total_cash_flows": 0,
            "errors": [],
            "details": []
        }

        for symbol in symbols:
            detail = {
                "symbol": symbol.name,
                "success": False,
                "cash_flows": 0,
                "errors": []
            }
            try:
                ok, bundle = self.vnstock_client.get_full_financial_data(symbol.name)
                if not ok or not bundle:
                    detail["errors"].append("Failed to fetch data from vnstock")
                else:
                    with transaction.atomic():
                        cnt = self._import_cash_flows(symbol, bundle)
                        detail["cash_flows"] = cnt
                        detail["success"] = True
                        result["total_cash_flows"] += cnt
                        result["successful_symbols"] += 1
            except Exception as e:
                detail["errors"].append(str(e))
                result["failed_symbols"] += 1
            finally:
                result["details"].append(detail)
                if self.sleep_between_symbols > 0:
                    time.sleep(self.sleep_between_symbols)

        return result

    def import_ratios_all(self) -> Dict[str, Any]:
        """Import ONLY ratios for all symbols in DB."""
        symbols = Symbol.objects.all().order_by('name')

        result = {
            "total_symbols": symbols.count(),
            "successful_symbols": 0,
            "failed_symbols": 0,
            "total_ratios": 0,
            "errors": [],
            "details": []
        }

        for symbol in symbols:
            detail = {
                "symbol": symbol.name,
                "success": False,
                "ratios": 0,
                "errors": []
            }
            try:
                ok, bundle = self.vnstock_client.get_full_financial_data(symbol.name)
                if not ok or not bundle:
                    detail["errors"].append("Failed to fetch data from vnstock")
                    result["failed_symbols"] += 1
                else:
                    with transaction.atomic():
                        cnt = self._import_ratios(symbol, bundle)
                        detail["ratios"] = cnt
                        detail["success"] = True
                        result["total_ratios"] += cnt
                        result["successful_symbols"] += 1
            except Exception as e:
                detail["errors"].append(str(e))
                result["failed_symbols"] += 1
            finally:
                result["details"].append(detail)
                if self.sleep_between_symbols > 0:
                    time.sleep(self.sleep_between_symbols)

        return result

    def import_all_complete(self, force_update: bool = False) -> Dict[str, Any]:
        """
        Import ALL financial tables (balance sheet, income statement, cash flow, ratio)
        for all symbols in database with detailed logging for each table.

        Args:
            force_update: If False (default), skip symbols that already have data.
                         If True, re-import all symbols (to get latest data from vnstock).
        """
        symbols = Symbol.objects.all().order_by('name')

        # Filter symbols based on force_update flag
        if not force_update:
            # Only import symbols that don't have complete data
            symbols_to_import = []
            for symbol in symbols:
                has_balance = BalanceSheet.objects.filter(symbol=symbol).exists()
                has_income = IncomeStatement.objects.filter(symbol=symbol).exists()
                has_cashflow = CashFlow.objects.filter(symbol=symbol).exists()
                has_ratio = Ratio.objects.filter(symbol=symbol).exists()

                # Import if missing any table
                if not (has_balance and has_income and has_cashflow and has_ratio):
                    symbols_to_import.append(symbol)

            symbols = symbols_to_import
            mode_text = "RESUME MODE: Importing only incomplete symbols"
        else:
            mode_text = "FORCE UPDATE MODE: Re-importing all symbols"

        total_symbols = len(symbols)

        result = {
            "total_symbols": total_symbols,
            "successful_symbols": 0,
            "failed_symbols": 0,
            "skipped_symbols": 0,
            "total_balance_sheets": 0,
            "total_income_statements": 0,
            "total_cash_flows": 0,
            "total_ratios": 0,
            "errors": [],
            "details": []
        }

        logger.info(f"[IMPORT ALL COMPLETE] {mode_text} - {total_symbols} symbols")
        print(f"\n{'='*60}")
        print(f"{mode_text}")
        print(f"Total symbols to process: {total_symbols}")
        print(f"{'='*60}\n")

        for idx, symbol in enumerate(symbols, 1):
            symbol_detail = {
                "symbol": symbol.name,
                "success": False,
                "balance_sheets": 0,
                "income_statements": 0,
                "cash_flows": 0,
                "ratios": 0,
                "errors": []
            }

            print(f"[{idx}/{total_symbols}] Processing: {symbol.name}")
            logger.info(f"[IMPORT ALL COMPLETE] [{idx}/{total_symbols}] Processing symbol: {symbol.name}")

            try:
                # Fetch data from vnstock
                fetch_success, bundle = self.vnstock_client.get_full_financial_data(symbol.name)

                if not fetch_success or not bundle:
                    error_msg = f"Failed to fetch data from vnstock"
                    symbol_detail["errors"].append(error_msg)
                    logger.error(f"[IMPORT ALL COMPLETE] {symbol.name} - {error_msg}")
                    print(f"  ✗ FAILED: {error_msg}\n")
                    result["failed_symbols"] += 1
                else:
                    # Import all tables in transaction
                    with transaction.atomic():
                        # 1. Import Balance Sheets
                        print(f"  → Importing Balance Sheets...", end=" ")
                        balance_count = self._import_balance_sheets(symbol, bundle)
                        symbol_detail["balance_sheets"] = balance_count
                        result["total_balance_sheets"] += balance_count
                        print(f"✓ SUCCESS ({balance_count} records)")
                        logger.info(f"[IMPORT ALL COMPLETE] {symbol.name} - Balance Sheets: {balance_count} records imported")

                        # 2. Import Income Statements
                        print(f"  → Importing Income Statements...", end=" ")
                        income_count = self._import_income_statements(symbol, bundle)
                        symbol_detail["income_statements"] = income_count
                        result["total_income_statements"] += income_count
                        print(f"✓ SUCCESS ({income_count} records)")
                        logger.info(f"[IMPORT ALL COMPLETE] {symbol.name} - Income Statements: {income_count} records imported")

                        # 3. Import Cash Flows
                        print(f"  → Importing Cash Flows...", end=" ")
                        cashflow_count = self._import_cash_flows(symbol, bundle)
                        symbol_detail["cash_flows"] = cashflow_count
                        result["total_cash_flows"] += cashflow_count
                        print(f"✓ SUCCESS ({cashflow_count} records)")
                        logger.info(f"[IMPORT ALL COMPLETE] {symbol.name} - Cash Flows: {cashflow_count} records imported")

                        # 4. Import Ratios
                        print(f"  → Importing Ratios...", end=" ")
                        ratio_count = self._import_ratios(symbol, bundle)
                        symbol_detail["ratios"] = ratio_count
                        result["total_ratios"] += ratio_count
                        print(f"✓ SUCCESS ({ratio_count} records)")
                        logger.info(f"[IMPORT ALL COMPLETE] {symbol.name} - Ratios: {ratio_count} records imported")

                        symbol_detail["success"] = True
                        result["successful_symbols"] += 1

                        print(f"  ✓ COMPLETED: All tables imported successfully\n")
                        logger.info(f"[IMPORT ALL COMPLETE] {symbol.name} - All tables imported successfully")

            except Exception as e:
                error_msg = f"Import error: {str(e)}"
                symbol_detail["errors"].append(error_msg)
                result["failed_symbols"] += 1
                logger.error(f"[IMPORT ALL COMPLETE] {symbol.name} - {error_msg}")
                print(f"  ✗ FAILED: {error_msg}\n")

            finally:
                result["details"].append(symbol_detail)

                # Sleep between symbols to avoid rate limiting
                if self.sleep_between_symbols > 0 and idx < total_symbols:
                    time.sleep(self.sleep_between_symbols)

        # Final summary
        print(f"\n{'='*60}")
        print(f"IMPORT COMPLETE SUMMARY")
        print(f"{'='*60}")
        print(f"Mode:                 {'FORCE UPDATE' if force_update else 'RESUME'}")
        print(f"Total Symbols:        {result['total_symbols']}")
        print(f"Successful:           {result['successful_symbols']}")
        print(f"Failed:               {result['failed_symbols']}")
        print(f"Balance Sheets:       {result['total_balance_sheets']} records")
        print(f"Income Statements:    {result['total_income_statements']} records")
        print(f"Cash Flows:           {result['total_cash_flows']} records")
        print(f"Ratios:               {result['total_ratios']} records")
        print(f"{'='*60}\n")

        logger.info(f"[IMPORT ALL COMPLETE] Finished: {result['successful_symbols']}/{result['total_symbols']} successful")

        return result

    def _import_symbol_data(self, symbol) -> Dict[str, Any]:
        """Import financial data for a single symbol."""
        symbol_result = {
            "symbol": symbol.name,
            "success": False,
            "balance_sheets": 0,
            "income_statements": 0,
            "cash_flows": 0,
            "ratios": 0,
            "errors": []
        }
        
        try:
            fetch_success, bundle = self.vnstock_client.get_full_financial_data(symbol.name)
            
            if not fetch_success or not bundle:
                symbol_result["errors"].append("Failed to fetch data from vnstock")
                return symbol_result
            
            with transaction.atomic():
                balance_sheet_count = self._import_balance_sheets(symbol, bundle)
                income_statement_count = self._import_income_statements(symbol, bundle)
                cash_flow_count = self._import_cash_flows(symbol, bundle)
                ratio_count = self._import_ratios(symbol, bundle)
                
                symbol_result.update({
                    "success": True,
                    "balance_sheets": balance_sheet_count,
                    "income_statements": income_statement_count,
                    "cash_flows": cash_flow_count,
                    "ratios": ratio_count
                })
        
        except Exception as e:
            logger.error(f"Error importing data for {symbol.name}: {str(e)}")
            symbol_result["errors"].append(f"Import error: {str(e)}")
        
        return symbol_result

    def _import_balance_sheets(self, symbol, bundle) -> int:
        """Import balance sheet data for a symbol."""
        count = 0
        balance_sheet_df = bundle.get('balance_sheet_df', pd.DataFrame())
        
        if balance_sheet_df.empty:
            return count
            
        for _, row in balance_sheet_df.iterrows():
            try:
                mapped_data = self._map_balance_sheet_data(symbol, row.to_dict())
                if mapped_data:
                    upsert_balance_sheet(mapped_data)
                    count += 1
            except Exception as e:
                logger.error(f"Error importing balance sheet for {symbol.name}: {str(e)}")
        
        return count

    def _import_income_statements(self, symbol, bundle) -> int:
        """Import income statement data for a symbol."""
        count = 0
        income_df = bundle.get('income_statement_df', pd.DataFrame())
        
        if income_df.empty:
            return count
            
        for _, row in income_df.iterrows():
            try:
                mapped_data = self._map_income_statement_data(symbol, row.to_dict())
                if mapped_data:
                    upsert_income_statement(mapped_data)
                    count += 1
            except Exception as e:
                logger.error(f"Error importing income statement for {symbol.name}: {str(e)}")
        
        return count

    def _import_cash_flows(self, symbol, bundle) -> int:
        """Import cash flow data for a symbol."""
        count = 0
        cash_flow_df = bundle.get('cash_flow_df', pd.DataFrame())
        
        if cash_flow_df.empty:
            return count
            
        for _, row in cash_flow_df.iterrows():
            try:
                mapped_data = self._map_cash_flow_data(symbol, row.to_dict())
                if mapped_data:
                    upsert_cash_flow(mapped_data)
                    count += 1
            except Exception as e:
                logger.error(f"Error importing cash flow for {symbol.name}: {str(e)}")
        
        return count

    def _import_ratios(self, symbol, bundle) -> int:
        """Import ratio data for a symbol."""
        count = 0
        ratio_df = bundle.get('ratios_df', pd.DataFrame())

        if ratio_df.empty:
            return count

        for _, row in ratio_df.iterrows():
            try:
                mapped_data = self._map_ratio_data(symbol, row.to_dict())
                if mapped_data:
                    upsert_ratio(mapped_data)
                    count += 1
            except Exception as e:
                logger.error(f"Error importing ratio for {symbol.name}: {str(e)}")

        return count

    def _map_balance_sheet_data(self, symbol, data) -> Dict[str, Any]:
        """Map vnstock balance sheet data theo mapping chính xác"""
        year = safe_int(data.get('yearReport'))
        quarter = safe_int(data.get('lengthReport'))
        
        if not year or not quarter:
            return None
        
        return {
            'symbol': symbol,
            'year_report': year,
            'length_report': quarter,
            # Mapping theo bảng Balance Sheet
            'current_assets_bn_vnd': safe_int(data.get('CURRENT ASSETS (Bn. VND)')),
            'cash_and_cash_equivalents_bn_vnd': safe_int(data.get('Cash and cash equivalents (Bn. VND)')),
            'short_term_investments_bn_vnd': safe_int(data.get('Short-term investments (Bn. VND)')),
            'accounts_receivable_bn_vnd': safe_int(data.get('Accounts receivable (Bn. VND)')),
            'net_inventories': safe_int(data.get('Net Inventories')),
            'other_current_assets_bn_vnd': safe_int(data.get('Other current assets (Bn. VND)')),
            'long_term_assets_bn_vnd': safe_int(data.get('LONG-TERM ASSETS (Bn. VND)')),
            'long_term_loans_receivables_bn_vnd': safe_int(data.get('Long-term loans receivables (Bn. VND)')),
            'fixed_assets_bn_vnd': safe_int(data.get('Fixed assets (Bn. VND)')),
            'long_term_investments_bn_vnd': safe_int(data.get('Long-term investments (Bn. VND)')),
            'other_non_current_assets': safe_int(data.get('Other non-current assets')),
            'total_assets_bn_vnd': safe_int(data.get('TOTAL ASSETS (Bn. VND)')),
            'liabilities_bn_vnd': safe_int(data.get('LIABILITIES (Bn. VND)')),
            'current_liabilities_bn_vnd': safe_int(data.get('Current liabilities (Bn. VND)')),
            'long_term_liabilities_bn_vnd': safe_int(data.get('Long-term liabilities (Bn. VND)')),
            'owners_equitybn_vnd': safe_int(data.get("OWNER'S EQUITY(Bn.VND)")),
            'capital_and_reserves_bn_vnd': safe_int(data.get('Capital and reserves (Bn. VND)')),
            'undistributed_earnings_bn_vnd': safe_int(data.get('Undistributed earnings (Bn. VND)')),
            'minority_interests': safe_int(data.get('MINORITY INTERESTS')),
            'total_resources_bn_vnd': safe_int(data.get('TOTAL RESOURCES (Bn. VND)')),
            'prepayments_to_suppliers_bn_vnd': safe_int(data.get('Prepayments to suppliers (Bn. VND)')),
            'short_term_loans_receivables_bn_vnd': safe_int(data.get('Short-term loans receivables (Bn. VND)')),
            'inventories_net_bn_vnd': safe_int(data.get('Inventories, Net (Bn. VND)')),
            'investment_and_development_funds_bn_vnd': safe_int(data.get('Investment and development funds (Bn. VND)')),
            'common_shares_bn_vnd': safe_int(data.get('Common shares (Bn. VND)')),
            'paid_in_capital_bn_vnd': safe_int(data.get('Paid-in capital (Bn. VND)')),
            'long_term_borrowings_bn_vnd': safe_int(data.get('Long-term borrowings (Bn. VND)')),
            'advances_from_customers_bn_vnd': safe_int(data.get('Advances from customers (Bn. VND)')),
            'short_term_borrowings_bn_vnd': safe_int(data.get('Short-term borrowings (Bn. VND)')),
            'good_will_bn_vnd': safe_int(data.get('Good will (Bn. VND)')),
            'long_term_prepayments_bn_vnd': safe_int(data.get('Long-term prepayments (Bn. VND)')),
            'other_long_term_assets_bn_vnd': safe_int(data.get('Other long-term assets (Bn. VND)')),
            'other_long_term_receivables_bn_vnd': safe_int(data.get('Other long-term receivables (Bn. VND)')),
            'long_term_trade_receivables_bn_vnd': safe_int(data.get('Long-term trade receivables (Bn. VND)')),
        }

    def _map_income_statement_data(self, symbol, data) -> Dict[str, Any]:
        """Map vnstock income statement data theo mapping chính xác"""
        year = safe_int(data.get('yearReport'))
        quarter = safe_int(data.get('lengthReport'))
        
        if not year or not quarter:
            return None
            
        return {
            'symbol': symbol,
            'year_report': year,
            'length_report': quarter,
            # Mapping theo bảng Income Statement
            'revenue_yoy_percent': safe_decimal(data.get('Revenue YoY (%)')),
            'revenue_bn_vnd': safe_int(data.get('Revenue (Bn. VND)')),
            'attribute_to_parent_company_bn_vnd': safe_int(data.get('Attribute to parent company (Bn. VND)')),
            'attribute_to_parent_company_yo_y_percent': safe_decimal(data.get('Attribute to parent company YoY (%)')),
            'financial_income': safe_int(data.get('Financial Income')),
            'interest_expenses': safe_int(data.get('Interest Expenses')),
            'sales': safe_int(data.get('Sales')),
            'sales_deductions': safe_int(data.get('Sales deductions')),
            'net_sales': safe_int(data.get('Net Sales')),
            'cost_of_sales': safe_int(data.get('Cost of Sales')),
            'gross_profit': safe_int(data.get('Gross Profit')),
            'financial_expenses': safe_int(data.get('Financial Expenses')),
            'gain_loss_from_joint_ventures': safe_int(data.get('Gain/(loss) from joint ventures')),
            'selling_expenses': safe_int(data.get('Selling Expenses')),
            'general_admin_expenses': safe_int(data.get('General & Admin Expenses')),
            'operating_profit_loss': safe_int(data.get('Operating Profit/Loss')),
            'other_income': safe_int(data.get('Other income')),
            'other_income_expenses': safe_int(data.get('Other Income/Expenses')),
            'net_other_income_expenses': safe_int(data.get('Net other income/expenses')),
            'profit_before_tax': safe_int(data.get('Profit before tax')),
            'business_income_tax_current': safe_int(data.get('Business income tax - current')),
            'business_income_tax_deferred': safe_int(data.get('Business income tax - deferred')),
            'net_profit_for_the_year': safe_int(data.get('Net Profit For the Year')),
            'minority_interest': safe_int(data.get('Minority Interest')),
            'attributable_to_parent_company': safe_int(data.get('Attributable to parent company')),
        }

    def _map_cash_flow_data(self, symbol, data) -> Dict[str, Any]:
        """Map vnstock cash flow data theo mapping chính xác"""
        year_report = safe_int(data.get('yearReport'))
        length_report = safe_int(data.get('lengthReport'))
        
        if year_report is None or length_report is None:
            return None

        return {
            'symbol': symbol,
            'year_report': year_report,
            'length_report': length_report,
            # Mapping theo bảng Cash Flow
            'net_profit_loss_before_tax': safe_int(data.get('Net Profit/Loss before tax')),
            'depreciation_and_amortisation': safe_int(data.get('Depreciation and Amortisation')),
            'provision_for_credit_losses': safe_int(data.get('Provision for credit losses')),
            'unrealized_foreign_exchange_gain_loss': safe_int(data.get('Unrealized foreign exchange gain/loss')),
            'profit_loss_from_investing_activities': safe_int(data.get('Profit/Loss from investing activities')),
            'interest_expense': safe_int(data.get('Interest Expense')),
            'operating_profit_before_changes_in_working_capital': safe_int(data.get('Operating profit before changes in working capital')),
            'increase_decrease_in_receivables': safe_int(data.get('Increase/Decrease in receivables')),
            'increase_decrease_in_inventories': safe_int(data.get('Increase/Decrease in inventories')),
            'increase_decrease_in_payables': safe_int(data.get('Increase/Decrease in payables')),
            'increase_decrease_in_prepaid_expenses': safe_int(data.get('Increase/Decrease in prepaid expenses')),
            'interest_paid': safe_int(data.get('Interest paid')),
            'business_income_tax_paid': safe_int(data.get('Business Income Tax paid')),
            'net_cash_inflows_outflows_from_operating_activities': safe_int(data.get('Net cash inflows/outflows from operating activities')),
            'purchase_of_fixed_assets': safe_int(data.get('Purchase of fixed assets')),
            'proceeds_from_disposal_of_fixed_assets': safe_int(data.get('Proceeds from disposal of fixed assets')),
            'loans_granted_purchases_of_debt_instruments_bn_vnd': safe_int(data.get('Loans granted, purchases of debt instruments (Bn. VND)')),
            'collection_of_loans_proceeds_sales_instruments_vnd': safe_int(data.get('Collection of loans, proceeds from sales of debts instruments (Bn. VND)')),
            'investment_in_other_entities': safe_int(data.get('Investment in other entities')),
            'proceeds_from_divestment_in_other_entities': safe_int(data.get('Proceeds from divestment in other entities')),
            'gain_on_dividend': safe_int(data.get('Gain on Dividend')),
            'net_cash_flows_from_investing_activities': safe_int(data.get('Net Cash Flows from Investing Activities')),
            'increase_in_charter_captial': safe_int(data.get('Increase in charter captial')),
            'payments_for_share_repurchases': safe_int(data.get('Payments for share repurchases')),
            'proceeds_from_borrowings': safe_int(data.get('Proceeds from borrowings')),
            'repayment_of_borrowings': safe_int(data.get('Repayment of borrowings')),
            'finance_lease_principal_payments': safe_int(data.get('Finance lease principal payments')),
            'dividends_paid': safe_int(data.get('Dividends paid')),
            'cash_flows_from_financial_activities': safe_int(data.get('Cash flows from financial activities')),
            'net_increase_decrease_in_cash_and_cash_equivalents': safe_int(data.get('Net increase/decrease in cash and cash equivalents')),
            'cash_and_cash_equivalents': safe_int(data.get('Cash and cash equivalents')),
            'foreign_exchange_differences_adjustment': safe_int(data.get('Foreign exchange differences Adjustment')),
            'cash_and_cash_equivalents_at_the_end_of_period': safe_int(data.get('Cash and Cash Equivalents at the end of period')),
        }

    def _map_ratio_data(self, symbol, data) -> Dict[str, Any]:
        """Map vnstock ratio data theo mapping chính xác"""
        # Ratio data có key dạng tuple: ('Meta', 'yearReport')
        year_report = safe_int(data.get(('Meta', 'yearReport')) or data.get('yearReport'))
        length_report = safe_int(data.get(('Meta', 'lengthReport')) or data.get('lengthReport'))
        
        if year_report is None or length_report is None or year_report == 0 or length_report == 0:
            return None
            
        return {
            'symbol': symbol,
            'year_report': year_report,
            'length_report': length_report,
            # Mapping theo bảng Ratio với tuple keys
            'st_lt_borrowings_equity': safe_decimal(data.get(('Chỉ tiêu cơ cấu nguồn vốn', '(ST+LT borrowings)/Equity'))),
            'debt_equity': safe_decimal(data.get(('Chỉ tiêu cơ cấu nguồn vốn', 'Debt/Equity'))),
            'fixed_asset_to_equity': safe_decimal(data.get(('Chỉ tiêu cơ cấu nguồn vốn', 'Fixed Asset-To-Equity'))),
            'owners_equity_charter_capital': safe_decimal(data.get(('Chỉ tiêu cơ cấu nguồn vốn', "Owners' Equity/Charter Capital"))),
            'asset_turnover': safe_decimal(data.get(('Chỉ tiêu hiệu quả hoạt động', 'Asset Turnover'))),
            'fixed_asset_turnover': safe_decimal(data.get(('Chỉ tiêu hiệu quả hoạt động', 'Fixed Asset Turnover'))),
            'days_sales_outstanding': safe_decimal(data.get(('Chỉ tiêu hiệu quả hoạt động', 'Days Sales Outstanding'))),
            'days_inventory_outstanding': safe_decimal(data.get(('Chỉ tiêu hiệu quả hoạt động', 'Days Inventory Outstanding'))),
            'days_payable_outstanding': safe_decimal(data.get(('Chỉ tiêu hiệu quả hoạt động', 'Days Payable Outstanding'))),
            'cash_cycle': safe_decimal(data.get(('Chỉ tiêu hiệu quả hoạt động', 'Cash Cycle'))),
            'inventory_turnover': safe_decimal(data.get(('Chỉ tiêu hiệu quả hoạt động', 'Inventory Turnover'))),
            'ebit_margin_percent': safe_decimal(data.get(('Chỉ tiêu khả năng sinh lợi', 'EBIT Margin (%)'))),
            'gross_profit_margin_percent': safe_decimal(data.get(('Chỉ tiêu khả năng sinh lợi', 'Gross Profit Margin (%)'))),
            'net_profit_margin_percent': safe_decimal(data.get(('Chỉ tiêu khả năng sinh lợi', 'Net Profit Margin (%)'))),
            'roe_percent': safe_decimal(data.get(('Chỉ tiêu khả năng sinh lợi', 'ROE (%)'))),
            'roic_percent': safe_decimal(data.get(('Chỉ tiêu khả năng sinh lợi', 'ROIC (%)'))),
            'roa_percent': safe_decimal(data.get(('Chỉ tiêu khả năng sinh lợi', 'ROA (%)'))),
            'ebitda_bn_vnd': safe_int(data.get(('Chỉ tiêu khả năng sinh lợi', 'EBITDA (Bn. VND)'))),
            'ebit_bn_vnd': safe_int(data.get(('Chỉ tiêu khả năng sinh lợi', 'EBIT (Bn. VND)'))),
            'dividend_yield_percent': safe_decimal(data.get(('Chỉ tiêu khả năng sinh lợi', 'Dividend yield (%)'))),
            'current_ratio': safe_decimal(data.get(('Chỉ tiêu thanh khoản', 'Current Ratio'))),
            'cash_ratio': safe_decimal(data.get(('Chỉ tiêu thanh khoản', 'Cash Ratio'))),
            'quick_ratio': safe_decimal(data.get(('Chỉ tiêu thanh khoản', 'Quick Ratio'))),
            'interest_coverage': safe_decimal(data.get(('Chỉ tiêu thanh khoản', 'Interest Coverage'))),
            'financial_leverage': safe_decimal(data.get(('Chỉ tiêu thanh khoản', 'Financial Leverage'))),
            'market_capital_bn_vnd': safe_int(data.get(('Chỉ tiêu định giá', 'Market Capital (Bn. VND)'))),
            'outstanding_share_mil_shares': safe_int(data.get(('Chỉ tiêu định giá', 'Outstanding Share (Mil. Shares)'))),
            'p_e': safe_decimal(data.get(('Chỉ tiêu định giá', 'P/E'))),
            'p_b': safe_decimal(data.get(('Chỉ tiêu định giá', 'P/B'))),
            'p_s': safe_decimal(data.get(('Chỉ tiêu định giá', 'P/S'))),
            'p_cash_flow': safe_decimal(data.get(('Chỉ tiêu định giá', 'P/Cash Flow'))),
            'eps_vnd': safe_decimal(data.get(('Chỉ tiêu định giá', 'EPS (VND)'))),
            'bvps_vnd': safe_decimal(data.get(('Chỉ tiêu định giá', 'BVPS (VND)'))),
            'ev_ebitda': safe_decimal(data.get(('Chỉ tiêu định giá', 'EV/EBITDA'))),
        }
