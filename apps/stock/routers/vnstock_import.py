# apps/stock/routers/vnstock_import.py
"""VNStock Import API routes."""

from typing import Dict, Any
from ninja import Router, Query
from ninja.errors import HttpError
from ninja.pagination import paginate, PageNumberPagination
from apps.stock.schemas import CompanyOut, SymbolList, SubCompanyOut, SymbolOutBasic
from apps.stock.services.symbol_service import SymbolService
from typing import List
from apps.stock.services.vnstock_import_service import VnstockImportService
from apps.stock.services.cache_service import VNStockCacheService
from apps.stock.services.rate_limiter import get_rate_limiter

router = Router(tags=["vnstock-import"])


@router.post("/symbols/import_all")
def import_all_symbols(request, exchange: str = "HSX", force_update: bool = False):
    """
    Import ALL stock data (symbols, companies, industries, shareholders, officers, events, sub_companies)
    for all symbols with detailed logging for each table.

    Query Parameters:
    - exchange (str): Exchange to import (HSX, HNX, UPCOM). Default: HSX
    - force_update (bool):
        - False (default): Resume mode - only import symbols missing data
        - True: Force update mode - re-import all symbols to get latest data
    """
    import time

    try:
        start_time = time.time()
        service = SymbolService()
        result = service.import_all_symbols(exchange=exchange, force_update=force_update)
        processing_time = time.time() - start_time
        result["processing_time"] = round(processing_time, 2)

        return result

    except Exception as e:
        return {
            "error": f"Import failed: {str(e)}",
            "exchange": exchange,
            "force_update": force_update
        }


@router.post("/import/symbols")
def import_symbols_from_vnstock(request, exchange: str = "HSX"):
    """Import tất cả symbols từ vnstock theo exchange"""
    service = VnstockImportService()
    return service.import_all_symbols_from_vnstock(exchange)


@router.post("/import/companies") 
def import_companies_for_symbols(request, exchange: str = "HSX"):
    """Import company data cho tất cả symbols có trong database"""
    service = VnstockImportService()
    return service.import_companies_from_vnstock(exchange)


@router.post("/import/industries")
def import_industries_for_symbols(request):
    """Import industry data và tạo quan hệ với symbols"""
    service = VnstockImportService()
    return service.import_industries_for_symbols()


@router.post("/import/shareholders")
def import_shareholders_for_all_symbols(request):
    """Import shareholders cho tất cả symbols có company"""
    service = VnstockImportService()
    return service.import_shareholders_for_all_symbols()


@router.post("/import/officers")
def import_officers_for_all_symbols(request):
    """Import officers cho tất cả symbols có company"""
    service = VnstockImportService()
    return service.import_officers_for_all_symbols()


@router.post("/import/events")
def import_events_for_all_symbols(request):
    """Import events cho tất cả symbols có company"""
    service = VnstockImportService()
    return service.import_events_for_all_symbols()


@router.post("/import/sub_companies")
def import_sub_companies_for_all_symbols(request):
    """Import sub companies (subsidiaries) cho tất cả symbols có company"""
    service = VnstockImportService()
    results = service.import_sub_companies_for_all_symbols()
    total_sub_companies = sum(r.get('sub_companies_count', 0) for r in results)
    return {
        "symbols_processed": len(results),
        "total_sub_companies": total_sub_companies,
        "results": results
    }

@router.get("/symbols/{symbol}")
def get_symbol_with_all_relations(request, symbol: int):
    """Lấy thông tin symbol với tất cả bảng liên quan: company, industries, shareholders, officers, events, sub_companies"""
    from apps.stock.services.symbol_service import SymbolService
    service = SymbolService()
    return service.get_symbol_payload(symbol)


@router.get("/symbols")
def list_symbols_with_basic_info(request, limit: int = 10):
    """Lấy danh sách symbols với thông tin cơ bản"""
    from apps.stock.services.symbol_service import SymbolService
    service = SymbolService()
    return service.get_symbols(limit=limit)


@router.get("/symbols/by-name/{symbol_name}", response=List[SymbolOutBasic])
def get_symbol_by_name(request, symbol_name: str, limit: int = 20):
    """Tìm kiếm symbol theo ký tự (ví dụ: VCS)."""
    service = SymbolService()
    return service.search_symbols_by_name(symbol_name, limit=limit)


@router.get("/stats")
def get_database_stats(request):
    """Lấy thống kê tổng quan về dữ liệu trong database"""
    from apps.stock.models import Symbol, Company, Industry, ShareHolder, Officers, Events, SubCompany
    from django.db.models import Count, Q
    
    # Basic counts
    symbols_count = Symbol.objects.count()
    companies_count = Company.objects.count()
    industries_count = Industry.objects.count()
    shareholders_count = ShareHolder.objects.count()
    officers_count = Officers.objects.count()
    events_count = Events.objects.count()
    sub_companies_count = SubCompany.objects.count()
    
    # Relationship stats
    symbols_with_company = Symbol.objects.filter(company__isnull=False).count()
    symbols_with_industries = Symbol.objects.filter(industries__isnull=False).distinct().count()
    symbols_with_shareholders = Symbol.objects.filter(company__shareholders__isnull=False).distinct().count()
    symbols_with_officers = Symbol.objects.filter(company__officers__isnull=False).distinct().count()
    symbols_with_events = Symbol.objects.filter(company__events__isnull=False).distinct().count()
    symbols_with_sub_companies = Symbol.objects.filter(company__subsidiaries__isnull=False).distinct().count()
    
    # Coverage percentages
    company_coverage = (symbols_with_company / symbols_count * 100) if symbols_count > 0 else 0
    industries_coverage = (symbols_with_industries / symbols_count * 100) if symbols_count > 0 else 0
    shareholders_coverage = (symbols_with_shareholders / symbols_count * 100) if symbols_count > 0 else 0
    officers_coverage = (symbols_with_officers / symbols_count * 100) if symbols_count > 0 else 0
    events_coverage = (symbols_with_events / symbols_count * 100) if symbols_count > 0 else 0
    sub_companies_coverage = (symbols_with_sub_companies / symbols_count * 100) if symbols_count > 0 else 0
    
    # Exchange breakdown
    exchange_stats = Symbol.objects.values('exchange').annotate(
        count=Count('id'),
        with_company=Count('id', filter=Q(company__isnull=False))
    ).order_by('-count')
    
    return {
        "overview": {
            "symbols": symbols_count,
            "companies": companies_count,
            "industries": industries_count,
            "shareholders": shareholders_count,
            "officers": officers_count,
            "events": events_count,
            "sub_companies": sub_companies_count
        },
        "coverage": {
            "company_coverage": f"{company_coverage:.1f}%",
            "industries_coverage": f"{industries_coverage:.1f}%",
            "shareholders_coverage": f"{shareholders_coverage:.1f}%",
            "officers_coverage": f"{officers_coverage:.1f}%",
            "events_coverage": f"{events_coverage:.1f}%",
            "sub_companies_coverage": f"{sub_companies_coverage:.1f}%"
        },
        "by_exchange": list(exchange_stats)
    }


@router.get("/cache/stats")
def get_cache_stats(request):
    """Lấy thống kê cache performance"""
    cache_service = VNStockCacheService()
    return cache_service.get_cache_stats()


@router.post("/cache/clear")
def clear_cache(request, symbol: str = None):
    """Xóa cache cho symbol cụ thể hoặc toàn bộ cache"""
    cache_service = VNStockCacheService()

    if symbol:
        cache_service.clear_symbol_cache(symbol.upper())
        return {"message": f"Cache cleared for symbol: {symbol.upper()}"}
    else:
        cache_service.clear_cache()
        return {"message": "All cache cleared"}


@router.get("/rate-limit/stats")
def get_rate_limit_stats(request):
    """Lấy thống kê rate limiting"""
    rate_limiter = get_rate_limiter()
    return rate_limiter.get_stats()


@router.post("/rate-limit/reset")
def reset_rate_limit_stats(request):
    """Reset rate limiting statistics"""
    rate_limiter = get_rate_limiter()
    rate_limiter.reset_stats()
    return {"message": "Rate limit statistics reset"}


