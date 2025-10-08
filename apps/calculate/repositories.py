import logging
from typing import Dict, Any, Optional
from django.db import transaction
from apps.calculate.models import CashFlow, IncomeStatement, BalanceSheet, Ratio
from apps.stock.models import Symbol

logger = logging.getLogger(__name__)


class CalculateRepository:
    """Repository class cho calculate models"""
    
    def upsert_cash_flow(self, data: Dict[str, Any]) -> Optional[CashFlow]:
        """Upsert cash flow record"""
        return upsert_cash_flow(data)
    
    def upsert_income_statement(self, data: Dict[str, Any]) -> Optional[IncomeStatement]:
        """Upsert income statement record"""
        return upsert_income_statement(data)
    
    def upsert_balance_sheet(self, data: Dict[str, Any]) -> Optional[BalanceSheet]:
        """Upsert balance sheet record"""
        return upsert_balance_sheet(data)
    
    def upsert_ratio(self, data: Dict[str, Any]) -> Optional[Ratio]:
        """Upsert ratio record"""
        return upsert_ratio(data)
    
    def get_cash_flows(self, symbol_id: int, limit: Optional[int] = None):
        """Get cash flows for symbol"""
        return qs_cash_flow(symbol_id, limit)
    
    def get_income_statements(self, symbol_id: int):
        """Get income statements for symbol"""
        return qs_income_statement(symbol_id)
    
    def get_balance_sheets(self, symbol_id: int):
        """Get balance sheets for symbol"""
        return qs_balance_sheet(symbol_id)
    
    def get_ratios(self, symbol_id: int):
        """Get ratios for symbol"""
        return qs_ratio(symbol_id)  

def upsert_balance_sheet(data: Dict[str, Any]) -> Optional[BalanceSheet]:
    try:
        symbol = data.pop('symbol')
        year_report = data.pop('year_report')
        length_report = data.pop('length_report')

        with transaction.atomic():
            obj, _ = BalanceSheet.objects.update_or_create(
                symbol=symbol,
                year_report=year_report,
                length_report=length_report,
                defaults=data
            )
        return obj
    except Exception as e:
        logger.error(f"[upsert_balance_sheet] {e}")
        return None

def upsert_income_statement(data: Dict[str, Any]) -> Optional[IncomeStatement]:
    try:
        symbol = data.pop('symbol')
        year_report = data.pop('year_report')
        length_report = data.pop('length_report')

        with transaction.atomic():
            obj, _ = IncomeStatement.objects.update_or_create(
                symbol=symbol,
                year_report=year_report,
                length_report=length_report,
                defaults=data
            )
        return obj
    except Exception as e:
        logger.error(f"[upsert_income_statement] {e}")
        return None

def upsert_cash_flow(data: Dict[str, Any]) -> Optional[CashFlow]:
    try:
        symbol = data.pop('symbol')
        year_report = data.pop('year_report')
        length_report = data.pop('length_report')

        with transaction.atomic():
            obj, _ = CashFlow.objects.update_or_create(
                symbol=symbol,
                year_report=year_report,
                length_report=length_report,
                defaults=data
            )
        return obj
    except Exception as e:
        logger.error(f"[upsert_cash_flow] {e}")
        return None

def upsert_ratio(data: Dict[str, Any]) -> Optional[Ratio]:
    try:
        symbol = data.pop('symbol')
        year_report = data.pop('year_report')
        length_report = data.pop('length_report')

        with transaction.atomic():
            obj, _ = Ratio.objects.update_or_create(
                symbol=symbol,
                year_report=year_report,
                length_report=length_report,
                defaults=data
            )
        return obj
    except Exception as e:
        logger.error(f"[upsert_ratio] {e}")
        return None

def qs_cash_flow(symbol_id: int, limit: Optional[int] = None):
    try:
        from datetime import datetime
        current_year = datetime.now().year
        ten_years_ago = current_year - 8
        
        qs = CashFlow.objects.filter(
            symbol_id=symbol_id,
            year_report__gte=ten_years_ago
        ).select_related('symbol').order_by('-year_report', '-length_report')
        
        if limit:
            qs = qs[:limit]
        return qs
    except Exception as e:
        logger.error(f"[qs_cash_flow] Error fetching cash flows for symbol_id={symbol_id}: {e}")
        return CashFlow.objects.none() 

def qs_income_statement(symbol_id: int):
    try:
        from datetime import datetime
        current_year = datetime.now().year
        ten_years_ago = current_year - 8
        
        return IncomeStatement.objects.filter(
            symbol_id=symbol_id,
            year_report__gte=ten_years_ago
        ).select_related('symbol').order_by('-year_report', '-length_report')
    except Exception as e:
        logger.error(f"[qs_income_statement] Error fetching income statements for symbol_id={symbol_id}: {e}")
        return IncomeStatement.objects.none()

def qs_balance_sheet(symbol_id: int):
    try:
        from datetime import datetime
        current_year = datetime.now().year
        ten_years_ago = current_year - 8
        
        return BalanceSheet.objects.filter(
            symbol_id=symbol_id,
            year_report__gte=ten_years_ago
        ).select_related('symbol').order_by('-year_report', '-length_report')
    except Exception as e:
        logger.error(f"[qs_balance_sheet] Error fetching balance sheets for symbol_id={symbol_id}: {e}")
        return BalanceSheet.objects.none()

def qs_ratio(symbol_id: int):
    try:
        from datetime import datetime
        current_year = datetime.now().year
        ten_years_ago = current_year - 8
        
        return Ratio.objects.filter(
            symbol_id=symbol_id,
            year_report__gte=ten_years_ago
        ).select_related('symbol').order_by('-year_report', '-length_report')[:10]
    except Exception as e:
        logger.error(f"[qs_ratio] Error fetching ratios for symbol_id={symbol_id}: {e}")
        return Ratio.objects.none()
    
def qs_ratio(symbol_id: int):
    try:
        from datetime import datetime
        current_year = datetime.now().year
        ten_years_ago = current_year - 8
        
        return Ratio.objects.filter(
            symbol_id=symbol_id,
            year_report__gte=ten_years_ago
        ).select_related('symbol').order_by('-year_report', '-length_report')[:10]
    except Exception as e:
        logger.error(f"[qs_ratio] Error fetching ratios for symbol_id={symbol_id}: {e}")
        return Ratio.objects.none()