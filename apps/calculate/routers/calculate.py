# apps/calculate/routers/calculate.py
"""Calculate API routes for importing financial data."""

from typing import List
from ninja import Router, Schema
from ninja.errors import HttpError
import time
from django.db import transaction
from apps.calculate.services.financial_service import CalculateService
from apps.calculate.services.query_financial_service import QueryFinancialService
from apps.calculate.dtos.cash_flow_dto import CashFlowOut
from apps.calculate.dtos.income_statement_dto import InComeOut
from apps.calculate.dtos.blance_sheet_dto import BalanceSheetOut
from apps.calculate.dtos.ratio_dto import RatioOut
router = Router(tags=["calculate"])


# Output schemas  
class ImportResultSchema(Schema):
    symbol: str
    success: bool
    balance_sheets: int = 0
    income_statements: int = 0
    cash_flows: int = 0
    errors: List[str] = []


class ImportSummarySchema(Schema):
    total_symbols: int
    successful_imports: int
    failed_imports: int
    total_balance_sheets: int
    total_income_statements: int
    total_cash_flows: int
    processing_time: float
    results: List[ImportResultSchema]


@router.post("/import/balance/all", response=ImportSummarySchema)
def import_all_financials(request):
    """Import financial data for ALL symbols in database."""
    try:
        start_time = time.time()
        service = CalculateService()
        result = service.import_all_financials()
        processing_time = time.time() - start_time
        
        return ImportSummarySchema(
            total_symbols=result["total_symbols"],
            successful_imports=result["successful_symbols"],
            failed_imports=result["failed_symbols"],
            total_balance_sheets=result["total_balance_sheets"],
            total_income_statements=result["total_income_statements"],
            total_cash_flows=result["total_cash_flows"],
            processing_time=round(processing_time, 2),
            results=[
                ImportResultSchema(
                    symbol=detail["symbol"],
                    success=detail["success"],
                    balance_sheets=detail["balance_sheets"],
                    income_statements=detail["income_statements"],
                    cash_flows=detail["cash_flows"],
                    errors=detail["errors"]
                ) for detail in result["details"]
            ]
        )
        
    except Exception as e:
        raise HttpError(500, f"Error importing all financials: {str(e)}")


@router.post("/import/income/all", response=ImportSummarySchema)
def import_income_all(request):
    """Import only income statements for ALL symbols in database."""
    try:
        start_time = time.time()
        service = CalculateService()
        result = service.import_income_statements_all()
        processing_time = time.time() - start_time

        return ImportSummarySchema(
            total_symbols=result["total_symbols"],
            successful_imports=result["successful_symbols"],
            failed_imports=result["failed_symbols"],
            total_balance_sheets=result["total_balance_sheets"],
            total_income_statements=result["total_income_statements"],
            total_cash_flows=result["total_cash_flows"],
            processing_time=round(processing_time, 2),
            results=[
                ImportResultSchema(
                    symbol=detail["symbol"],
                    success=detail["success"],
                    balance_sheets=detail["balance_sheets"],
                    income_statements=detail["income_statements"],
                    cash_flows=detail["cash_flows"],
                    errors=detail["errors"]
                ) for detail in result["details"]
            ]
        )
    except Exception as e:
        raise HttpError(500, f"Error importing income statements: {str(e)}")


@router.post("/import/cashflow/all", response=ImportSummarySchema)
def import_cashflow_all(request):
    """Import only cash flows for ALL symbols in database."""
    try:
        start_time = time.time()
        service = CalculateService()
        result = service.import_cash_flows_all()
        processing_time = time.time() - start_time

        return ImportSummarySchema(
            total_symbols=result["total_symbols"],
            successful_imports=result["successful_symbols"],
            failed_imports=result["failed_symbols"],
            total_balance_sheets=result["total_balance_sheets"],
            total_income_statements=result["total_income_statements"],
            total_cash_flows=result["total_cash_flows"],
            processing_time=round(processing_time, 2),
            results=[
                ImportResultSchema(
                    symbol=detail["symbol"],
                    success=detail["success"],
                    balance_sheets=detail["balance_sheets"],
                    income_statements=detail["income_statements"],
                    cash_flows=detail["cash_flows"],
                    errors=detail["errors"]
                ) for detail in result["details"]
            ]
        )
    except Exception as e:
        raise HttpError(500, f"Error importing cash flows: {str(e)}")


@router.post("/import/ratio/all", response=ImportSummarySchema)
def import_ratio_all(request):
    """Import only ratios for ALL symbols in database."""
    try:
        start_time = time.time()
        service = CalculateService()
        result = service.import_ratios_all()
        processing_time = time.time() - start_time

        return ImportSummarySchema(
            total_symbols=result["total_symbols"],
            successful_imports=result["successful_symbols"],
            failed_imports=result["failed_symbols"],
            total_balance_sheets=result["total_balance_sheets"],
            total_income_statements=result["total_income_statements"],
            total_cash_flows=result["total_cash_flows"],
            processing_time=round(processing_time, 2),
            results=[
                ImportResultSchema(
                    symbol=detail["symbol"],
                    success=detail["success"],
                    balance_sheets=detail["balance_sheets"],
                    income_statements=detail["income_statements"],
                    cash_flows=detail["cash_flows"],
                    errors=detail["errors"]
                ) for detail in result["details"]
            ]
        )
    except Exception as e:
        raise HttpError(500, f"Error importing ratios: {str(e)}")


class ImportCompleteResultSchema(Schema):
    symbol: str
    success: bool
    balance_sheets: int = 0
    income_statements: int = 0
    cash_flows: int = 0
    ratios: int = 0
    errors: List[str] = []


class ImportCompleteSummarySchema(Schema):
    total_symbols: int
    successful_imports: int
    failed_imports: int
    total_balance_sheets: int
    total_income_statements: int
    total_cash_flows: int
    total_ratios: int
    processing_time: float
    results: List[ImportCompleteResultSchema]


@router.post("/import/all-complete", response=ImportCompleteSummarySchema)
def import_all_complete(request, force_update: bool = False):
    """
    Import ALL financial data (balance sheet, income statement, cash flow, ratio)
    for ALL symbols in database with detailed logging for each table.

    Query Parameters:
    - force_update (bool):
        - False (default): Resume mode - only import symbols missing data
        - True: Force update mode - re-import all symbols to get latest data
    """
    try:
        start_time = time.time()
        service = CalculateService()
        result = service.import_all_complete(force_update=force_update)
        processing_time = time.time() - start_time

        return ImportCompleteSummarySchema(
            total_symbols=result["total_symbols"],
            successful_imports=result["successful_symbols"],
            failed_imports=result["failed_symbols"],
            total_balance_sheets=result["total_balance_sheets"],
            total_income_statements=result["total_income_statements"],
            total_cash_flows=result["total_cash_flows"],
            total_ratios=result["total_ratios"],
            processing_time=round(processing_time, 2),
            results=[
                ImportCompleteResultSchema(
                    symbol=detail["symbol"],
                    success=detail["success"],
                    balance_sheets=detail["balance_sheets"],
                    income_statements=detail["income_statements"],
                    cash_flows=detail["cash_flows"],
                    ratios=detail["ratios"],
                    errors=detail["errors"]
                ) for detail in result["details"]
            ]
        )
    except Exception as e:
        raise HttpError(500, f"Error importing all complete data: {str(e)}")


@router.get("/cashflows/{symbol_id}", response=List[CashFlowOut])
def get_cashflows(request, symbol_id: int, limit: int = 10):
    service = QueryFinancialService()
    return service.get_cash_flow_statements(symbol_id, limit)
@router.get("/incomes/{symbol_id}", response=List[InComeOut])
def get_incomes(request, symbol_id: int):
    service = QueryFinancialService()
    return service.get_income_statements(symbol_id)
@router.get("/balances/{symbol_id}", response=List[BalanceSheetOut])
def get_balances(request, symbol_id: int):
    service = QueryFinancialService()
    return service.get_balance_sheets(symbol_id)
@router.get("/ratios/{symbol_id}", response=List[RatioOut])
def get_ratios(request, symbol_id: int):
    service = QueryFinancialService()
    return service.get_ratios(symbol_id)