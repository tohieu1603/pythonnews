import time
from typing import Any, Dict, List, Optional
from django.http import Http404
import pandas as pd
from django.shortcuts import get_object_or_404
from vnstock import Listing
from ninja.errors import HttpError
from apps.stock.clients.vnstock_client import VNStockClient
from apps.stock.models import Symbol, Events
from apps.stock.repositories import repositories as repo
from apps.stock.services.mappers import DataMappers
from apps.stock.services.industry_resolver import IndustryResolver
from apps.stock.services.company_processor import CompanyProcessor
from apps.stock.services.payload_builder import PayloadBuilder
from apps.stock.services.fetch_service import FetchService
from apps.stock.services.cache_service import VNStockCacheService
from apps.stock.utils.safe import (
    safe_str,
    to_datetime,
    to_epoch_seconds,
)
from django.utils import timezone
from datetime import timedelta
from apps.stock.schemas import SymbolList, SymbolOutBasic
from core.db_utils import ensure_django_connection_closed
from django.db import reset_queries

class SymbolService:
    def __init__(
        self, vn_client: Optional[VNStockClient] = None, per_symbol_sleep: float = 0.2,
        max_workers: int = 10, batch_size: int = 20
    ):
        self.vn_client = vn_client or VNStockClient()
        self.per_symbol_sleep = per_symbol_sleep
        self.max_workers = max_workers
        self.batch_size = batch_size
        # Initialize helper services
        self.industry_resolver = IndustryResolver()
        self.company_processor = CompanyProcessor()
        self.payload_builder = PayloadBuilder()
        self.fetch_service = FetchService(
            max_retries=getattr(self.vn_client, 'max_retries', 5),
            wait_seconds=getattr(self.vn_client, 'wait_seconds', 60)
        )
        # Initialize cache service for better performance
        self.cache_service = VNStockCacheService()

    # -------- Delegation methods to helper services --------
    def _fetch_shareholders_df(self, symbol_name: str) -> pd.DataFrame:
        """Delegate to fetch service."""
        return self.fetch_service.fetch_shareholders_df(symbol_name)

    def _fetch_events_df(self, symbol_name: str) -> pd.DataFrame:
        """Delegate to fetch service."""
        return self.fetch_service.fetch_events_df(symbol_name)

    def _fetch_officers_df(self, symbol_name: str) -> pd.DataFrame:
        """Delegate to fetch service."""
        return self.fetch_service.fetch_officers_df(symbol_name)
    def _fetch_news_df(self, symbol_name: str) -> pd.DataFrame:
        """Delegate to fetch service."""
        return self.fetch_service.fetch_news_df(symbol_name)
    def _build_shareholder_rows(self, company_obj, df: pd.DataFrame) -> List[Dict]:
        return DataMappers.build_shareholder_rows(company_obj, df)

    def _build_event_rows(self, df: pd.DataFrame) -> List[Dict]:
        return DataMappers.map_events(df)
    def _build_news_rows(self, df: pd.DataFrame) -> List[Dict]:
        return DataMappers.map_news(df)

    def _build_officer_rows(self, df: pd.DataFrame) -> List[Dict]:
        return DataMappers.map_officers(df)
    
    
    def import_all_symbols(self, exchange: str = "HSX", force_update: bool = False) -> Dict[str, Any]:
        """
        Import ALL stock data (symbols, companies, industries, shareholders, officers, events, sub_companies)
        for all symbols with detailed logging for each table.

        Args:
            exchange: Exchange to import (HSX, HNX, UPCOM). Default: HSX
            force_update: If False (default), skip symbols that already have data.
                         If True, re-import all symbols (to get latest data from vnstock).
        """
        from apps.stock.models import ShareHolder, Officers, Events, SubCompany

        mode_text = "FORCE UPDATE MODE" if force_update else "RESUME MODE"

        result = {
            "exchange": exchange,
            "mode": mode_text,
            "total_symbols": 0,
            "symbols_processed": 0,
            "symbols_failed": 0,
            "total_companies": 0,
            "total_industries": 0,
            "total_shareholders": 0,
            "total_officers": 0,
            "total_events": 0,
            "total_sub_companies": 0,
            "errors": [],
            "details": []
        }

        print(f"\n{'='*60}")
        print(f"STOCK IMPORT - {mode_text}")
        print(f"Exchange: {exchange}")
        print(f"{'='*60}\n")

        try:
            # Step 1: Import Symbols from vnstock
            print(f"[1/7] → Importing Symbols from {exchange}...", end=" ")
            symbols_imported = self._import_symbols_from_vnstock(exchange)
            result["total_symbols"] = symbols_imported
            print(f"✓ SUCCESS ({symbols_imported} symbols)")

            # Get symbols to process
            symbols = Symbol.objects.all().order_by('name')

            if not force_update:
                symbols_to_process = []
                for symbol in symbols:
                    has_company = hasattr(symbol, 'company') and symbol.company is not None
                    has_shareholders = has_company and ShareHolder.objects.filter(company=symbol.company).exists()
                    has_officers = has_company and Officers.objects.filter(company=symbol.company).exists()
                    has_events = has_company and Events.objects.filter(company=symbol.company).exists()
                    has_subs = has_company and SubCompany.objects.filter(parent=symbol.company).exists()

                    # Process if missing any data
                    if not (has_company and has_shareholders and has_officers and has_events and has_subs):
                        symbols_to_process.append(symbol)

                symbols = symbols_to_process
                print(f"  ℹ Resume mode: {len(symbols)} symbols need processing\n")
            else:
                symbols = list(symbols)
                print(f"  ℹ Force update: Processing all {len(symbols)} symbols\n")

            # Step 2-7: Process each symbol with all data
            total_symbols = len(symbols)
            for idx, symbol in enumerate(symbols, 1):
                symbol_detail = {
                    "symbol": symbol.name,
                    "success": False,
                    "company": False,
                    "industries": 0,
                    "shareholders": 0,
                    "officers": 0,
                    "events": 0,
                    "sub_companies": 0,
                    "errors": []
                }

                try:
                    # Fetch bundle data
                    bundle, ok = self.cache_service.fetch_company_bundle_with_cache(symbol.name)
                    if not ok or not bundle:
                        print(f"\n[{idx}/{total_symbols}] {symbol.name}")
                        print(f"  ⊘ SKIPPED: No bundle data")
                        symbol_detail["errors"].append("No bundle data")
                        result["symbols_failed"] += 1
                        continue

                    # Get overview data
                    overview_df = bundle.get("overview_df_TCBS")
                    if overview_df is None or overview_df.empty:
                        overview_df = bundle.get("overview_df_VCI")
                    if overview_df is None or overview_df.empty:
                        print(f"\n[{idx}/{total_symbols}] {symbol.name}")
                        print(f"  ⊘ SKIPPED: No overview data")
                        symbol_detail["errors"].append("No overview data")
                        result["symbols_failed"] += 1
                        continue

                    print(f"\nSuccessfully fetched data for {symbol.name}")

                    data = overview_df.iloc[0]

                    # Import Company
                    company = self.company_processor.process_company_data(bundle, data)
                    symbol.company = company
                    symbol.save()
                    symbol_detail["company"] = True
                    result["total_companies"] += 1

                    # Import Industries
                    industries = self.industry_resolver.resolve_symbol_industries(bundle, symbol.name)
                    for industry in industries:
                        repo.upsert_symbol_industry(symbol, industry)
                    symbol_detail["industries"] = len(industries)
                    result["total_industries"] += len(industries)

                    # Import Shareholders
                    print(f"  → Importing Shareholders...", end=" ", flush=True)
                    shareholders_df = bundle.get("shareholders_df")
                    if shareholders_df is not None and not shareholders_df.empty:
                        shareholder_rows = DataMappers.map_shareholders(shareholders_df)
                        repo.upsert_shareholders(company, shareholder_rows)
                        symbol_detail["shareholders"] = len(shareholder_rows)
                        result["total_shareholders"] += len(shareholder_rows)
                        print(f"✓ SUCCESS ({len(shareholder_rows)} records)")
                    else:
                        print(f"⊘ SKIPPED (no data)")

                    # Import Officers
                    print(f"  → Importing Officers...", end=" ", flush=True)
                    officers_df = bundle.get("officers_df")
                    if officers_df is not None and not officers_df.empty:
                        officer_rows = DataMappers.map_officers(officers_df)
                        repo.upsert_officers(company, officer_rows)
                        symbol_detail["officers"] = len(officer_rows)
                        result["total_officers"] += len(officer_rows)
                        print(f"✓ SUCCESS ({len(officer_rows)} records)")
                    else:
                        print(f"⊘ SKIPPED (no data)")

                    # Import Events
                    print(f"  → Importing Events...", end=" ", flush=True)
                    events_df = bundle.get("events_df")
                    if events_df is not None and not events_df.empty:
                        event_rows = DataMappers.map_events(events_df)
                        repo.upsert_events(company, event_rows)
                        symbol_detail["events"] = len(event_rows)
                        result["total_events"] += len(event_rows)
                        print(f"✓ SUCCESS ({len(event_rows)} records)")
                    else:
                        print(f"⊘ SKIPPED (no data)")

                    # Import Sub Companies
                    print(f"  → Importing Sub Companies...", end=" ", flush=True)
                    subsidiaries_df = bundle.get("subsidiaries")
                    if subsidiaries_df is not None and not subsidiaries_df.empty:
                        sub_company_rows = DataMappers.map_sub_company(subsidiaries_df)
                        repo.upsert_sub_company(sub_company_rows, company)
                        symbol_detail["sub_companies"] = len(sub_company_rows)
                        result["total_sub_companies"] += len(sub_company_rows)
                        print(f"✓ SUCCESS ({len(sub_company_rows)} records)")
                    else:
                        print(f"⊘ SKIPPED (no data)")

                    symbol_detail["success"] = True
                    result["symbols_processed"] += 1
                    print(f"  ✓ COMPLETED: All tables imported successfully")

                except Exception as e:
                    error_msg = f"Import error: {str(e)}"
                    symbol_detail["errors"].append(error_msg)
                    result["symbols_failed"] += 1
                    print(f"  ✗ FAILED: {error_msg}")

                finally:
                    result["details"].append(symbol_detail)
                    ensure_django_connection_closed()
                    reset_queries()

                    if self.per_symbol_sleep > 0:
                        time.sleep(self.per_symbol_sleep)

            # Final summary
            print(f"\n{'='*60}")
            print(f"STOCK IMPORT COMPLETE SUMMARY")
            print(f"{'='*60}")
            print(f"Mode:                 {mode_text}")
            print(f"Exchange:             {exchange}")
            print(f"Total Symbols:        {result['total_symbols']}")
            print(f"Processed:            {result['symbols_processed']}")
            print(f"Failed:               {result['symbols_failed']}")
            print(f"Companies:            {result['total_companies']} records")
            print(f"Industries:           {result['total_industries']} mappings")
            print(f"Shareholders:         {result['total_shareholders']} records")
            print(f"Officers:             {result['total_officers']} records")
            print(f"Events:               {result['total_events']} records")
            print(f"Sub Companies:        {result['total_sub_companies']} records")
            print(f"{'='*60}\n")

            return result

        except Exception as e:
            error_msg = f"Import failed: {str(e)}"
            result["errors"].append(error_msg)
            print(f"\n✗ IMPORT FAILED: {error_msg}")
            return result

    def _import_symbols_from_vnstock(self, exchange: str = "HSX") -> int:
        """Import symbols from vnstock and return count"""
        try:
            symbols_df = self.cache_service.fetch_symbols_with_cache(exchange)
            if symbols_df is None or symbols_df.empty:
                print("Failed to fetch symbols from vnstock")
                return 0

            count = 0
            for _, row in symbols_df.iterrows():
                try:
                    symbol_name = safe_str(
                        row.get('symbol') or row.get('ticker') or
                        row.get('Symbol') or row.get('SYMBOL')
                    )
                    if not symbol_name:
                        continue

                    repo.upsert_symbol(symbol_name, defaults={'exchange': exchange})
                    count += 1
                except Exception as e:
                    print(f"Error importing symbol: {e}")
                    continue

            return count
        except Exception as e:
            print(f"Error in _import_symbols_from_vnstock: {e}")
            return 0
    
    def list_symbols_payload(self) -> List[Dict[str, Any]]:
        """List all symbols with industries and minimal company info."""
        symbols = repo.qs_symbols_with_industries()
        data: List[Dict[str, Any]] = []
        for s in symbols:
            industries = [
                {
                    "id": ind.id,
                    "name": ind.name,
                    "updated_at": to_datetime(ind.updated_at),
                }
                for ind in s.industries.all()
            ]
            company_payload = None
            if s.company:
                company_payload = {
                    "id": s.company.id,
                    "company_name": s.company.company_name,
                    "updated_at": to_datetime(s.company.updated_at),
                }
            data.append(
                {
                    "id": s.id,
                    "name": s.name,
                    "exchange": s.exchange,
                    "updated_at": to_datetime(s.updated_at),
                    "industries": industries,
                    "company": company_payload,
                }
            )
        return data
    
    def get_symbols(self, limit: int = 10) -> List[SymbolList]:
        
        symbols = repo.qs_symbols(limit=limit)
        return [
            SymbolList(
                id=s.id,
                name=s.name,
                exchange=s.exchange,
                updated_at=to_datetime(s.updated_at),
            )
            for s in symbols
        ]
    
    def get_symbol_payload(self, symbol: int) -> Dict[str, Any]:
        sym: Symbol = get_object_or_404(repo.qs_symbol_by_name(symbol))
        c = sym.company

        industries = []
        try:
            industries = [
                {
                    "id": ind.id,
                    "name": ind.name,
                    "level": ind.level,
                    "updated_at": to_datetime(ind.updated_at),
                }
                for ind in sym.industries.all()
            ]
        except AttributeError as e:
            print(f"Error accessing industries for symbol {symbol}: {e}")
            try:
                from apps.stock.models import Industry
                symbol_industries = Industry.objects.filter(id = symbol)
                industries = [
                    {
                        "id": ind.id,
                        "name": ind.name,
                        "level": ind.level,
                        "updated_at": to_datetime(ind.updated_at),
                    }
                    for ind in symbol_industries
                ]
            except Exception as e2:
                print(f"Alternative industries access failed: {e2}")
                industries = []

        shareholders = []
        news_list = []
        events_list = []
        officers_list = []
        subsidiaries_list = []

        if c:
            shareholders = [
                {
                    "id": sh.id,
                    "share_holder": sh.share_holder,
                    "quantity": sh.quantity,
                    "share_own_percent": (
                        float(sh.share_own_percent)
                        if sh.share_own_percent is not None
                        else None
                    ),
                    "update_date": to_datetime(sh.update_date),
                }
                for sh in c.shareholders.all().order_by('-share_own_percent')[:7]   
            ]

            news_list = [
                {
                    "id": n.id,
                    "title": n.title,
                    "news_image_url": n.news_image_url,
                    "news_source_link": n.news_source_link,
                    "price_change_pct": (
                        float(n.price_change_pct) if n.price_change_pct is not None else None
                    ),
                    "public_date": to_epoch_seconds(n.public_date),
                }
                for n in c.news.all()[:5]
            ]

            events_list = [
                {
                    "id": e.id,
                    "event_title": e.event_title,
                    "public_date": to_datetime(e.public_date),
                    "issue_date": to_datetime(e.issue_date),
                    "source_url": e.source_url,
                }
                for e in c.events.all().order_by('-public_date')[:6]
            ]

            three_years_ago = timezone.now() - timedelta(days=3*365)

            
            officers_list = [
                {
                    "id": o.id,
                    "officer_name": o.officer_name,
                    "officer_position": o.officer_position,
                    "position_short_name": o.position_short_name,
                    "officer_owner_percent": (
                        float(o.officer_owner_percent)
                        if o.officer_owner_percent is not None
                        else None
                    ),
                    "updated_at": to_datetime(o.updated_at),
                }
                 for o in c.officers.filter(updated_at__gte=three_years_ago)
                       .order_by('-updated_at')
            ]
            subsidiaries_list = [
                {
                    "id": sc.id,
                    "company_name": sc.company_name,
                    "sub_own_percent": (
                        float(sc.sub_own_percent) if sc.sub_own_percent is not None else None
                    ),
                }
                for sc in c.subsidiaries.all()[:5]
            ]

            company_payload = {
                "id": c.id,
                "company_name": c.company_name,
                "company_profile": c.company_profile,
                "history": c.history,
                "issue_share": c.issue_share,
                "financial_ratio_issue_share": c.financial_ratio_issue_share,
                "charter_capital": c.charter_capital,
                "outstanding_share": c.outstanding_share,
                "foreign_percent": (
                    float(c.foreign_percent) if c.foreign_percent is not None else None
                ),
                "established_year": c.established_year,
                "no_employees": c.no_employees,
                "stock_rating": float(c.stock_rating) if c.stock_rating is not None else None,
                "website": c.website,
                "updated_at": to_datetime(c.updated_at),
                "shareholders": shareholders,
                "news": news_list,
                "events": events_list,
                "officers": officers_list,
                "subsidiaries": subsidiaries_list,
            }
        else:
            company_payload = None

        return {
            "id": sym.id,
            "name": sym.name,
            "exchange": sym.exchange,
            "updated_at": to_datetime(sym.updated_at),
            "industries": industries,
            "company": company_payload,
        }

    def search_symbols_by_name(self, symbol_name: str, limit: int = 20) -> List[SymbolOutBasic]:
        term = (symbol_name or "").strip()
        if not term:
            return []
        queryset = repo.qs_symbols_like(term).order_by('name', 'id')
        if limit:
            queryset = queryset[:limit]
        return [
            SymbolOutBasic(id=sym.id, name=sym.name, exchange=sym.exchange)
            for sym in queryset
        ]

    def get_symbol_payload_by_name(self, symbol_name: str) -> Dict[str, Any]:
        symbol_key = symbol_name.strip()
        if not symbol_key:
            raise HttpError(400, "Symbol name cannot be empty")

        symbol_obj = repo.qs_symbol_name(symbol_key).first()
        if not symbol_obj:
            raise HttpError(404, "Symbol not found")

        return {
            "id": symbol_obj.id,
            "name": symbol_obj.name,
            "exchange": symbol_obj.exchange,
        }

